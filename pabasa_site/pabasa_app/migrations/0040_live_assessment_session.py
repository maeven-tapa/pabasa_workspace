from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0039_hunt_star_award'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveAssessmentSession',
            fields=[
                ('id', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('student_ids', models.JSONField(default=list, blank=True)),
                ('student_count', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('waiting', 'Waiting'), ('started', 'Started'), ('ended', 'Ended'), ('cancelled', 'Cancelled')], default='waiting', max_length=20)),
                ('start_at', models.DateTimeField(blank=True, null=True)),
                ('countdown_seconds', models.IntegerField(default=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='live_assessment_sessions', to='pabasa_app.course')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_assessment_sessions', to='pabasa_app.material')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_assessment_sessions', to='pabasa_app.user')),
            ],
            options={'db_table': 'live_assessment_sessions', 'ordering': ['-created_at']},
        ),
    ]
