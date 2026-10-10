"""Internal read-only view benchmark; Redis receives synthetic payloads only.

Run inside the deployed image with a base64-encoded temporary Redis connection
object in argv[1]. This does not deploy a cache or change production records.
"""

import base64
import concurrent.futures
import http.client
import json
import logging
import math
import os
import statistics
import sys
import threading
import time
import urllib.parse
import uuid

CLIENT_COUNT = 20

sys.path.insert(0, '/app/pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
from django.conf import settings

# PostgreSQL enforces read-only operations on every connection in this process.
settings.DATABASES['default']['OPTIONS']['options'] = '-c default_transaction_read_only=on'
import django
django.setup()
logging.disable(logging.CRITICAL)
from django.contrib.auth.models import AnonymousUser
from django.db import connection, connections
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from pabasa_app.models import Section, Enrollment
from pabasa_app import views

trial = json.loads(base64.b64decode(sys.argv[1]))
redis_host = urllib.parse.urlparse(trial['url']).hostname
redis_headers = {'Authorization': 'Bearer ' + trial['token'], 'Content-Type': 'application/json'}
section = Section.objects.select_related('teacher').get(pk=6)
teacher_id = section.teacher_id
row_count = Enrollment.objects.filter(section=section, status='active').count()
connections.close_all()
local = threading.local()
factory = RequestFactory()


def redis_command(command):
    client = getattr(local, 'redis', None)
    if client is None:
        client = local.redis = http.client.HTTPSConnection(redis_host, timeout=15)
    client.request('POST', '/', json.dumps(command), redis_headers)
    response = client.getresponse()
    result = json.loads(response.read())
    if response.status != 200 or 'error' in result:
        raise RuntimeError('Redis command failed; credentials and response withheld.')
    return result.get('result')


def run_view(spec):
    name, path, function = spec
    request = factory.get(path, {'section_id': 6}, HTTP_HOST='tupcpabasa.app',
                          HTTP_X_REQUESTED_WITH='XMLHttpRequest', secure=True)
    request.session = {'user_id': teacher_id, 'user_role': 'teacher'}
    request.user = AnonymousUser()
    connection.close()
    started = time.perf_counter()
    try:
        with CaptureQueriesContext(connection) as queries:
            response = function(request)
            content = response.content
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            raise RuntimeError(f'{name} returned HTTP {response.status_code}; response withheld.')
        if 'application/json' in response.get('Content-Type', ''):
            if json.loads(content).get('success') is not True:
                raise RuntimeError(f'{name} did not return successful data; response withheld.')
        return {'ms': elapsed, 'queries': len(queries), 'sql_ms': sum(float(item['time']) * 1000 for item in queries),
                'bytes': len(content)}
    finally:
        connection.close()


def stats(values):
    ordered = sorted(values)
    return {'mean_ms': statistics.mean(values), 'median_ms': statistics.median(values),
            'p95_ms': ordered[math.ceil(len(values) * .95) - 1], 'samples': len(values)}


specs = [
    ('teacher_dashboard', '/dashboard/teacher/', views.dashboard_teacher),
    ('teacher_overview_api', '/dashboard/teacher/overview/', views.get_teacher_overview),
    ('teacher_students_api', '/dashboard/teacher/students-api/', views.get_teacher_students_api),
]
report = {'concurrency': CLIENT_COUNT, 'scope': 'Internal Django view render, same teacher and class; no HTTP middleware/browser/network timing.',
          'class_rows': row_count, 'redis_trial_region': trial['region'],
          'redis_scope': 'REST cache-read timings for synthetic payloads matching response sizes; these are not cached production responses.',
          'database_access': 'PostgreSQL default_transaction_read_only=on', 'results': {}}

for spec in specs:
    try:
        warm = run_view(spec)
        with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
            samples = list(pool.map(run_view, [spec] * (2 * CLIENT_COUNT)))
        result = {'uncached': stats([item['ms'] for item in samples]),
                  'queries_per_request_mean': statistics.mean(item['queries'] for item in samples),
                  'sql_ms_mean': statistics.mean(item['sql_ms'] for item in samples),
                  'response_bytes': warm['bytes']}
        key = 'pabasa-synthetic-benchmark:' + uuid.uuid4().hex
        # Match the byte size, never the content, of the actual response.
        payload = 'x' * warm['bytes']
        redis_command(['SET', key, payload, 'EX', 600])
        def read_cached(_):
            # Warm this thread's reusable HTTPS connection outside timing.
            if not getattr(local, 'warmed', False):
                redis_command(['GET', key])
                local.warmed = True
            started = time.perf_counter()
            cached = redis_command(['GET', key])
            duration = (time.perf_counter() - started) * 1000
            if cached != payload:
                raise RuntimeError('Synthetic Redis payload did not match.')
            return duration
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
                cached_samples = list(pool.map(read_cached, range(2 * CLIENT_COUNT)))
            result['redis_warm_read'] = stats(cached_samples)
        finally:
            redis_command(['DEL', key])
        report['results'][spec[0]] = result
    except Exception as error:
        # No credentials, query parameters, rows, or response content in logs.
        report['results'][spec[0]] = {'error_type': type(error).__name__,
                                    'error': str(error) if isinstance(error, RuntimeError) else 'Details withheld.'}

report['limitations'] = [f'{CLIENT_COUNT} concurrent internal requests share one teacher/class, not {CLIENT_COUNT} separate browser sessions.',
                         'Redis endpoint region was not selectable through the anonymous trial.',
                         'A production cache still needs authorization, invalidation, miss handling, and middleware.',
                         f'A small current class cannot establish performance for a {CLIENT_COUNT}-student roster.']
print('PABASA_CACHE_BENCHMARK ' + json.dumps(report), flush=True)
