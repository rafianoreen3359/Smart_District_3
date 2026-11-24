import csv
import json

from django.core.management.base import BaseCommand, CommandError

from library.models import Book

FIELDS = ["title", "author", "isbn", "published_date", "price"]


class Command(BaseCommand):
    help = "Export all books to a CSV or JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--format", default="csv", help="csv or json (default: csv)")
        parser.add_argument("--output", help="Output file (default: books.<format>)")

    def handle(self, *args, **options):
        fmt = options["format"].lower()
        if fmt not in ("csv", "json"):
            raise CommandError(f"Invalid format '{fmt}'. Use 'csv' or 'json'.")

        path = options["output"] or f"books.{fmt}"
        rows = [
            {
                "title": b.title,
                "author": b.author.name,
                "isbn": b.isbn,
                "published_date": b.published_date.isoformat() if b.published_date else "",
                "price": str(b.price),
            }
            for b in Book.objects.select_related("author").order_by("id")
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                if fmt == "csv":
                    writer = csv.DictWriter(f, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    json.dump(rows, f, indent=2)
        except OSError as exc:
            raise CommandError(f"Cannot write '{path}': {exc}")

        self.stdout.write(self.style.SUCCESS(f"Exported {len(rows)} books to {path}"))
