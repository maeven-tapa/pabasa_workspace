from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0007_alter_accountstatushistory_id_alter_activitylog_id_and_more')]
    operations = [migrations.CreateModel(
        name='StudentActivityRecordingSubmission',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('activity_key', models.CharField(max_length=100)),
            ('audio_file', models.FileField(upload_to='activity_recordings/%Y/%m/%d/')),
            ('duration_seconds', models.PositiveIntegerField(blank=True, null=True)),
            ('status', models.CharField(choices=[('submitted', 'Submitted'), ('retry', 'Retry Requested'), ('checked', 'Checked')], default='submitted', max_length=20)),
            ('submitted_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_recording_submissions', to='pabasa_app.user')),
            ('checked_at', models.DateTimeField(blank=True, null=True)),
            ('checked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='checked_activity_recordings', to='pabasa_app.user')),
        ],
        options={'db_table': 'student_activity_recording_submissions', 'constraints': [models.UniqueConstraint(fields=('student', 'activity_key'), name='unique_student_activity_recording')]},
    )]
