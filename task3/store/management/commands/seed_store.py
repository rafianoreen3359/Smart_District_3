from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from store.models import Notification, Product

PRODUCTS = [
    ("Ceramic Mug", "Hand-glazed 350 ml mug that keeps coffee warm.", "12.50"),
    ("Wireless Headphones", "Over-ear, 30 hour battery, deep bass.", "79.99"),
    ("Leather Notebook", "A5 notebook with 200 acid-free pages.", "18.00"),
    ("Desk Lamp", "Dimmable LED lamp with USB charging port.", "34.90"),
    ("Canvas Backpack", "Water-resistant, fits a 15 inch laptop.", "56.00"),
    ("Steel Water Bottle", "Insulated 750 ml bottle, cold for 24 hours.", "22.25"),
]


class Command(BaseCommand):
    help = "Create demo products plus a demo user (demo / demo12345) with notifications."

    def handle(self, *args, **options):
        for name, description, price in PRODUCTS:
            Product.objects.get_or_create(
                name=name, defaults={"description": description, "price": Decimal(price)}
            )
        user, created = get_user_model().objects.get_or_create(username="demo")
        if created:
            user.set_password("demo12345")
            user.save()
            for text in ["Welcome to the store!", "Your order has shipped.", "New arrivals this week."]:
                Notification.objects.create(user=user, message=text)
        self.stdout.write(self.style.SUCCESS("Demo data ready. Login: demo / demo12345"))
