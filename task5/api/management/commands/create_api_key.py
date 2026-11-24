from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from api.models import APIKey


class Command(BaseCommand):
    help = "Create an API key. The raw key is printed once and only its hash is stored."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="A label, e.g. 'Reporting service'")
        parser.add_argument("--owner", required=True, help="Email of the user the key belongs to")
        parser.add_argument("--scopes", default=APIKey.READ_SCOPE, help="Space-separated scopes")

    def handle(self, *args, **options):
        try:
            owner = User.objects.get(email__iexact=options["owner"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{options['owner']}'.")
        key, raw = APIKey.create_with_key(options["name"], owner, options["scopes"])
        self.stdout.write(self.style.SUCCESS(f"API key created: {key.name}"))
        self.stdout.write("Copy it now. It will never be shown again:")
        self.stdout.write(self.style.WARNING(raw))
        self.stdout.write(f"Use it with:  Authorization: Api-Key {raw}")
