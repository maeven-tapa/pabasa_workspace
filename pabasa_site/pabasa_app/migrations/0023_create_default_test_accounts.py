from django.db import migrations

from pabasa_app.test_accounts import ensure_default_test_accounts, remove_default_test_accounts


def create_default_test_accounts(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    ensure_default_test_accounts(User=User)


def delete_default_test_accounts(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    remove_default_test_accounts(User=User)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0022_course_courseassessmentassignment"),
    ]

    operations = [
        migrations.RunPython(create_default_test_accounts, delete_default_test_accounts),
    ]
