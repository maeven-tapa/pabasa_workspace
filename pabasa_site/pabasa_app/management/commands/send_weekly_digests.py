from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from pabasa_app.weekly_digest import send_weekly_digests


def _parse_bound(value, option_name):
    if not value:
        return None
    parsed = parse_datetime(value)
    if not parsed:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{option_name} must be an ISO date or datetime.") from exc
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class Command(BaseCommand):
    help = "Send weekly PABASA digest emails to users who enabled Weekly Digest."

    def add_arguments(self, parser):
        parser.add_argument("--start", help="Inclusive window start as ISO date/datetime.")
        parser.add_argument("--end", help="Exclusive window end as ISO date/datetime.")
        parser.add_argument("--user-id", type=int, help="Limit sending to one user ID.")
        parser.add_argument("--dry-run", action="store_true", help="Build digests without sending or recording metadata.")
        parser.add_argument("--force", action="store_true", help="Send even if the same digest window was already recorded.")

    def handle(self, *args, **options):
        try:
            start = _parse_bound(options.get("start"), "--start")
            end = _parse_bound(options.get("end"), "--end")
        except ValueError as exc:
            raise SystemExit(str(exc))

        results = send_weekly_digests(
            start=start,
            end=end,
            user_id=options.get("user_id"),
            dry_run=options.get("dry_run", False),
            force=options.get("force", False),
        )

        sent_count = 0
        skipped_count = 0
        for result in results:
            if result.get("sent") or result.get("dry_run"):
                sent_count += 1
                status = "DRY RUN" if result.get("dry_run") else "SENT"
            else:
                skipped_count += 1
                status = f"SKIPPED: {result.get('skipped', 'unknown')}"
            self.stdout.write(f"{status} user_id={result['user_id']} email={result.get('email') or 'N/A'}")

        self.stdout.write(self.style.SUCCESS(
            f"Weekly digest complete. Processed={len(results)} sent_or_ready={sent_count} skipped={skipped_count}"
        ))
