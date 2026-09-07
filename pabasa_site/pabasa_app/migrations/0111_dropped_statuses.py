from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0110_classcrlafinalization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="account_status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("pending_archive", "Pending Archive"),
                    ("dropped", "Dropped"),
                    ("archived", "Archived"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="enrollment",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("completed", "Completed"),
                    ("awaiting_assignment", "Awaiting Assignment"),
                    ("dropped", "Dropped"),
                ],
                default="active",
                max_length=30,
            ),
        ),
    ]
