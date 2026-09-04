from django.db import migrations, models


def backfill_assessment_week_enabled(apps, schema_editor):
    """Ensure all Section records have assessment_week_enabled set to False (not NULL or True).
    
    The Assessment Week feature should start OFF by default for all existing and new sections.
    This backfill handles three cases:
    1. NULL values (from the initial migration) → False
    2. True values (manually set or from old logic) → False  
    3. False values (correct) → no change
    """
    Section = apps.get_model('pabasa_app', 'Section')
    # Update all non-False values to False
    # This includes NULL and True values
    Section.objects.exclude(assessment_week_enabled=False).update(assessment_week_enabled=False)


def reverse_backfill(apps, schema_editor):
    """No need to reverse this as we're just ensuring a sensible default."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('pabasa_app', '0099_liveassessmentsession_batches'),
    ]

    operations = [
        migrations.RunPython(backfill_assessment_week_enabled, reverse_backfill),
    ]
