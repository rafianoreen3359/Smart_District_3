import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Message, Presence, Room, room_group_name

HISTORY_LIMIT = 50
MAX_MESSAGE_LENGTH = 1000
CLOSE_UNAUTHENTICATED = 4401
CLOSE_NO_SUCH_ROOM = 4404


def serialize_message(message, username):
    return {
        "id": message.id,
        "username": username,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """One chat room per URL. Only logged-in users may connect.

    Client -> server
      {"type": "message", "content": "hi"}
      {"type": "typing", "is_typing": true}

    Server -> client
      {"type": "history", "messages": [...last 50, oldest first...]}
      {"type": "message", "message": {...}}
      {"type": "presence", "users": ["alice", "bob"]}
      {"type": "typing", "username": "alice", "is_typing": true}
      {"type": "announcement", "title": "...", "body": "...", "created_at": "..."}
      {"type": "error", "code": "...", "detail": "..."}
    """

    async def connect(self):
        self.joined = False
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.group_name = room_group_name(self.room_name)
        user = self.scope.get("user")

        # Closing before accept() rejects the handshake (HTTP 403).
        if user is None or not user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return

        self.user_id = user.pk
        self.username = user.get_username()

        self.room_id = await self.get_room_id()
        if self.room_id is None:
            await self.close(code=CLOSE_NO_SUCH_ROOM)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.joined = True

        await self.add_presence()
        await self.send_json({"type": "history", "messages": await self.get_history()})
        await self.broadcast_presence()

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        self.joined = False
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.remove_presence()
        await self.broadcast_presence()

    # ---- incoming from this client ------------------------------------------
    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if not text_data:
            await self.send_error("unsupported_payload", "Send JSON text frames only.")
            return
        try:
            content = json.loads(text_data)
        except ValueError:
            await self.send_error("invalid_json", "Payload must be valid JSON.")
            return
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type") if isinstance(content, dict) else None

        if kind == "message":
            text = content.get("content")
            text = text.strip() if isinstance(text, str) else ""
            if not text:
                await self.send_error("empty_message", "Write something before sending.")
            elif len(text) > MAX_MESSAGE_LENGTH:
                await self.send_error(
                    "message_too_long",
                    f"Messages can be up to {MAX_MESSAGE_LENGTH} characters; this one has {len(text)}.",
                )
            else:
                message = await self.save_message(text)
                await self.channel_layer.group_send(
                    self.group_name, {"type": "chat.message", "message": message}
                )

        elif kind == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "username": self.username,
                    "is_typing": bool(content.get("is_typing")),
                },
            )
        else:
            await self.send_error("unknown_type", 'Use type "message" or "typing".')

    # ---- group event handlers (Channels maps "chat.message" -> chat_message) -
    async def chat_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

    async def chat_typing(self, event):
        if event["username"] == self.username:
            return  # you do not need to be told that you are typing
        await self.send_json(
            {"type": "typing", "username": event["username"], "is_typing": event["is_typing"]}
        )

    async def presence_update(self, event):
        await self.send_json({"type": "presence", "users": event["users"]})

    async def chat_announcement(self, event):
        await self.send_json(
            {
                "type": "announcement",
                "title": event["title"],
                "body": event["body"],
                "created_at": event["created_at"],
            }
        )

    # ---- helpers -------------------------------------------------------------
    async def send_error(self, code, detail):
        await self.send_json({"type": "error", "code": code, "detail": detail})

    async def broadcast_presence(self):
        users = await self.online_users()
        await self.channel_layer.group_send(
            self.group_name, {"type": "presence.update", "users": users}
        )

    # ---- database access (sync ORM wrapped for the async consumer) ----------
    @database_sync_to_async
    def get_room_id(self):
        return Room.objects.filter(name=self.room_name).values_list("id", flat=True).first()

    @database_sync_to_async
    def get_history(self):
        recent = (
            Message.objects.filter(room_id=self.room_id)
            .select_related("user")
            .order_by("-created_at", "-id")[:HISTORY_LIMIT]
        )
        return [serialize_message(m, m.user.get_username()) for m in reversed(list(recent))]

    @database_sync_to_async
    def save_message(self, content):
        message = Message.objects.create(
            room_id=self.room_id, user_id=self.user_id, content=content
        )
        return serialize_message(message, self.username)

    @database_sync_to_async
    def add_presence(self):
        Presence.objects.create(
            room_id=self.room_id, user_id=self.user_id, channel_name=self.channel_name
        )

    @database_sync_to_async
    def remove_presence(self):
        Presence.objects.filter(channel_name=self.channel_name).delete()

    @database_sync_to_async
    def online_users(self):
        names = Presence.objects.filter(room_id=self.room_id).values_list(
            "user__username", flat=True
        )
        return sorted(set(names))  # one entry per user, even with several tabs open
