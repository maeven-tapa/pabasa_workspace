from django.db import migrations
from django.utils import timezone


def make_created_at_aware(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    tz = timezone.get_current_timezone()
    # Iterate safely - update only naive datetimes
    for m in Material.objects.exclude(created_at__isnull=True):
        ca = m.created_at
        try:
            if timezone.is_naive(ca):
                m.created_at = timezone.make_aware(ca, tz)
                m.save(update_fields=['created_at'])
        except Exception:
            # Best-effort: skip problematic rows
            continue


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0009_material_created_at_material_section_and_more'),
    ]

    operations = [
        migrations.RunPython(make_created_at_aware, reverse_code=migrations.RunPython.noop),
    ]
