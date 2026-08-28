from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0084_classify_legacy_practice"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoryReadingProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("story_title", models.CharField(blank=True, default="", max_length=150)),
                ("total_words", models.PositiveIntegerField(default=0)),
                ("words_read", models.PositiveIntegerField(default=0)),
                ("progress_percent", models.FloatField(default=0)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_reading_progress", to="pabasa_app.material")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_reading_progress", to="pabasa_app.user")),
            ],
            options={
                "db_table": "story_reading_progress",
                "constraints": [
                    models.UniqueConstraint(fields=("student", "material"), name="unique_story_reading_progress"),
                ],
            },
        ),
    ]