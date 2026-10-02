from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0016_default_prescribed_activity_access_unlocked')]

    operations = [
        migrations.AddField(
            model_name='studentactivityrecordingsubmission',
            name='teacher_score',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(1)],
            ),
        ),
        migrations.AddConstraint(
            model_name='studentactivityrecordingsubmission',
            constraint=models.CheckConstraint(
                condition=models.Q(teacher_score__isnull=True) | models.Q(teacher_score__in=[0, 1]),
                name='teacher_score_zero_or_one',
            ),
        ),
    ]
