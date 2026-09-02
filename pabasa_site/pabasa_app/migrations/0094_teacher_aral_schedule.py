from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MaxValueValidator, MinValueValidator


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0093_seed_salawag_grade_two_sections"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherAralSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.PositiveSmallIntegerField(choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")], validators=[MinValueValidator(0), MaxValueValidator(6)])),
                ("remark", models.CharField(max_length=200)),
                ("applies_to", models.CharField(choices=[("current", "Current Term"), ("all", "All Terms")], default="current", max_length=10)),
                ("term", models.PositiveSmallIntegerField(blank=True, choices=[(1, "Term 1"), (2, "Term 2"), (3, "Term 3"), (4, "Term 4")], null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school_calendar", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_aral_schedules", to="pabasa_app.schoolcalendar")),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_aral_schedules", to="pabasa_app.section")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aral_schedules", to="pabasa_app.user")),
            ],
            options={"db_table": "teacher_aral_schedules", "ordering": ["weekday", "section__class_name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="teacheraralschedule",
            constraint=models.CheckConstraint(
                condition=(models.Q(("applies_to", "all"), ("term__isnull", True)) | models.Q(("applies_to", "current"), ("term__isnull", False))),
                name="teacher_aral_schedule_term_matches_scope",
            ),
        ),
    ]