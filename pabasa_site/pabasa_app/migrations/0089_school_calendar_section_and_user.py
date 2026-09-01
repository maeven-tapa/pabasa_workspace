from django.db import migrations, models
import django.db.models.deletion
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0088_storyreadingprogress_word_metrics"),
    ]

    operations = [
        migrations.AddField(
            model_name="section",
            name="school_calendar",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sections", to="pabasa_app.schoolcalendar"),
        ),
        migrations.AddField(
            model_name="user",
            name="school_calendar",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="users", to="pabasa_app.schoolcalendar"),
        ),
        migrations.RemoveConstraint(
            model_name="section",
            name="unique_school_canonical_grade_section",
        ),
        migrations.AddConstraint(
            model_name="section",
            constraint=models.UniqueConstraint(
                models.F("school"),
                models.F("school_calendar"),
                Lower("grade_level"),
                Lower("section"),
                condition=models.Q(("grade_level__gt", ""), ("section__gt", "")),
                name="unique_school_calendar_canonical_grade_section",
            ),
        ),
    ]
