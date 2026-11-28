import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Announcement, Room, room_group_name

logger = logging.getLogger(__name__)


def broadcast_announcement(announcement):
    """Send the announcement to the group of every room."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    event = {
        "type": "chat.announcement",  # handled by ChatConsumer.chat_announcement
        "title": announcement.title,
        "body": announcement.body,
        "created_at": announcement.created_at.isoformat(),
    }
    group_send = async_to_sync(channel_layer.group_send)
    for name in Room.objects.values_list("name", flat=True):
        group_send(room_group_name(name), event)


@receiver(post_save, sender=Announcement)
def announcement_created(sender, instance, created, **kwargs):
    if not created:
        return

    def send():
        try:
            broadcast_announcement(instance)
        except Exception:  # a Redis outage must not break saving in the admin
            logger.exception("Could not broadcast announcement %s", instance.pk)

    # Wait for the transaction to commit so consumers never see a rolled-back row.
    transaction.on_commit(send)
