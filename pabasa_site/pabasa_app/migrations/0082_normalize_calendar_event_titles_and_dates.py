from django.db import migrations, models


def normalize_calendar_events(apps, schema_editor):
    CalendarEvent = apps.get_model("pabasa_app", "CalendarEvent")

    legacy_global = CalendarEvent.objects.filter(
        scope="global",
        school__isnull=True,
    )
    legacy_global.filter(
        event_type="school_opening",
        title="School Opening",
    ).update(title="Opening Block")
    legacy_global.filter(
        event_type="school_closing",
        title="School Closing",
    ).update(title="End-of-Term Block")
    legacy_global.filter(
        event_type="school_closing",
        title="End-of-Term Block",
        end_date__lt=models.F("start_date"),
    ).update(end_date=models.F("start_date"))


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0081_alter_assessment_system_assessment_key_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_calendar_events, migrations.RunPython.noop),
    ]
