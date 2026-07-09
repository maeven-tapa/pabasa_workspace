import pabasa_app.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0035_material_code_teacher_assessment_material"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="available_stars",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="theme_stars_credited",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="unlocked_themes",
            field=models.JSONField(blank=True, default=pabasa_app.models.default_unlocked_themes),
        ),
        migrations.AddField(
            model_name="user",
            name="equipped_theme",
            field=models.CharField(default="sky", max_length=30),
        ),
    ]
