from django.db import migrations

def update_default_test_accounts(apps, schema_editor):
    pass


def revert_default_test_accounts(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0023_create_default_test_accounts"),
    ]

    operations = [
        migrations.RunPython(update_default_test_accounts, revert_default_test_accounts),
    ]
