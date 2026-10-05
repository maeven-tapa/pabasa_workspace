"""Exercise independent student logins against one disposable SQLite file."""
from contextlib import closing
from datetime import timedelta
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from .models import LiveAssessmentSession, Material, User
from .student_session_lock import STUDENT_SESSION_LEASE_TIMEOUT


CONCURRENT_REQUESTS = r'''
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[1]
settings.ALLOWED_HOSTS = ['testserver']
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
import json, shlex, threading
from pathlib import Path
from django.db import close_old_connections
from django.http import JsonResponse
from django.test import Client
from django.urls import clear_url_caches, path, reverse
from django.utils import timezone
from datetime import timedelta
from pabasa_app.models import LiveAssessmentSession, User
from pabasa_site import urls

students = list(User.objects.filter(custom_id__startswith='CONCURRENT-LIVE-STUDENT-'))
barrier = threading.Barrier(len(students))
speech_ready = threading.Barrier(len(students) + 1)
release_speech = threading.Event()

def blocked_speech(request):
    # Replace only provider I/O: the real login middleware still validates
    # each long-running request while the other threads handle heartbeats.
    speech_ready.wait(timeout=10)
    if not release_speech.wait(timeout=15):
        return JsonResponse({'success': False}, status=504)
    return JsonResponse({'success': True})

urls.urlpatterns.insert(0, path('test-blocked-speech/', blocked_speech))
clear_url_caches()

def simulate_speech(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = student.active_session_key
    try:
        return client.post('/test-blocked-speech/').status_code
    finally:
        close_old_connections()

def check_heartbeat(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = student.active_session_key
    try:
        return client.post(reverse('student_session_heartbeat'), {'page': reverse('assessment')}).status_code
    finally:
        close_old_connections()

def read_and_publish(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = student.active_session_key
    statuses = []
    try:
        barrier.wait(timeout=10)
        response = client.post(reverse('student_session_heartbeat'), {'page': reverse('assessment')})
        statuses.append(('heartbeat', response.status_code))
        for progress in (0.1, 0.2, 0.3):
            barrier.wait(timeout=10)
            response = client.post(reverse('live_assessment_student_state_update', args=[sys.argv[2]]),
                json.dumps({'status': 'reading', 'progress': progress, 'elapsed_seconds': 30,
                    'recovery_state': {'stage': 'words', 'task1_score': student.pk % 10}}),
                content_type='application/json')
            statuses.append(('publish', response.status_code))
            response = client.get(reverse('live_assessment_session_state', args=[sys.argv[2]]))
            statuses.append(('poll', response.status_code))
        statuses.append(('auth', 200 if client.session.get('user_id') == student.pk else 401))
        return statuses
    finally:
        close_old_connections()

launch_args = shlex.split(Path(sys.argv[3]).read_text())
thread_count = int(launch_args[launch_args.index('--threads') + 1])
with ThreadPoolExecutor(max_workers=thread_count) as executor:
    speech_requests = [executor.submit(simulate_speech, student) for student in students]
    try:
        speech_ready.wait(timeout=10)
        heartbeat_requests = [executor.submit(check_heartbeat, student) for student in students]
        assert [request.result(timeout=10) for request in heartbeat_requests] == [200] * 10
        assert all(not request.done() for request in speech_requests)
    finally:
        release_speech.set()
    assert [request.result(timeout=10) for request in speech_requests] == [200] * 10
    outcomes = list(executor.map(read_and_publish, students))
failures = [(index, operation, status) for index, outcomes_for_student in enumerate(outcomes)
    for operation, status in outcomes_for_student if status != 200]
assert not failures, f'Concurrent student request failures: {failures}'
session = LiveAssessmentSession.objects.get(pk=sys.argv[2])
assert session.status == 'started'
assert len(session.student_states) == 10
assert all(session.student_states[str(student.pk)]['progress'] == 0.3 for student in students)
assert all(session.student_states[str(student.pk)]['recovery_state']['task1_score'] == student.pk % 10 for student in students)
assert all(User.objects.get(pk=student.pk).active_session_key == student.active_session_key for student in students)
print('10 student logins preserved; 80 overlapping heartbeat, publish, poll and auth checks passed.')
print('Login checks stayed available while all 10 speech requests were waiting on provider I/O.')

# Reconnect all ten accounts from replacement devices at once. Each old
# device has stopped publishing presence beyond its takeover lease.
User.objects.filter(pk__in=[student.pk for student in students]).update(
    active_session_last_seen=timezone.now() - timedelta(minutes=11))

def sign_in_again(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    try:
        response = client.post(reverse('login_user'), {
            'custom_id': student.custom_id, 'password': 'concurrent-test-password'})
        if response.status_code != 200:
            return (response.status_code, response.json().get('error'))
        new_key = client.session.session_key
        old_client = Client(raise_request_exception=False)
        old_client.cookies[settings.SESSION_COOKIE_NAME] = student.active_session_key
        assert old_client.post(reverse('student_session_heartbeat')).status_code == 401
        assert client.post(reverse('student_session_heartbeat'), {'page': reverse('assessment')}).status_code == 200
        assert User.objects.get(pk=student.pk).active_session_key == new_key
        return 200
    finally:
        close_old_connections()

with ThreadPoolExecutor(max_workers=thread_count) as executor:
    login_statuses = list(executor.map(sign_in_again, students))
assert login_statuses == [200] * 10, f'Concurrent sign-in failures: {login_statuses}'
print('10 concurrent replacement logins kept ownership isolated and recovery intact.')
session.refresh_from_db()
assert all(session.student_states[str(student.pk)]['progress'] == 0.3 for student in students)
'''


