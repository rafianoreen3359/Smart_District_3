from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .context_processor import unread_cache_key
from .models import Notification, Product


def home(request):
    return render(request, "store/home.html", {"products": Product.objects.all()})


def about(request):
    return render(request, "store/about.html")


def cart_detail(request):
    cart = request.session.get("cart", {})
    items = [
        {
            "pk": pk,
            "name": item.get("name", "Item"),
            "price": Decimal(item["price"]),
            "qty": item["qty"],
            "line_total": Decimal(item["price"]) * item["qty"],
        }
        for pk, item in cart.items()
    ]
    return render(request, "store/cart.html", {"items": items})


@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = request.session.setdefault("cart", {})
    item = cart.setdefault(str(pk), {"qty": 0, "price": str(product.price), "name": product.name})
    item["qty"] += 1
    request.session.modified = True
    messages.success(request, f"Added {product.name} to your cart.")
    return redirect("store:home")


@require_POST
def remove_from_cart(request, pk):
    cart = request.session.get("cart", {})
    if cart.pop(str(pk), None) is not None:
        request.session.modified = True
    return redirect("store:cart")


@require_POST
def clear_cart(request):
    request.session.pop("cart", None)
    return redirect("store:cart")


@login_required
def notification_list(request):
    return render(
        request,
        "store/notifications.html",
        {"notification_list": Notification.objects.filter(user=request.user)},
    )


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    cache.delete(unread_cache_key(request.user.pk))  # make the badge update at once
    return redirect("store:notifications")
