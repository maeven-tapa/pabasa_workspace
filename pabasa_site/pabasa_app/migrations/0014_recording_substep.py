from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0013_itemized_activity_recordings')]

    operations = [
        migrations.AddField(
            model_name='studentactivityrecordingsubmission',
            name='substep',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name='studentactivityrecordingsubmission',
            name='unique_itemized_activity_recording',
        ),
        migrations.AddConstraint(
            model_name='studentactivityrecordingsubmission',
            constraint=models.UniqueConstraint(
                fields=('student', 'activity_key', 'item_index'),
                condition=Q(item_index__isnull=False, substep__isnull=True),
                name='unique_itemized_activity_recording',
            ),
        ),
        migrations.AddConstraint(
            model_name='studentactivityrecordingsubmission',
            constraint=models.UniqueConstraint(
                fields=('student', 'activity_key', 'item_index', 'substep'),
                condition=Q(item_index__isnull=False, substep__isnull=False),
                name='unique_staged_activity_recording',
            ),
        ),
    ]
