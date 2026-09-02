from django.db import migrations

def create_default_test_accounts(apps, schema_editor):
    # Retained only for migration graph compatibility. Testing accounts are
    # managed as ordinary database records now.
    pass


def delete_default_test_accounts(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0022_course_courseassessmentassignment"),
    ]

    operations = [
        migrations.RunPython(create_default_test_accounts, delete_default_test_accounts),
    ]
