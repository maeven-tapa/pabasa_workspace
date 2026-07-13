from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0038_normalize_material_language_to_filipino")]
    operations = [
        migrations.CreateModel(
            name="HuntStarAward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_id", models.CharField(max_length=64)),
                ("award_key", models.CharField(max_length=32)),
                ("word_index", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("tier", models.CharField(blank=True, max_length=16)),
                ("stars", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hunt_star_awards", to="pabasa_app.material")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hunt_star_awards", to="pabasa_app.user")),
            ],
            options={"db_table": "hunt_star_awards"},
        ),
        migrations.AddConstraint(
            model_name="huntstaraward",
            constraint=models.UniqueConstraint(fields=("student", "material", "attempt_id", "award_key"), name="unique_hunt_attempt_award"),
        ),
    ]
