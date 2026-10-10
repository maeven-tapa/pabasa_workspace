"""Offline regression checks: fake Django/database/HTTP, real worker barriers."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parent


def load_script(filename):
    spec = importlib.util.spec_from_file_location('benchmark_under_test', ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BenchmarkTests(unittest.TestCase):
    def exercise(self, filename, *, fail_wave=False, fail_baseline=False, fail_setup=False):
        saved, deleted, requests, connections = [], [], [], []
        teacher = types.SimpleNamespace(pk=1, role='teacher', is_archived=False)
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = (1000,)
        cursor.fetchall.return_value = []
        connection = Mock()
        connection.cursor.return_value = cursor
        settings = types.SimpleNamespace(DATABASES={'default': {'OPTIONS': {}}},
                                         SESSION_COOKIE_NAME='sessionid')

        class SessionStore(dict):
            def set_expiry(self, seconds):
                self.expiry = seconds

            def save(self):
                if fail_setup and len(saved) == 7:
                    raise RuntimeError('Synthetic setup failure')
                self.session_key = f'synthetic-{len(saved)}'
                saved.append(self)

        def delete_sessions(**kwargs):
            deleted.extend(kwargs['session_key__in'])
            return types.SimpleNamespace(delete=lambda: (len(deleted), {}))

        class Client:
            def __init__(self, host, timeout):
                self.closed = False
                connections.append(self)

            def request(self, method, path, headers):
                self.path = path
                requests.append((path, headers))

            def getresponse(self):
                failed = fail_baseline or (fail_wave and len(requests) > 9)
                body = (b'PABASA Dashboard' if '/dashboard/teacher/?' in self.path
                        else b'{"success": true}')
                return types.SimpleNamespace(status=503 if failed else 200, read=lambda: body)

            def close(self):
                self.closed = True

        def view(request):
            dashboard = '/dashboard/teacher/?' in request.path
            return types.SimpleNamespace(status_code=200,
                content=b'PABASA Dashboard' if dashboard else b'{"success": true}',
                get=lambda name, default='': 'text/html' if dashboard else 'application/json')

        class Queries(list):
            def __init__(self, connection):
                super().__init__()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        modules = {}

        def module(name, **attrs):
            modules[name] = types.ModuleType(name)
            modules[name].__dict__.update(attrs)

        module('django', setup=lambda: None)
        module('django.conf', settings=settings)
        module('django.contrib.sessions.backends.db', SessionStore=SessionStore)
        module('django.contrib.sessions.models',
               Session=types.SimpleNamespace(objects=types.SimpleNamespace(filter=delete_sessions)))
        module('django.contrib.auth.models', AnonymousUser=lambda: object())
        module('django.core.management', call_command=Mock())
        module('django.db', connection=connection, connections=Mock())
        module('django.test', RequestFactory=lambda: types.SimpleNamespace(
            get=lambda path, **kwargs: types.SimpleNamespace(path=path)))
        module('django.test.utils', CaptureQueriesContext=Queries)
        module('pabasa_app.models',
               Section=types.SimpleNamespace(objects=types.SimpleNamespace(
                   select_related=lambda name: types.SimpleNamespace(
                       get=lambda **kwargs: types.SimpleNamespace(teacher=teacher)))),
               Enrollment=types.SimpleNamespace(objects=types.SimpleNamespace(
                   filter=lambda **kwargs: types.SimpleNamespace(count=lambda: 1))))
        module('pabasa_app.views', dashboard_teacher=view,
               get_teacher_students_api=view, get_teacher_overview=view)
        module('pabasa_app', views=modules['pabasa_app.views'])
        benchmark = load_script(filename)
        output = io.StringIO()
        original_path = sys.path[:]
        try:
            with patch.dict(sys.modules, modules), patch.dict('os.environ', {}, clear=True), \
                    patch.object(benchmark.http.client, 'HTTPSConnection', Client), \
                    patch.object(benchmark.time, 'sleep'), \
                    patch.object(benchmark.logging, 'disable'), contextlib.redirect_stdout(output):
                runner = getattr(benchmark, 'run', None) or benchmark.run_test
                if fail_setup:
                    with self.assertRaisesRegex(RuntimeError, 'Synthetic setup failure'):
                        runner()
                    report = None
                else:
                    runner()
                    report = json.loads(output.getvalue().strip().split(' ', 1)[1])
        finally:
            sys.path[:] = original_path
        self.assertEqual(deleted, [s.session_key for s in saved])
        self.assertTrue(all(s.expiry == 600 for s in saved))
        self.assertTrue(all(c.closed for c in connections))
        if report:
            self.assertEqual(report['clients'], 20)
            self.assertEqual(report['temporary_sessions_created'], 20)
            self.assertEqual(report['temporary_sessions_deleted'], 20)
            self.assertTrue(all('20-client-test' in headers['User-Agent'] for _, headers in requests))
        return report, requests

    def test_current_twenty_sessions_and_request_totals(self):
        report, requests = self.exercise('test_current_fifteen_users.py')
        self.assertFalse(report['aborted'])
        self.assertEqual(len(requests), 189)
        self.assertEqual(report['total_concurrent_requests'], 180)
        self.assertEqual(len({h['Cookie'] for _, h in requests}), 20)
        self.assertTrue(all(w['samples'] == 20 for w in report['rounds']))
        self.assertTrue(all(r['samples'] == 60 for r in report['concurrent'].values()))

    def test_previous_benchmark_twenty_sessions_and_request_totals(self):
        report, requests = self.exercise('test_fifteen_users.py')
        self.assertEqual(len(requests), 180)
        self.assertEqual(report['total_http_requests'], 180)
        self.assertEqual(len({h['Cookie'] for _, h in requests}), 20)
        self.assertTrue(all(r['samples'] == 60 for r in report['http_results'].values()))
        self.assertTrue(all(r['samples'] == 40 for r in report['internal_results'].values()))

    def test_wave_failure_aborts_and_cleans_twenty_sessions(self):
        report, requests = self.exercise('test_current_fifteen_users.py', fail_wave=True)
        self.assertTrue(report['aborted'])
        self.assertEqual(report['total_concurrent_requests'], 20)
        self.assertEqual(len(requests), 29)
        self.assertIn('20-request wave', report['abort_reason'])

    def test_baseline_failure_skips_load_and_cleans_sessions(self):
        report, requests = self.exercise('test_current_fifteen_users.py', fail_baseline=True)
        self.assertTrue(report['aborted'])
        self.assertEqual(report['total_concurrent_requests'], 0)
        self.assertEqual(len(requests), 3)

    def test_partial_session_setup_cleans_only_created_sessions(self):
        for filename in ('test_current_fifteen_users.py', 'test_fifteen_users.py'):
            with self.subTest(filename=filename):
                self.exercise(filename, fail_setup=True)


if __name__ == '__main__':
    unittest.main()
