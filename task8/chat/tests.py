"""WebsocketCommunicator tests for the chat consumer and the announcement signal.

Run with:  python manage.py test chat
"""
from contextlib import asynccontextmanager

from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase, override_settings

from chat.models import Announcement, Message, Presence, Room
from chat.routing import websocket_urlpatterns

User = get_user_model()

IN_MEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Test the routing + consumer directly. Session auth is bypassed by setting
# scope["user"] ourselves, so no cookies or HTTP login are needed.
application = URLRouter(websocket_urlpatterns)


async def receive_until(communicator, event_type):
    """Return the next event of the given type, skipping any others."""
    while True:
        data = await communicator.receive_json_from()
        if data["type"] == event_type:
            return data


async def drain(communicator):
    """Consume everything already queued for this client."""
    while not await communicator.receive_nothing(timeout=0.2):
        await communicator.receive_json_from()


async def collect(communicator):
    """Return every event that arrives until the client goes quiet."""
    events = []
    while not await communicator.receive_nothing(timeout=0.3):
        events.append(await communicator.receive_json_from())
    return events


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ChatConsumerTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.room = Room.objects.create(name="lobby", created_by=self.alice)

    @asynccontextmanager
    async def joined(self, user, room="lobby"):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{room}/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        self.assertTrue(connected, "authenticated connection should be accepted")
        try:
            yield communicator
        finally:
            await communicator.disconnect()

    async def test_authenticated_user_connects_and_gets_history_then_presence(self):
        async with self.joined(self.alice) as client:
            first = await client.receive_json_from()
            self.assertEqual(first["type"], "history")
            self.assertEqual(first["messages"], [])
            presence = await receive_until(client, "presence")
            self.assertEqual(presence["users"], ["alice"])

    async def test_anonymous_connection_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/chat/lobby/")
        communicator.scope["user"] = AnonymousUser()
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4401)
        self.assertEqual(await database_sync_to_async(Presence.objects.count)(), 0)

    async def test_unknown_room_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/chat/does-not-exist/")
        communicator.scope["user"] = self.alice
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4404)

    async def test_message_is_broadcast_to_room_and_saved(self):
        await database_sync_to_async(Room.objects.create)(name="other")
        async with self.joined(self.alice) as a, self.joined(self.bob) as b:
            async with self.joined(self.alice, room="other") as elsewhere:
                await drain(a), await drain(b), await drain(elsewhere)

                await a.send_json_to({"type": "message", "content": "  hello bob  "})

                for client in (a, b):  # sender and the other member both get it
                    event = await receive_until(client, "message")
                    self.assertEqual(event["message"]["username"], "alice")
                    self.assertEqual(event["message"]["content"], "hello bob")

                # a different room hears nothing
                self.assertTrue(await elsewhere.receive_nothing(timeout=0.3))

        saved = await database_sync_to_async(list)(Message.objects.values_list("content", flat=True))
        self.assertEqual(saved, ["hello bob"])

    async def test_last_50_messages_load_on_connect_oldest_first(self):
        await database_sync_to_async(Message.objects.bulk_create)(
            [Message(room=self.room, user=self.bob, content=f"msg {i}") for i in range(60)]
        )
        async with self.joined(self.alice) as client:
            history = await client.receive_json_from()
        self.assertEqual(history["type"], "history")
        contents = [m["content"] for m in history["messages"]]
        self.assertEqual(len(contents), 50)
        self.assertEqual(contents[0], "msg 10")
        self.assertEqual(contents[-1], "msg 59")

    async def test_presence_updates_when_users_join_and_leave(self):
        async with self.joined(self.alice) as a:
            self.assertEqual((await receive_until(a, "presence"))["users"], ["alice"])

            async with self.joined(self.bob):
                self.assertEqual((await receive_until(a, "presence"))["users"], ["alice", "bob"])

            # bob's connection closed when the inner block ended
            self.assertEqual((await receive_until(a, "presence"))["users"], ["alice"])

    async def test_typing_indicator_reaches_others_but_not_the_typist(self):
        async with self.joined(self.alice) as a, self.joined(self.bob) as b:
            await drain(a), await drain(b)

            await a.send_json_to({"type": "typing", "is_typing": True})

            event = await b.receive_json_from()
            self.assertEqual(event, {"type": "typing", "username": "alice", "is_typing": True})
            self.assertFalse([e for e in await collect(a) if e["type"] == "typing"])

            await a.send_json_to({"type": "typing", "is_typing": False})
            event = await b.receive_json_from()
            self.assertFalse(event["is_typing"])

    async def test_empty_and_oversized_messages_get_error_events(self):
        async with self.joined(self.alice) as client:
            await drain(client)

            await client.send_json_to({"type": "message", "content": "   "})
            self.assertEqual((await client.receive_json_from())["code"], "empty_message")

            await client.send_json_to({"type": "message", "content": "x" * 1001})
            self.assertEqual((await client.receive_json_from())["code"], "message_too_long")

        self.assertEqual(await database_sync_to_async(Message.objects.count)(), 0)

    async def test_announcement_signal_broadcasts_to_every_room(self):
        await database_sync_to_async(Room.objects.create)(name="general")
        async with self.joined(self.alice, room="lobby") as a:
            async with self.joined(self.bob, room="general") as b:
                await drain(a), await drain(b)

                # Created like the admin does: a plain model save fires post_save.
                await database_sync_to_async(Announcement.objects.create)(
                    title="Maintenance", body="Back in 10 minutes."
                )

                for client in (a, b):
                    event = await receive_until(client, "announcement")
                    self.assertEqual(event["title"], "Maintenance")
                    self.assertEqual(event["body"], "Back in 10 minutes.")
