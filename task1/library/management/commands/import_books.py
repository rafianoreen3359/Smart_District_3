import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from library.models import Author, Book

REQUIRED = {"title", "author", "isbn"}


class Command(BaseCommand):
    help = "Import books from a CSV (columns: title, author, isbn, published_date, price)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the CSV file")

    def handle(self, *args, **options):
        path = options["csv_path"]
        created = updated = skipped = 0

        try:
            f = open(path, newline="", encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Cannot open '{path}': {exc}")

        with f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
                raise CommandError(
                    f"CSV must have columns: {', '.join(sorted(REQUIRED))}."
                )

            with transaction.atomic():
                for line_no, row in enumerate(reader, start=2):
                    title = (row.get("title") or "").strip()
                    author_name = (row.get("author") or "").strip()
                    isbn = (row.get("isbn") or "").strip()

                    if not (title and author_name and isbn):
                        self.stdout.write(self.style.WARNING(f"Line {line_no}: missing value, skipped"))
                        skipped += 1
                        continue

                    try:
                        price = Decimal((row.get("price") or "0").strip())
                        date_text = (row.get("published_date") or "").strip()
                        pub_date = (
                            datetime.strptime(date_text, "%Y-%m-%d").date() if date_text else None
                        )
                    except (InvalidOperation, ValueError):
                        self.stdout.write(self.style.WARNING(f"Line {line_no}: bad price/date, skipped"))
                        skipped += 1
                        continue

                    author, _ = Author.objects.get_or_create(name=author_name)
                    _, was_created = Book.objects.update_or_create(
                        isbn=isbn,
                        defaults={
                            "title": title,
                            "author": author,
                            "published_date": pub_date,
                            "price": price,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(self.style.SUCCESS(f"Created: {created}"))
        self.stdout.write(self.style.HTTP_INFO(f"Updated: {updated}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped}"))
