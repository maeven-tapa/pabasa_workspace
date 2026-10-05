"""Verify session cleanup on a disposable copy, leaving the source DB untouched."""
from contextlib import closing, redirect_stdout, ExitStack
from datetime import timedelta
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'pabasa_site'
REMOVED = {
    'users': {'last_activity', 'active_session_last_seen', 'active_session_learning'},
    'live_assessment_sessions': {'timing_mode', 'duration_seconds'},
    'django_session': {'session_data', 'expire_date'},
}


def fingerprint(database):
    result = {}
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations'"
        )]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = [row[1] for row in db.execute('PRAGMA table_info(' + quoted + ')')
                       if row[1] not in REMOVED.get(table, set())]
            selection = ','.join('"' + column.replace('"', '""') + '"' for column in columns)
            rows = sorted(repr(row) for row in db.execute('SELECT ' + selection + ' FROM ' + quoted))
            result[table] = (len(rows), hashlib.sha256('\n'.join(rows).encode()).hexdigest())
    return result


def main():
    source = (PROJECT / 'db.sqlite3').resolve()
    before = fingerprint(source)
    with tempfile.TemporaryDirectory(prefix='pabasa-session-cleanup-') as directory, ExitStack() as cleanup:
        target = Path(directory) / 'verify.sqlite3'
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(target)) as copy:
                original.backup(copy)
        sys.path.insert(0, str(PROJECT))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
        from django.conf import settings
        settings.DATABASES['default']['NAME'] = str(target)
        import django
        django.setup()
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from django.utils import timezone
        cleanup.callback(connection.close)

        # Reconstruct the preceding schema on this copy if cleanup is already
        # applied locally, so repeated checks still exercise the upgrade.
        executor = MigrationExecutor(connection)
        with redirect_stdout(io.StringIO()):
            executor.migrate([('pabasa_app', '0023_supplementary_student_assignment')])

        store = SessionStore()
        for payload, seconds in (
            ({'user_id': 1, 'user_role': 'student', 'session_timeouts_disabled': False}, 60),
            ({'_auth_user_id': '1', 'session_timeouts_disabled': True}, 60),
            ({'user_id': 1, 'user_role': 'teacher'}, 0),
            ({'user_id': 1, 'session_timeouts_disabled': False}, -60),
            ({'session_timeouts_disabled': False}, 60),
        ):
            login = SessionStore()
            login.update(payload)
            login.set_expiry(seconds)
            login.save()
        copy_before = fingerprint(target)
        with connection.cursor() as cursor:
            cursor.execute('SELECT session_key, session_data, expire_date FROM django_session')
            previous_logins = {key: (store.decode(data), expiry) for key, data, expiry in cursor.fetchall()}
        executor = MigrationExecutor(connection)
        now = timezone.now()
        with redirect_stdout(io.StringIO()):
            executor.migrate([('pabasa_app', '0024_remove_session_timeout_fields')])
        after = fingerprint(target)
        assert all(after[table] == digest for table, digest in copy_before.items()), 'Existing records changed'
        with connection.cursor() as cursor:
            for table, removed in REMOVED.items():
                if table == 'django_session':
                    continue
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
                assert not columns & removed, 'Obsolete columns remain'
            cursor.execute('SELECT session_key, session_data, expire_date FROM django_session')
            current_logins = {key: (store.decode(data), expiry) for key, data, expiry in cursor.fetchall()}
            assert previous_logins.keys() == current_logins.keys(), 'Login records lost'
            for key, (old_payload, old_expiry) in previous_logins.items():
                payload, expiry = current_logins[key]
                expected = dict(old_payload)
                expected.pop('session_timeouts_disabled', None)
                if old_expiry > now.replace(tzinfo=None) and (expected.get('user_id') or expected.get('_auth_user_id')):
                    expected['_session_expiry'] = settings.SESSION_COOKIE_AGE
                    assert expiry > now.replace(tzinfo=None) + timedelta(days=99 * 365)
                else:
                    assert expiry == old_expiry
                assert payload == expected, 'Login payload changed unexpectedly'
            cursor.execute('PRAGMA integrity_check')
            assert cursor.fetchall() == [('ok',)]
            cursor.execute('PRAGMA foreign_key_check')
            assert not cursor.fetchall()
        connection.close()
    assert fingerprint(source) == before, 'Source database changed'
    print(f'PASS: all {len(before)} existing tables preserve records; obsolete columns removed; login payloads preserved.')
    print('PASS: SQLite integrity and foreign keys; source database untouched.')
    print('PASS: legacy, browser-close, admin, anonymous and revoked login migration cases.')


if __name__ == '__main__':
    main()
