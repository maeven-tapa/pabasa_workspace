from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0062_update_official_crla_story_sets"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="assigned_weeks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="material",
            name="source_type",
            field=models.CharField(
                choices=[("personal", "Personal"), ("shared", "Shared"), ("template", "Template")],
                default="personal",
                max_length=20,
            ),
        ),
    ]
