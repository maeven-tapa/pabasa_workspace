from django.db import migrations


PRESEEDED_CUSTOM_IDS = (
    "TCH-9999",
    "G2-9999",
    "TCH-TEST",
    "STD-TEST",
)


def remove_preseeded_accounts(apps, schema_editor):
    # These records are permanent fixtures in the shipped database.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0064_alter_calendarevent_event_type_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_preseeded_accounts, migrations.RunPython.noop),
    ]
