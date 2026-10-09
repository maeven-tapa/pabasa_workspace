from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0025_remove_student_device_lock')]

    operations = [
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='expected_text', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='recognized_transcript', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='stt_match', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='fluency_classification', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='classification_source', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='studentactivityrecordingsubmission', name='review_status', field=models.CharField(default='not_required', max_length=20)),
    ]
