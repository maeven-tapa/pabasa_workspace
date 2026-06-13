from django.contrib.auth.hashers import make_password
from django.db import migrations, models


ADMIN_CUSTOM_ID = "ADM-0001"
ADMIN_PASSWORD = "PBSADM1@2026"


def create_admin_account(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    admin_defaults = {
        "role": "admin",
        "first_name": "PABASA",
        "last_name": "Admin",
        "middle_initial": "",
        "suffix": "",
        "sex": "N/A",
        "birth_month": 1,
        "birth_day": 1,
        "birth_year": 2026,
        "email": "admin@pabasa.local",
        "contact_no": "",
        "password_hash": make_password(ADMIN_PASSWORD),
    }

    admin_user, created = User.objects.get_or_create(
        custom_id=ADMIN_CUSTOM_ID,
        defaults=admin_defaults,
    )
    if not created:
        for field, value in admin_defaults.items():
            setattr(admin_user, field, value)
        admin_user.save()


def remove_admin_account(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    User.objects.filter(custom_id=ADMIN_CUSTOM_ID, role="admin").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0014_alter_material_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("teacher", "Teacher"),
                    ("student", "Student"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(create_admin_account, remove_admin_account),
    ]
