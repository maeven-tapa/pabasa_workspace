from django.db import migrations


PRESEEDED_CUSTOM_IDS = (
    "TCH-9999",
    "G2-9999",
    "TCH-TEST",
    "STD-TEST",
)


def remove_preseeded_accounts(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    User.objects.filter(custom_id__in=PRESEEDED_CUSTOM_IDS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0064_alter_calendarevent_event_type_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_preseeded_accounts, migrations.RunPython.noop),
    ]
