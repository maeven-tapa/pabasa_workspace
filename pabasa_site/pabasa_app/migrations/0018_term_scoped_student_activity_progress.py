from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0017_studentactivityrecordingsubmission_teacher_score')]

    operations = [
        migrations.RemoveConstraint(
            model_name='studentactivityprogress',
            name='unique_student_activity_progress',
        ),
        migrations.AddField(
            model_name='studentactivityprogress',
            name='school_calendar',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='activity_progress',
                to='pabasa_app.schoolcalendar',
            ),
        ),
        migrations.AddField(
            model_name='studentactivityprogress',
            name='term',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3'), (4, 'Term 4')],
            ),
        ),
        migrations.AddConstraint(
            model_name='studentactivityprogress',
            constraint=models.UniqueConstraint(
                condition=models.Q(school_calendar__isnull=False, term__isnull=False),
                fields=('student', 'school_calendar', 'term', 'activity_key'),
                name='unique_student_calendar_term_activity_progress',
            ),
        ),
    ]
