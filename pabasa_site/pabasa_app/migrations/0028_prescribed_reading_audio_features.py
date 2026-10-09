from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0027_prescribed_reading_attempt')]
    operations = [
        migrations.AddField('prescribedreadingattempt', 'audio_features', models.JSONField(blank=True, null=True)),
        migrations.AddField('prescribedreadingattempt', 'audio_analysis_status', models.CharField(default='pending', max_length=32)),
        migrations.AddField('prescribedreadingattempt', 'audio_analysis_error', models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField('prescribedreadingattempt', 'audio_analysis_version', models.CharField(blank=True, default='', max_length=80)),
    ]
