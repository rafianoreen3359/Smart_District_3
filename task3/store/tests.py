from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .context_processor import cart_summary, notifications, site_settings
from .models import Notification, Product

User = get_user_model()


class SiteSettingsProcessorTests(SimpleTestCase):
    @override_settings(SITE_NAME="Rafia's Shop", SUPPORT_EMAIL="help@rafia'sshop.com")
    def test_values_come_from_settings(self):
        ctx = site_settings(RequestFactory().get("/"))
        self.assertEqual(ctx["SITE_NAME"], "Rafia's Shop")
        self.assertEqual(ctx["SUPPORT_EMAIL"], "help@rafia'sshop.com")
        self.assertEqual(ctx["CURRENT_YEAR"], date.today().year)


class CartSummaryProcessorTests(SimpleTestCase):
    def _request(self, session):
        request = RequestFactory().get("/")
        request.session = session
        request.user = AnonymousUser()  # anonymous user
        return request

    def test_empty_cart(self):
        ctx = cart_summary(self._request({}))
        self.assertEqual(ctx["cart_count"], 0)
        self.assertEqual(ctx["cart_total"], Decimal("0.00"))

    def test_cart_with_items(self):
        session = {"cart": {"1": {"qty": 2, "price": "5.50"}, "2": {"qty": 1, "price": "4.00"}}}
        ctx = cart_summary(self._request(session))
        self.assertEqual(ctx["cart_count"], 3)
        self.assertEqual(ctx["cart_total"], Decimal("15.00"))

    def test_request_without_session_does_not_crash(self):
        ctx = cart_summary(RequestFactory().get("/"))
        self.assertEqual(ctx["cart_count"], 0)


class NotificationsProcessorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("sam", password="pw")
        for i in range(3):
            Notification.objects.create(user=self.user, message=f"n{i}")
        Notification.objects.create(user=self.user, message="old", is_read=True)

    def _request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_anonymous_gets_zero(self):
        ctx = notifications(self._request(AnonymousUser()))
        self.assertEqual(ctx["unread_notifications"], 0)

    def test_is_lazy_no_query_until_used(self):
        request = self._request(self.user)
        with self.assertNumQueries(0):          # calling the processor costs nothing
            ctx = notifications(request)
        with self.assertNumQueries(1):          # query runs only when the value is used
            self.assertEqual(ctx["unread_notifications"], 3)

    def test_count_is_cached_for_60_seconds(self):
        request = self._request(self.user)
        self.assertEqual(notifications(request)["unread_notifications"], 3)  # fills cache
        Notification.objects.create(user=self.user, message="new")
        with self.assertNumQueries(0):          # served from cache
            self.assertEqual(notifications(request)["unread_notifications"], 3)
        cache.clear()
        self.assertEqual(notifications(request)["unread_notifications"], 4)


class PageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("sam", password="pw")
        Notification.objects.create(user=self.user, message="hi")
        self.mug = Product.objects.create(name="Mug", price=Decimal("7.50"))

    @override_settings(SITE_NAME="Cool Shop", SUPPORT_EMAIL="help@coolshop.com")
    def test_header_values_appear_without_view_passing_them(self):
        response = self.client.get(reverse("store:about"))
        self.assertContains(response, "Cool Shop")
        self.assertContains(response, "help@coolshop.com")
        self.assertContains(response, str(date.today().year))
        self.assertContains(response, "Cart: 0 items")

    def test_page_without_notifications_runs_no_queries(self):
        with self.assertNumQueries(0):
            self.client.get(reverse("store:about"))

    def test_logged_in_page_not_using_notifications_skips_notification_query(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("store:about"))
        self.assertFalse(any("store_notification" in q["sql"] for q in ctx.captured_queries))

    def test_page_using_notifications_shows_count(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("store:home"))
        self.assertContains(response, "Unread: 1")

    def test_cart_persists_in_session_for_anonymous_user(self):
        self.client.post(reverse("store:add_to_cart", args=[self.mug.pk]))
        self.client.post(reverse("store:add_to_cart", args=[self.mug.pk]))
        response = self.client.get(reverse("store:about"))
        self.assertContains(response, "Cart: 2 items, $15.00")

    def test_cart_page_lists_items_and_remove_works(self):
        self.client.post(reverse("store:add_to_cart", args=[self.mug.pk]))
        response = self.client.get(reverse("store:cart"))
        self.assertContains(response, "Mug")
        self.assertContains(response, "$7.50")
        self.client.post(reverse("store:remove_from_cart", args=[self.mug.pk]))
        self.assertContains(self.client.get(reverse("store:cart")), "Your cart is empty")

    def test_notifications_page_requires_login(self):
        response = self.client.get(reverse("store:notifications"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_mark_all_read_updates_badge(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("store:home")), "Unread: 1")
        self.client.post(reverse("store:mark_all_read"))
        self.assertContains(self.client.get(reverse("store:home")), "Unread: 0")
