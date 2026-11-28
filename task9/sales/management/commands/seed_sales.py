import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from sales.models import REGIONS, Sale

PRODUCTS = [
    ("TR-100", "Trailhead Daypack 22L", "64.00"), ("TR-200", "Summit Shell Jacket", "189.00"),
    ("HM-310", "Harbor Merino Crew", "78.00"), ("HM-320", "Harbor Wool Beanie", "29.00"),
    ("KT-410", "Cast-Iron Skillet 12in", "54.00"), ("KT-420", "Pour-Over Kettle", "62.00"),
    ("CP-510", "Basecamp Tent 2P", "249.00"), ("CP-520", "Down Sleeping Bag", "219.00"),
    ("OF-610", "Oak Standing Desk", "529.00"), ("OF-620", "Ergo Desk Chair", "389.00"),
    ("AC-710", "Insulated Bottle 1L", "34.00"), ("AC-720", "Trail Headlamp", "39.00"),
]


class Command(BaseCommand):
    help = "Create sample sales rows for the report generator"

    def add_arguments(self, parser):
        parser.add_argument("--rows", type=int, default=6000)

    def handle(self, *args, **opts):
        rnd = random.Random(42)
        today = date.today()
        Sale.objects.all().delete()
        rows = []
        for _ in range(opts["rows"]):
            sku, name, price = rnd.choice(PRODUCTS)
            rows.append(Sale(
                sku=sku, product_name=name, region=rnd.choice(REGIONS)[0], units=rnd.randint(1, 9),
                unit_price=Decimal(price), sold_at=today - timedelta(days=rnd.randint(0, 540))))
        Sale.objects.bulk_create(rows, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Created {len(rows)} sales"))
