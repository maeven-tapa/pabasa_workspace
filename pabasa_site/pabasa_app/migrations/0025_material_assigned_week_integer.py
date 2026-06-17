import re

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def _parse_week_from_legacy(raw):
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value.lower() in {"unassigned", "none", "null"}:
        return None
    match = re.match(r"^(?:week\s*)?(\d{1,2})$", value, re.IGNORECASE)
    if not match:
        return None
    week = int(match.group(1))
    if 1 <= week <= 99:
        return week
    return None


def populate_assigned_week_integer(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    for material in Material.objects.all().iterator():
        week = _parse_week_from_legacy(material.assigned_week)
        Material.objects.filter(pk=material.pk).update(assigned_week_integer=week)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0024_update_default_test_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="assigned_week_integer",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(99)],
            ),
        ),
        migrations.RunPython(
            populate_assigned_week_integer,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="material",
            name="assigned_week",
        ),
        migrations.RenameField(
            model_name="material",
            old_name="assigned_week_integer",
            new_name="assigned_week",
        ),
    ]
