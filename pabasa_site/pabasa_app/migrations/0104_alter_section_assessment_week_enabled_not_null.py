from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0103_merge_20260904_1005')]

    operations = [
        # Set all remaining NULL values to False (shouldn't be any after 0100, but belt and suspenders)
        migrations.RunSQL(
            "UPDATE sections SET assessment_week_enabled = 0 WHERE assessment_week_enabled IS NULL",
            reverse_sql="UPDATE sections SET assessment_week_enabled = NULL WHERE assessment_week_enabled = 0",
        ),
        # ALTER the field to NOT NULL and set DEFAULT 0
        migrations.AlterField(
            model_name='section',
            name='assessment_week_enabled',
            field=models.BooleanField(default=False, null=False),
        ),
    ]
