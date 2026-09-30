from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0012_material_publication_scope_and_assignments')]

    operations = [
        migrations.AddField(
            model_name='studentactivityrecordingsubmission',
            name='item_index',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name='studentactivityrecordingsubmission',
            name='unique_student_activity_recording',
        ),
        migrations.AddConstraint(
            model_name='studentactivityrecordingsubmission',
            constraint=models.UniqueConstraint(
                fields=('student', 'activity_key'),
                condition=Q(item_index__isnull=True),
                name='unique_student_activity_recording',
            ),
        ),
        migrations.AddConstraint(
            model_name='studentactivityrecordingsubmission',
            constraint=models.UniqueConstraint(
                fields=('student', 'activity_key', 'item_index'),
                condition=Q(item_index__isnull=False),
                name='unique_itemized_activity_recording',
            ),
        ),
    ]
