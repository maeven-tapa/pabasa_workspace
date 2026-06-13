from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0015_add_admin_role_and_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
