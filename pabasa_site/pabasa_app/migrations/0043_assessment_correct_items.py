from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0042_liveassessmentsession_activity_log_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="correct_items",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
