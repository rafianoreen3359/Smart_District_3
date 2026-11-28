"""ASGI entrypoint: HTTP goes to Django, WebSockets go to Channels routing."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django before importing anything that touches models/settings.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from realtime.routing import websocket_urlpatterns as realtime_ws  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Origin check first, then session auth so consumers see scope["user"].
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(realtime_ws + chat_ws))
        ),
    }
)
