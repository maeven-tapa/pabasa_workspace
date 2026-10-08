"""Exercise independent student logins against one disposable SQLite file."""
from contextlib import closing
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
from pabasa_app.models import LiveAssessmentSession, User
from django.contrib.sessions.models import Session
from pabasa_site import urls

students = list(User.objects.filter(custom_id__startswith='CONCURRENT-LIVE-STUDENT-'))
login_keys = {int(login.get_decoded()['user_id']): login.session_key
    for login in Session.objects.all() if login.get_decoded().get('user_role') == 'student'}
barrier = threading.Barrier(len(students))
speech_ready = threading.Barrier(len(students) + 1)
release_speech = threading.Event()

def blocked_speech(request):
    # Replace only provider I/O: the real login middleware still validates
    # each long-running request while the other threads handle login checks.
    speech_ready.wait(timeout=10)
    if not release_speech.wait(timeout=15):
        return JsonResponse({'success': False}, status=504)
    return JsonResponse({'success': True})

urls.urlpatterns.insert(0, path('test-blocked-speech/', blocked_speech))
clear_url_caches()

def simulate_speech(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
    try:
        return client.post('/test-blocked-speech/').status_code
    finally:
        close_old_connections()

def check_login(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
    try:
        return client.get(reverse('live_assessment_session_state', args=[sys.argv[2]])).status_code
    finally:
        close_old_connections()

def read_and_publish(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
    statuses = []
    try:
        barrier.wait(timeout=10)
        response = client.get(reverse('live_assessment_session_state', args=[sys.argv[2]]))
        statuses.append(('login', response.status_code))
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
        login_checks = [executor.submit(check_login, student) for student in students]
        assert [request.result(timeout=10) for request in login_checks] == [200] * 10
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
assert all(Session.objects.filter(session_key=login_keys[student.pk]).exists() for student in students)
print('10 student logins preserved; 80 overlapping login, publish, poll and auth checks passed.')
print('Login checks stayed available while all 10 speech requests were waiting on provider I/O.')

# Exercise the actual reader endpoint and scoring with ten simultaneous students.
# Only external Google transport/credentials are replaced, including a temporary
# provider 500 for every recording. Each recovered transcript belongs to its student.
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from google.api_core.exceptions import InternalServerError
from google.cloud.speech_v2.types import cloud_speech
settings.GOOGLE_CLOUD_PROJECT_ID = 'concurrency-test'
settings.GOOGLE_STT_API_KEY = ''
attempts = {}
attempt_lock = threading.Lock()
provider_barrier = threading.Barrier(len(students))
transcripts = {}

def recognize(*, request, **kwargs):
    audio = request.content
    with attempt_lock:
        attempts[audio] = attempts.get(audio, 0) + 1
        attempt = attempts[audio]
    if attempt == 1:
        provider_barrier.wait(timeout=10)
        raise InternalServerError('500 Internal server error') from RuntimeError('provider transport')
    return cloud_speech.RecognizeResponse(results=[{'alternatives': [{'transcript': transcripts[audio]}]}])

def read_sentence_or_story(student, mode):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
    audio = f'{student.pk}-{mode}'.encode()
    target = 'Si Ana ay masaya.' if mode == 'sentence' else 'Si Ana ay masaya. May bola si Ana.'
    # Half the students substitute a word; recovery must preserve actual errors.
    transcripts[audio] = target if student.pk % 2 else target.replace('masaya', 'malungkot')
    try:
        response = client.post(reverse('reading_transcribe_api'), {
            'audio': SimpleUploadedFile('clip.webm', audio, content_type='audio/webm'),
            'target_text': target, 'language': 'Filipino', 'mode': mode,
            'crla_sentence_word_scoring': '1', 'sentence_word_results': '[]',
            'crla_story_reading': '1', 'current_syllable_index': '0',
        }, HTTP_X_PABASA_STT_PROVIDER='google', HTTP_X_PABASA_STT_MODEL='chirp_3')
        assert response.status_code == 200, (mode, student.pk, response.status_code, response.content[:300])
        data = response.json()
        assert data['success'] and data['raw_transcript'] == transcripts[audio], data
        results = data['word_results']
        assert len(results) == len(target.split()), results
        incorrect = [word for word in results if word['result'] != 'correct']
        assert len(incorrect) == (0 if student.pk % 2 else 1), results
        assert attempts[audio] == 2, attempts
        assert client.session.get('user_id') == student.pk
        return 200
    finally:
        close_old_connections()

with patch('pabasa_app.reading_stt.google_stt_credentials', return_value=object()), \
        patch('google.cloud.speech_v2.SpeechClient') as speech_client:
    speech_client.return_value.recognize.side_effect = recognize
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for mode in ('sentence', 'paragraph'):
            assert list(executor.map(lambda student: read_sentence_or_story(student, mode), students)) == [200] * 10
assert len(attempts) == 20
assert all(count == 2 for count in attempts.values())
print('10 simultaneous sentence and 10 story readings recovered provider 500s with isolated, accurate scores.')

# Reconnect after explicit server-side revocation, without any inactivity rule.
Session.objects.filter(session_key__in=[login_keys[student.pk] for student in students]).delete()

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
        old_client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
        assert old_client.get(reverse('live_assessment_session_state', args=[sys.argv[2]])).status_code == 401
        assert client.get(reverse('live_assessment_session_state', args=[sys.argv[2]])).status_code == 200
        assert new_key != login_keys[student.pk]
        assert Session.objects.filter(session_key=new_key).exists()
        return 200
    finally:
        close_old_connections()

with ThreadPoolExecutor(max_workers=thread_count) as executor:
    login_statuses = list(executor.map(sign_in_again, students))
assert login_statuses == [200] * 10, f'Concurrent sign-in failures: {login_statuses}'
print('10 concurrent replacement logins kept sessions isolated and recovery intact.')
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
        for index in range(10):
            student = self.make_user(f'CONCURRENT-LIVE-STUDENT-{index}')
            login = SessionStore()
            login.update({'user_id': student.pk, 'user_role': 'student'})
            login.create()
            students.append(student)
        session = LiveAssessmentSession.objects.create(id='concurrent-live-timeout', teacher=teacher,
            material=material, status='started', start_at=timezone.now(),
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
            self.assertIn('10 simultaneous sentence and 10 story readings recovered', result.stdout)
            self.assertIn('10 concurrent replacement logins', result.stdout)