class LiveCrlaConcurrentRequestsTests(TransactionTestCase):
    def make_user(self, identifier, role='student'):
        return User.objects.create(custom_id=identifier, role=role, first_name=identifier,
            last_name='Concurrent', middle_initial='', suffix='', sex='female',
            birth_month=1, birth_day=1, birth_year=2012,
            email=identifier.lower() + '@example.com', password_hash=self.test_password_hash)

    def test_ten_students_can_reconnect_and_publish_concurrently(self):
        self.test_password_hash = make_password('concurrent-test-password')
        teacher = self.make_user('CONCURRENT-LIVE-TEACHER', 'teacher')
        material = Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
        if material is None:
            material = Material.objects.create(title='CRLA BoSY', item_type='paragraph',
                is_system_owned=True, is_official_reading=True, assessment_kind='crla',
                system_assessment_key='bosy_crla_pretest')
        students = []
        earlier = timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(minutes=1)
        for index in range(10):
            student = self.make_user(f'CONCURRENT-LIVE-STUDENT-{index}')
            login = SessionStore()
            login.update({'user_id': student.pk, 'user_role': 'student'})
            login.create()
            User.objects.filter(pk=student.pk).update(active_session_key=login.session_key,
                active_session_created_at=earlier, active_session_last_seen=earlier,
                last_activity=earlier, active_session_learning=True)
            students.append(student)
        session = LiveAssessmentSession.objects.create(id='concurrent-live-timeout', teacher=teacher,
            material=material, status='started', start_at=timezone.now(), timing_mode='none',
            student_ids=[student.pk for student in students], student_count=10,
            batch_assignments={str(student.pk): 1 for student in students}, total_batches=1,
            student_states={str(student.pk): {'status': 'reading', 'progress': 0} for student in students})
        # Separate connections in a child process use an actual on-disk DB,
        # matching the deployed SQLite setup rather than its in-memory test lock.
        with tempfile.TemporaryDirectory(prefix='pabasa-live-concurrency-') as directory:
            database = Path(directory) / 'live.sqlite3'
            with closing(sqlite3.connect(database)) as target:
                connection.connection.backup(target)
            result = subprocess.run([sys.executable, '-c', CONCURRENT_REQUESTS, str(database), session.pk,
                    str(Path(__file__).resolve().parents[2] / 'Procfile')],
                cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'K_SERVICE': ''},
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertIn('10 student logins preserved', result.stdout)
            self.assertIn('Login checks stayed available', result.stdout)
            self.assertIn('10 concurrent replacement logins', result.stdout)
