from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def backfill_enrollments(apps, schema_editor):
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    StoryProgress = apps.get_model('pabasa_app', 'StoryReadingProgress')
    Practice = apps.get_model('pabasa_app', 'Practice')

    for row in Assessment.objects.filter(student__isnull=False, section__isnull=False, enrollment__isnull=True).select_related('section'):
        matches = Enrollment.objects.filter(
            student_id=row.student_id,
            section_id=row.section_id,
            school_calendar_id=row.section.school_calendar_id,
        )
        if matches.count() == 1:
            row.enrollment_id = matches.first().id
            row.save(update_fields=['enrollment'])

    for practice in Practice.objects.filter(section__isnull=False).select_related('section'):
        attempts = practice.attempts if isinstance(practice.attempts, list) else []
        changed = False
        for attempt in attempts:
            if attempt.get('enrollment_id') or not attempt.get('student_id'):
                continue
            matches = Enrollment.objects.filter(
                student_id=attempt['student_id'], section_id=practice.section_id,
                school_calendar_id=practice.section.school_calendar_id,
            )
            if matches.count() == 1:
                attempt['enrollment_id'] = matches.first().id
                changed = True
        if changed:
            practice.save(update_fields=['attempts', 'updated_at'])

    for row in StoryProgress.objects.filter(enrollment__isnull=True).select_related('material'):
        section_id = getattr(row.material, 'section_id', None)
        if not section_id:
            continue
        section = row.material.section
        matches = Enrollment.objects.filter(
            student_id=row.student_id,
            section_id=section_id,
            school_calendar_id=section.school_calendar_id,
        )
        if matches.count() == 1:
            row.enrollment_id = matches.first().id
            row.save(update_fields=['enrollment'])


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0091_enrollment_integrity')]
    operations = [
        migrations.AddField(
            model_name='assessment', name='enrollment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessment_attempts', to='pabasa_app.enrollment'),
        ),
        migrations.AddField(
            model_name='storyreadingprogress', name='enrollment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='story_reading_progress', to='pabasa_app.enrollment'),
        ),
        migrations.RunPython(backfill_enrollments, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name='storyreadingprogress', name='unique_story_reading_progress'),
        migrations.AddConstraint(
            model_name='storyreadingprogress',
            constraint=models.UniqueConstraint(condition=Q(enrollment__isnull=True), fields=['student', 'material'], name='unique_legacy_story_reading_progress'),
        ),
        migrations.AddConstraint(
            model_name='storyreadingprogress',
            constraint=models.UniqueConstraint(condition=Q(enrollment__isnull=False), fields=['enrollment', 'material'], name='unique_enrollment_story_reading_progress'),
        ),
    ]
