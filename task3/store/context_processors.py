from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils.functional import SimpleLazyObject

from .models import Notification

CACHE_SECONDS = 60


def unread_cache_key(user_id):
    return f"unread_notifications:{user_id}"


def site_settings(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "CURRENT_YEAR": date.today().year,
    }


def cart_summary(request):
    session = getattr(request, "session", {})
    cart = session.get("cart", {})
    count = sum(item["qty"] for item in cart.values())
    total = sum(
        (Decimal(item["price"]) * item["qty"] for item in cart.values()),
        Decimal("0.00"),
    )
    return {"cart_count": count, "cart_total": total}


def _unread_count(request):
    user = request.user
    if not user.is_authenticated:
        return 0
    return cache.get_or_set(
        unread_cache_key(user.pk),
        lambda: Notification.objects.filter(user=user, is_read=False).count(),
        CACHE_SECONDS,
    )


def notifications(request):
    return {"unread_notifications": SimpleLazyObject(lambda: _unread_count(request))}
