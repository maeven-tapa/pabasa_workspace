from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.db import migrations
from django.utils import timezone


def persist_existing_logins(apps, schema_editor):
    sessions = apps.get_model('sessions', 'Session')
    alias = schema_editor.connection.alias
    store = SessionStore()
    now = timezone.now()
    lifetime = 100 * 365 * 24 * 60 * 60
    for session in sessions.objects.using(alias).all().iterator():
        payload = store.decode(session.session_data)
        logged_in = session.expire_date > now and (payload.get('user_id') or payload.get('_auth_user_id'))
        if not logged_in and 'session_timeouts_disabled' not in payload:
            continue
        payload.pop('session_timeouts_disabled', None)
        expiry = session.expire_date
        if logged_in:
            payload['_session_expiry'] = lifetime
            expiry = now + timedelta(seconds=lifetime)
        sessions.objects.using(alias).filter(pk=session.pk).update(
            session_data=store.encode(payload), expire_date=expiry,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('pabasa_app', '0023_supplementary_student_assignment'),
        ('sessions', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(model_name='user', name='active_session_last_seen'),
        migrations.RemoveField(model_name='user', name='active_session_learning'),
        migrations.RemoveField(model_name='user', name='last_activity'),
        migrations.RemoveField(model_name='liveassessmentsession', name='timing_mode'),
        migrations.RemoveField(model_name='liveassessmentsession', name='duration_seconds'),
        migrations.RunPython(persist_existing_logins, migrations.RunPython.noop),
    ]
