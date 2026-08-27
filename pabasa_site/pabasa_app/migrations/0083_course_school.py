from django.db import migrations, models
import django.db.models.deletion


def backfill_course_school(apps, schema_editor):
    Course = apps.get_model("pabasa_app", "Course")
    for course in Course.objects.select_related("teacher").prefetch_related("sections"):
        school_ids = {section.school_id for section in course.sections.all() if section.school_id}
        if len(school_ids) == 1:
            course.school_id = school_ids.pop()
            course.save(update_fields=["school"])
        elif not school_ids and course.teacher.school_record_id:
            course.school_id = course.teacher.school_record_id
            course.save(update_fields=["school"])


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0082_normalize_calendar_event_titles_and_dates")]

    operations = [
        migrations.AddField(
            model_name="course",
            name="school",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="courses",
                to="pabasa_app.school",
            ),
        ),
        migrations.RunPython(backfill_course_school, migrations.RunPython.noop),
    ]
