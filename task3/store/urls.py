from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("cart/", views.cart_detail, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="add_to_cart"),
    path("cart/remove/<int:pk>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/read/", views.mark_all_read, name="mark_all_read"),
]
