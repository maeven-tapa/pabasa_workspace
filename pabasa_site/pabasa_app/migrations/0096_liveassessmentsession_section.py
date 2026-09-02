from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0095_merge_0094_section_assessment_week_enabled_0094_teacher_aral_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='liveassessmentsession',
            name='section',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='live_assessment_sessions',
                to='pabasa_app.section',
            ),
        ),
    ]