import json
from datetime import datetime, timezone

from channels.generic.websocket import AsyncJsonWebsocketConsumer

MAX_MESSAGE_LENGTH = 500


def now_iso() -> str:
    """Server timestamp in UTC, ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class BoardConsumer(AsyncJsonWebsocketConsumer):
    """Echoes every message back with a server timestamp.

    Client -> server:  {"text": "hello"}   (a bare non-JSON string is also accepted)
    Server -> client:  {"type": "echo", "text": "hello", "timestamp": "..."}
                       {"type": "error", "code": "message_too_long", ...}
    """

    async def connect(self):
        await self.accept()
        await self.send_json(
            {
                "type": "system",
                "text": "Connected to the board.",
                "max_length": MAX_MESSAGE_LENGTH,
                "timestamp": now_iso(),
            }
        )

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        # Overridden so malformed JSON becomes a JSON error event instead of
        # an unhandled exception that would drop the connection.
        if text_data is None:
            await self.send_error("unsupported_payload", "Binary frames are not supported.")
            return
        try:
            content = json.loads(text_data)
        except json.JSONDecodeError:
            content = text_data  # treat as plain text
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict):
            text = content.get("text")
        else:
            text = content

        if not isinstance(text, str):
            await self.send_error("invalid_message", 'Send {"text": "..."} with a string value.')
            return

        if len(text) > MAX_MESSAGE_LENGTH:
            await self.send_error(
                "message_too_long",
                f"Message is {len(text)} characters; the limit is {MAX_MESSAGE_LENGTH}.",
                max_length=MAX_MESSAGE_LENGTH,
                length=len(text),
            )
            return

        await self.send_json({"type": "echo", "text": text, "timestamp": now_iso()})

    async def send_error(self, code, detail, **extra):
        await self.send_json(
            {"type": "error", "code": code, "detail": detail, "timestamp": now_iso(), **extra}
        )


class CounterConsumer(AsyncJsonWebsocketConsumer):
    """Per-connection counter that starts at the integer in the URL.

    Client -> server:  {"action": "tick"}
    Server -> client:  {"type": "counter", "value": 8, "timestamp": "..."}
    """

    async def connect(self):
        self.value = self.scope["url_route"]["kwargs"]["start"]
        await self.accept()
        await self.send_json({"type": "ready", "value": self.value, "timestamp": now_iso()})

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None:
            await self.send_error("unsupported_payload", "Binary frames are not supported.")
            return
        try:
            content = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("invalid_json", "Payload must be valid JSON.")
            return
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        action = content.get("action") if isinstance(content, dict) else None
        if action == "tick":
            self.value += 1
            await self.send_json({"type": "counter", "value": self.value, "timestamp": now_iso()})
        else:
            await self.send_error("unknown_action", 'Send {"action": "tick"}.')

    async def send_error(self, code, detail, **extra):
        await self.send_json(
            {"type": "error", "code": code, "detail": detail, "timestamp": now_iso(), **extra}
        )
