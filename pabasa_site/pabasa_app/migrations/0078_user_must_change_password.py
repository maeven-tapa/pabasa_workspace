from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0077_backfill_principal_school_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
    ]
