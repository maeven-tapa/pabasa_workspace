"""Bounded 20-client GET benchmark; temporary sessions expire and are removed."""
import concurrent.futures
import datetime as dt
import http.client
import json
import logging
import math
import os
import statistics
import sys
import threading
import time
import uuid

CLIENT_COUNT = 20


def stats(rows):
    values = sorted(r['ms'] for r in rows)
    return {'samples': len(rows), 'mean_ms': statistics.mean(values),
            'median_ms': statistics.median(values),
            'p95_ms': values[math.ceil(len(values) * .95) - 1],
            'max_ms': max(values), 'failures': sum(not r['ok'] for r in rows),
            'statuses': {str(s): sum(r['status'] == s for r in rows)
                         for s in sorted({r['status'] for r in rows})}}


def run():
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.core.management import call_command
    from django.db import connection, connections
    from pabasa_app.models import Section, Enrollment
    call_command('migrate', check=True, verbosity=0)
    section = Section.objects.select_related('teacher').get(pk=6)
    teacher = section.teacher
    if not teacher or teacher.role != 'teacher' or teacher.is_archived:
        raise RuntimeError('Benchmark teacher is unavailable.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_database_size(current_database())')
        db_bytes = cursor.fetchone()[0]
        cursor.execute("SELECT name, setting, unit FROM pg_settings WHERE name IN ('shared_buffers','max_connections','work_mem') ORDER BY name")
        db_settings = [dict(zip(('name','setting','unit'), r)) for r in cursor.fetchall()]
    report = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'clients': CLIENT_COUNT, 'test_id': uuid.uuid4().hex[:12],
              'class_rows': Enrollment.objects.filter(section=section, status='active').count(),
              'database_bytes': db_bytes, 'database_settings': db_settings,
              'scope': f'{CLIENT_COUNT} separate temporary sessions sharing one existing teacher/class; public HTTPS GETs only.',
              'single_user': {}, 'concurrent': {}, 'rounds': [], 'aborted': False}
    specs = [('dashboard', '/dashboard/teacher/?section_id=6'),
             ('students', '/dashboard/teacher/students-api/?section_id=6'),
             ('overview', '/dashboard/teacher/overview/?section_id=6')]
    keys, rows = [], []
    clients = []
    report['user_agent'] = f'PABASA-authorized-{CLIENT_COUNT}-client-test-' + report['test_id']

    def request(index, spec, barrier=None):
        name, path = spec
        if barrier: barrier.wait(timeout=30)
        started = time.perf_counter()
        status, ok, error = 0, False, None
        try:
            clients[index].request('GET', path, headers={
                'Cookie': settings.SESSION_COOKIE_NAME + '=' + keys[index],
                'User-Agent': report['user_agent'], 'X-Requested-With': 'XMLHttpRequest'})
            response = clients[index].getresponse()
            body = response.read()
            status = response.status
            ok = status == 200 and (b'PABASA Dashboard' in body if name == 'dashboard'
                                   else json.loads(body).get('success') is True)
            if not ok: error = 'UnexpectedStatusOrContent'
        except Exception as exc:
            error = type(exc).__name__
            clients[index].close()
            clients[index] = http.client.HTTPSConnection('tupcpabasa.app', timeout=20)
        return {'name': name, 'ms': (time.perf_counter()-started)*1000,
                'status': status, 'ok': ok, 'error_type': error}
    try:
        for _ in range(CLIENT_COUNT):
            session = SessionStore()
            session['user_id'] = teacher.pk
            session['user_role'] = 'teacher'
            session['pabasa_benchmark'] = report['test_id']
            session.set_expiry(600)
            session.save()
            keys.append(session.session_key)
            clients.append(http.client.HTTPSConnection('tupcpabasa.app', timeout=20))
        connections.close_all()
        report['http_started_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        for spec in specs:
            baseline = [request(0, spec) for _ in range(3)]
            report['single_user'][spec[0]] = stats(baseline)
            if any(not r['ok'] for r in baseline):
                report['aborted'] = True
                report['abort_reason'] = 'Single-user authentication/content check failed.'
                break
        if not report['aborted']:
            with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
                for round_index in range(1, 4):
                    for spec in specs:
                        barrier = threading.Barrier(CLIENT_COUNT)
                        wave_start = dt.datetime.now(dt.timezone.utc).isoformat()
                        wave = list(pool.map(lambda i: request(i, spec, barrier), range(CLIENT_COUNT)))
                        for row in wave: row['round'] = round_index
                        rows.extend(wave)
                        report['rounds'].append({'round': round_index, 'name': spec[0],
                            'started_utc': wave_start, 'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(), **stats(wave)})
                        if sum(not r['ok'] for r in wave) >= 5:
                            report['aborted'] = True
                            report['abort_reason'] = f'At least five failures in a {CLIENT_COUNT}-request wave.'
                            break
                    if report['aborted']: break
                    if round_index < 3: time.sleep(5)
        report['http_finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        for name, _ in specs:
            selected = [r for r in rows if r['name'] == name]
            if selected: report['concurrent'][name] = stats(selected)
        report['total_concurrent_requests'] = len(rows)
        report['total_concurrent_failures'] = sum(not r['ok'] for r in rows)
        report['failure_types'] = {e: sum(r['error_type'] == e for r in rows)
                                   for e in sorted({r['error_type'] for r in rows if r['error_type']})}
    finally:
        for client in clients: client.close()
        connections.close_all()
        deleted, _ = Session.objects.filter(session_key__in=keys).delete()
        report['temporary_sessions_created'] = len(keys)
        report['temporary_sessions_deleted'] = deleted
        report['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    print('PABASA_CURRENT_TWENTY_TEST ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
