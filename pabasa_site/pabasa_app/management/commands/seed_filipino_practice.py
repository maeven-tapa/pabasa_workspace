import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from pabasa_app.models import Material


SEED_PATH = Path(__file__).resolve().parents[1] / "filipino_grade_2_practice.json"


class Command(BaseCommand):
    help = "Add or refresh only the Filipino Grade 2 practice curriculum."

    @transaction.atomic
    def handle(self, *args, **options):
        records = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        created_count = 0
        updated_count = 0

        for record in records:
            content_json = record["content_json"]
            lookup = {
                "type": "practice",
                "language": "Filipino",
                "content_json__mode": content_json["mode"],
                "content_json__difficulty": content_json["difficulty"],
                "content_json__level": content_json["level"],
            }
            defaults = {
                "title": record["title"],
                "item_type": record["item_type"],
                "prompt_text": record["prompt_text"],
                "content_text": record["content_text"],
                "content_json": content_json,
                "difficulty_level": record["difficulty_level"],
                "source_type": "shared",
                "status": "published",
                "student_access": True,
                "is_active": True,
            }
            _material, created = Material.objects.update_or_create(
                **lookup,
                defaults=defaults,
            )
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Filipino practice seed complete: {created_count} created, "
                f"{updated_count} updated. English practice content was not queried or changed."
            )
        )
