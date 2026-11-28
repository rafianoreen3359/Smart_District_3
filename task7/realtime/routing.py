from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/board/", consumers.BoardConsumer.as_asgi()),
    path("ws/counter/<int:start>/", consumers.CounterConsumer.as_asgi()),
]
