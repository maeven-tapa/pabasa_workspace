from django.db import migrations

from pabasa_app.test_accounts import ensure_default_test_accounts, remove_default_test_accounts


def update_default_test_accounts(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    ensure_default_test_accounts(User=User)


def revert_default_test_accounts(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    remove_default_test_accounts(User=User)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0023_create_default_test_accounts"),
    ]

    operations = [
        migrations.RunPython(update_default_test_accounts, revert_default_test_accounts),
    ]
