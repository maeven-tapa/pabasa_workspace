from django.core.management.base import BaseCommand

from pabasa_app.test_accounts import (
    DEFAULT_TEST_ACCOUNTS,
    ensure_default_test_accounts,
)


class Command(BaseCommand):
    help = "Ensure default teacher and student test accounts exist."

    def handle(self, *args, **options):
        results = ensure_default_test_accounts()
        for custom_id, created in results:
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created test account: {custom_id}"))
            else:
                self.stdout.write(f"Test account already exists: {custom_id}")

        self.stdout.write("")
        self.stdout.write("Default test credentials:")
        for account in DEFAULT_TEST_ACCOUNTS:
            self.stdout.write(
                f"  {account['custom_id']} / {account['password']} ({account['role']})"
            )
