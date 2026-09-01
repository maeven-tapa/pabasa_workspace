from django.db import migrations, models
from django.db.models import Count, Q


def refuse_ambiguous_current_enrollments(apps, schema_editor):
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    duplicates = Enrollment.objects.filter(
        school_calendar__isnull=False,
        status__in=['active', 'awaiting_assignment'],
    ).values('student_id', 'school_calendar_id').annotate(total=Count('id')).filter(total__gt=1)
    if duplicates.exists():
        details = list(duplicates.values_list('student_id', 'school_calendar_id', 'total'))
        raise RuntimeError(
            'Ambiguous current enrollments exist; run audit_enrollment_integrity and resolve them before migrating: '
            + repr(details)
        )


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0090_school_year_enrollment_and_account_status')]
    operations = [
        migrations.RunPython(refuse_ambiguous_current_enrollments, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='enrollment',
            constraint=models.UniqueConstraint(
                fields=['student', 'school_calendar'],
                condition=Q(school_calendar__isnull=False, status__in=['active', 'awaiting_assignment']),
                name='unique_current_student_school_year',
            ),
        ),
    ]
