import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

from library.models import Author, Book


class Command(BaseCommand):
    help = "Fill the database with fake authors and books."

    def add_arguments(self, parser):
        parser.add_argument("--authors", type=int, default=10, help="How many authors")
        parser.add_argument("--books", type=int, default=50, help="How many books")
        parser.add_argument("--clear", action="store_true", help="Delete existing data first")

    def handle(self, *args, **options):
        n_authors, n_books = options["authors"], options["books"]
        if n_authors < 0 or n_books < 0:
            raise CommandError("--authors and --books must be 0 or greater.")

        fake = Faker()

        with transaction.atomic():
            if options["clear"]:
                Book.objects.all().delete()
                Author.objects.all().delete()
                self.stdout.write(self.style.WARNING("Existing data cleared."))

            Author.objects.bulk_create(
                [Author(name=fake.name(), email=fake.email()) for _ in range(n_authors)]
            )

            author_ids = list(Author.objects.values_list("id", flat=True))
            if n_books and not author_ids:
                raise CommandError("Cannot create books: there are no authors.")

            Book.objects.bulk_create(
                [
                    Book(
                        title=fake.sentence(nb_words=4).rstrip("."),
                        author_id=random.choice(author_ids),
                        isbn=fake.unique.isbn13(separator=""),
                        published_date=fake.date_between(start_date="-30y", end_date="today"),
                        price=round(random.uniform(5, 80), 2),
                    )
                    for _ in range(n_books)
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(f"Created {n_authors} authors and {n_books} books.")
        )
