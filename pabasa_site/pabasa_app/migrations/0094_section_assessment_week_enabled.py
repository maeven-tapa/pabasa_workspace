from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0093_seed_salawag_grade_two_sections")]

    operations = [
        migrations.AddField(
            model_name="section",
            name="assessment_week_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
