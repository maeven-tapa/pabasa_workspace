"""Bounded authenticated load test; only temporary benchmark sessions are written.

Run locally to dispatch through the existing deployed-image diagnostic job.
Twenty virtual clients share the previously measured teacher and class. Session
keys and response bodies stay in memory and are never printed. All temporary
sessions are removed in finally and expire after ten minutes if interrupted.
"""
import base64
import concurrent.futures
import datetime as dt
import http.client
import json
import logging
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import uuid

CLIENT_COUNT = 20


def stats(rows):
    values = sorted(r['ms'] for r in rows)
    return {'samples': len(rows), 'mean_ms': statistics.mean(values),
            'median_ms': statistics.median(values),
            'p95_ms': values[math.ceil(len(values) * .95) - 1], 'max_ms': max(values),
            'failures': sum(not r['ok'] for r in rows),
            'statuses': {str(status): sum(r['status'] == status for r in rows)
                         for status in sorted({r['status'] for r in rows})}}


def run_test():
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.contrib.auth.models import AnonymousUser
    from django.db import connection, connections
    from django.test import RequestFactory
    from django.test.utils import CaptureQueriesContext
    from pabasa_app.models import Section, Enrollment
    from pabasa_app import views

    section = Section.objects.select_related('teacher').get(pk=6)
    teacher = section.teacher
    if not teacher or teacher.role != 'teacher' or teacher.is_archived:
        raise RuntimeError('Previously measured teacher is unavailable.')
    with connection.cursor() as cursor:
        cursor.execute("SELECT name, setting, unit FROM pg_settings WHERE name IN "
                       "('shared_buffers', 'max_connections', 'work_mem') ORDER BY name")
        database_settings = [dict(zip(('name', 'setting', 'unit'), row)) for row in cursor.fetchall()]
        cursor.execute('SELECT pg_database_size(current_database())')
        database_bytes = cursor.fetchone()[0]
    report = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'clients': CLIENT_COUNT, 'class_rows': Enrollment.objects.filter(section=section, status='active').count(),
              'scope': f'{CLIENT_COUNT} authenticated virtual clients sharing one existing teacher and class; GET requests only.',
              'user_agent': f'PABASA-authorized-{CLIENT_COUNT}-client-test',
              'database_settings': database_settings, 'database_bytes': database_bytes,
              'http_results': {}, 'internal_results': {}}
    specs = [('dashboard', '/dashboard/teacher/?section_id=6', views.dashboard_teacher),
             ('students', '/dashboard/teacher/students-api/?section_id=6', views.get_teacher_students_api),
             ('overview', '/dashboard/teacher/overview/?section_id=6', views.get_teacher_overview)]
    session_keys = []
    original_options = dict(settings.DATABASES['default'].get('OPTIONS', {}))
    try:
        for _ in range(CLIENT_COUNT):
            session = SessionStore()
            session['user_id'] = teacher.pk
            session['user_role'] = 'teacher'
            session['pabasa_benchmark'] = uuid.uuid4().hex
            session.set_expiry(600)
            session.save()
            session_keys.append(session.session_key)
        connections.close_all()

        # Match the prior internal test before exercising the public HTTP path.
        settings.DATABASES['default']['OPTIONS']['options'] = '-c default_transaction_read_only=on'
        factory = RequestFactory()
        def internal(spec):
            name, path, function = spec
            connection.close()
            request = factory.get(path, HTTP_HOST='tupcpabasa.app',
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest', secure=True)
            request.session = {'user_id': teacher.pk, 'user_role': 'teacher'}
            request.user = AnonymousUser()
            started = time.perf_counter()
            try:
                with CaptureQueriesContext(connection) as queries:
                    response = function(request)
                    content = response.content
                ok = response.status_code == 200
                if 'application/json' in response.get('Content-Type', ''):
                    ok = ok and json.loads(content).get('success') is True
                return {'ms': (time.perf_counter() - started) * 1000,
                        'status': response.status_code, 'ok': ok, 'queries': len(queries)}
            except Exception:
                return {'ms': (time.perf_counter() - started) * 1000,
                        'status': 0, 'ok': False, 'queries': 0}
            finally:
                connection.close()
        for spec in specs:
            internal(spec)
            with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
                rows = list(pool.map(internal, [spec] * (2 * CLIENT_COUNT)))
            report['internal_results'][spec[0]] = dict(stats(rows),
                mean_queries=statistics.mean(r['queries'] for r in rows))

        connections.close_all()
        settings.DATABASES['default']['OPTIONS'] = original_options
        barrier = threading.Barrier(CLIENT_COUNT)
        report['http_started_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        def virtual_user(session_key):
            client = http.client.HTTPSConnection('tupcpabasa.app', timeout=15)
            headers = {'Cookie': settings.SESSION_COOKIE_NAME + '=' + session_key,
                       'User-Agent': report['user_agent'],
                       'X-Requested-With': 'XMLHttpRequest'}
            rows = []
            try:
                for round_index in range(3):
                    barrier.wait(timeout=30)
                    for name, path, _ in specs:
                        started = time.perf_counter()
                        status, ok = 0, False
                        try:
                            client.request('GET', path, headers=headers)
                            response = client.getresponse()
                            body = response.read()
                            status = response.status
                            if name == 'dashboard':
                                ok = status == 200 and b'PABASA Dashboard' in body
                            else:
                                ok = status == 200 and json.loads(body).get('success') is True
                        except Exception:
                            client.close()
                            client = http.client.HTTPSConnection('tupcpabasa.app', timeout=15)
                        rows.append({'name': name, 'round': round_index + 1,
                                     'ms': (time.perf_counter() - started) * 1000,
                                     'status': status, 'ok': ok})
                    if round_index < 2:
                        time.sleep(5)
                return rows
            finally:
                client.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
            rows = [row for user_rows in pool.map(virtual_user, session_keys) for row in user_rows]
        report['http_finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        for name, _, _ in specs:
            endpoint_rows = [r for r in rows if r['name'] == name]
            report['http_results'][name] = dict(stats(endpoint_rows),
                by_round={str(i): stats([r for r in endpoint_rows if r['round'] == i]) for i in (1, 2, 3)})
        report['total_http_requests'] = len(rows)
        report['total_http_failures'] = sum(not r['ok'] for r in rows)
    finally:
        connections.close_all()
        settings.DATABASES['default']['OPTIONS'] = original_options
        # Delete only this execution's temporary sessions, using exact random keys.
        deleted, _ = Session.objects.filter(session_key__in=session_keys).delete()
        report['temporary_sessions_created'] = len(session_keys)
        report['temporary_sessions_deleted'] = deleted
        report['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    print('PABASA_TWENTY_USER_TEST ' + json.dumps(report), flush=True)


def dispatch():
    sdk = Path(r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk')
    source = base64.b64encode(Path(__file__).read_bytes()).decode()
    code = f"import base64;exec(base64.b64decode('{source}'))"
    result = subprocess.run([str(sdk / 'platform/bundledpython/python.exe'), str(sdk / 'lib/gcloud.py'),
                            'run', 'jobs', 'execute', 'pabasa-revision-check-01172',
                            '--project=project-2b0d295d-ee06-40a7-927', '--region=asia-southeast1',
                            '--task-timeout=300s', '--args=^~^-c~' + code,
                            '--wait', '--format=value(metadata.name)'], capture_output=True, text=True)
    if result.returncode:
        print(json.dumps({'status': 'failed', 'exit_code': result.returncode,
                          'details': 'Inspect diagnostic job logs for sanitized failure.'}))
    else:
        execution = result.stdout.strip()
        (Path(__file__).resolve().parents[1] / 'tmp/twenty-user-test-execution.txt').write_text(execution)
        print(json.dumps({'status': 'succeeded', 'execution': execution}))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    if os.environ.get('CLOUD_RUN_EXECUTION'):
        run_test()
    else:
        dispatch()
