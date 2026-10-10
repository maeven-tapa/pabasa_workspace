"""Read-only student-list timing breakdown, with no SQL text or personal data logged."""
import base64
import concurrent.futures
import json
import logging
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

CLIENT_COUNT = 20


def profile():
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    from django.conf import settings
    settings.DATABASES['default']['OPTIONS']['options'] = '-c default_transaction_read_only=on'
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.db import connection, connections
    from django.test import RequestFactory
    from django.test.utils import CaptureQueriesContext
    from django.contrib.auth.models import AnonymousUser
    from pabasa_app.models import Section
    from pabasa_app.views import get_teacher_students_api
    teacher_id = Section.objects.get(pk=6).teacher_id
    connections.close_all()
    def sample(_):
        connection.close()
        request = RequestFactory().get('/dashboard/teacher/students-api/?section_id=6',
            HTTP_HOST='tupcpabasa.app', HTTP_X_REQUESTED_WITH='XMLHttpRequest', secure=True)
        request.session = {'user_id': teacher_id, 'user_role': 'teacher'}
        request.user = AnonymousUser()
        started = time.perf_counter()
        try:
            connection.ensure_connection()
            connect_ms = (time.perf_counter() - started) * 1000
            with CaptureQueriesContext(connection) as queries:
                response = get_teacher_students_api(request)
                ok = response.status_code == 200 and json.loads(response.content).get('success') is True
            rows = []
            for q in queries:
                # Table identifiers only; never expose query text, arguments or records.
                tables = sorted(set(re.findall(r'(?:FROM|JOIN)\s+"([A-Za-z_][A-Za-z_0-9]*)"', q['sql'], re.IGNORECASE)))
                rows.append({'tables': tables, 'ms': float(q['time']) * 1000})
            return {'total_ms': (time.perf_counter() - started) * 1000, 'connect_ms': connect_ms,
                    'sql_ms': sum(r['ms'] for r in rows), 'ok': ok, 'queries': rows}
        finally:
            connection.close()
    single = [sample(None) for _ in range(3)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
        concurrent_samples = list(pool.map(sample, range(2 * CLIENT_COUNT)))
    def aggregate(samples):
        groups = {}
        for s in samples:
            for q in s['queries']:
                key = ','.join(q['tables']) or 'unclassified SQL statements'
                groups.setdefault(key, []).append(q['ms'])
        return {'requests': len(samples), 'failures': sum(not s['ok'] for s in samples),
                'total_ms_mean': statistics.mean(s['total_ms'] for s in samples),
                'connect_ms_mean': statistics.mean(s['connect_ms'] for s in samples),
                'sql_ms_mean': statistics.mean(s['sql_ms'] for s in samples),
                'query_groups': sorted([{'tables': k, 'count': len(v), 'mean_ms': statistics.mean(v),
                                         'max_ms': max(v)} for k,v in groups.items()],
                                       key=lambda x:x['mean_ms'], reverse=True)}
    print('PABASA_STUDENT_PROFILE ' + json.dumps({'concurrency': CLIENT_COUNT,
                                                'single': aggregate(single),
                                                f'concurrent_{CLIENT_COUNT}': aggregate(concurrent_samples)}), flush=True)


if __name__ == '__main__':
    if os.environ.get('CLOUD_RUN_EXECUTION'):
        profile()
    else:
        sdk = Path(r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk')
        source = base64.b64encode(Path(__file__).read_bytes()).decode()
        code = f"import base64;exec(base64.b64decode('{source}'))"
        completed = subprocess.run([str(sdk / 'platform/bundledpython/python.exe'), str(sdk / 'lib/gcloud.py'),
            'run', 'jobs', 'execute', 'pabasa-revision-check-01172', '--project=project-2b0d295d-ee06-40a7-927',
            '--region=asia-southeast1', '--args=^~^-c~'+code, '--wait', '--format=value(metadata.name)'],
            capture_output=True, text=True)
        print(json.dumps({'status': 'succeeded' if completed.returncode == 0 else 'failed',
                          'execution': completed.stdout.strip() if completed.returncode == 0 else None}))
        raise SystemExit(completed.returncode)
