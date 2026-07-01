from collections import defaultdict
from datetime import datetime

from django.db import migrations, models
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(str(value))
    if parsed is not None:
        return parsed
    return None


def backfill_assessment_attempts(apps, schema_editor):
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    connection = schema_editor.connection

    if 'assessment_attempts' not in connection.introspection.table_names():
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                assessment_id,
                student_id,
                started_at,
                completed_at,
                status,
                device_info,
                mic_used,
                accuracy,
                wpm,
                fluency_score,
                pronunciation_score,
                time_score,
                total_score,
                crla_classification,
                classification,
                duration_seconds,
                word_count,
                transcript,
                speech_recognition_used,
                needs_manual_review,
                passed,
                remarks,
                updated_at
            FROM assessment_attempts
            ORDER BY started_at, id
            """
        )
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

    grouped_attempts = defaultdict(list)
    for row in rows:
        record = dict(zip(columns, row))
        assessment_id = record.get('assessment_id')
        student_id = record.get('student_id')
        if assessment_id is None or student_id is None:
            continue

        attempt = {
            'student_id': student_id,
            'started_at': _parse_datetime(record.get('started_at')) or timezone.now(),
            'completed_at': _parse_datetime(record.get('completed_at')),
            'status': record.get('status') or 'started',
            'device_info': record.get('device_info') or {},
            'mic_used': bool(record.get('mic_used', False)),
            'accuracy': record.get('accuracy'),
            'wpm': record.get('wpm'),
            'fluency_score': record.get('fluency_score'),
            'pronunciation_score': record.get('pronunciation_score'),
            'time_score': record.get('time_score'),
            'total_score': record.get('total_score'),
            'crla_classification': record.get('crla_classification') or '',
            'classification': record.get('classification') or '',
            'duration_seconds': record.get('duration_seconds'),
            'word_count': record.get('word_count'),
            'transcript': record.get('transcript') or '',
            'speech_recognition_used': bool(record.get('speech_recognition_used', False)),
            'needs_manual_review': bool(record.get('needs_manual_review', False)),
            'passed': bool(record.get('passed', False)),
            'remarks': record.get('remarks') or '',
        }
        grouped_attempts[assessment_id].append(attempt)

    for assessment in Assessment.objects.all().iterator():
        attempts = grouped_attempts.get(assessment.id, [])
        if not attempts:
            continue
        assessment.attempts = attempts
        assessment.save(update_fields=['attempts'])


def drop_legacy_assessment_attempt_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS assessment_attempts')


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0031_merge_20260701_1351'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessment',
            name='attempts',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_assessment_attempts, migrations.RunPython.noop),
        migrations.RunPython(drop_legacy_assessment_attempt_table, migrations.RunPython.noop),
    ]
