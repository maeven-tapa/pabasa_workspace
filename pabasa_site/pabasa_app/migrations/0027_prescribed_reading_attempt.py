import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0026_reading_fluency_review')]

    operations = [
        migrations.CreateModel(
            name='PrescribedReadingAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('term', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3'), (4, 'Term 4')], null=True)),
                ('activity_key', models.CharField(max_length=100)),
                ('item_index', models.PositiveIntegerField()),
                ('attempt_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('attempt_number', models.PositiveIntegerField(default=1)),
                ('expected_text', models.TextField(blank=True, default='')),
                ('audio_file', models.FileField(upload_to='activity_recordings/%Y/%m/%d/')),
                ('audio_mime_type', models.CharField(blank=True, default='', max_length=100)),
                ('duration_seconds', models.FloatField(blank=True, null=True)),
                ('recognized_transcript', models.TextField(blank=True, default='')),
                ('stt_match', models.BooleanField(blank=True, null=True)),
                ('stt_provider', models.CharField(blank=True, default='', max_length=40)),
                ('stt_model', models.CharField(blank=True, default='', max_length=80)),
                ('stt_word_metadata', models.JSONField(blank=True, default=list)),
                ('classification', models.CharField(blank=True, default='', max_length=20)),
                ('classification_confidence', models.FloatField(blank=True, null=True)),
                ('classification_source', models.CharField(blank=True, default='', max_length=20)),
                ('review_status', models.CharField(default='not_required', max_length=20)),
                ('classifier_version', models.CharField(blank=True, default='', max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('school_calendar', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='pabasa_app.schoolcalendar')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prescribed_reading_attempts', to='pabasa_app.user')),
            ],
            options={'db_table': 'prescribed_reading_attempts', 'ordering': ['created_at', 'id']},
        ),
        migrations.AddConstraint(model_name='prescribedreadingattempt', constraint=models.UniqueConstraint(fields=('student', 'activity_key', 'item_index', 'attempt_number'), name='unique_prescribed_reading_attempt')),
    ]
