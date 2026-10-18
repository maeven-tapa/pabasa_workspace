"""Exercise independent student logins against one disposable SQLite file."""
from contextlib import closing
from datetime import timedelta
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from .models import Assessment, CalendarEvent, Enrollment, LiveAssessmentSession, Material, School, SchoolCalendar, Section, User


CONCURRENT_REQUESTS = r'''
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[1]
settings.ALLOWED_HOSTS = ['testserver']
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
import asyncio, json, threading
from pathlib import Path
from django.db import close_old_connections, connections
from django.http import JsonResponse
from django.test import Client
from django.urls import clear_url_caches, path, reverse
from django.utils import timezone
from pabasa_app.models import Enrollment, LiveAssessmentSession, User
from django.contrib.sessions.models import Session
from pabasa_site import urls

students = list(User.objects.filter(custom_id__startswith='CONCURRENT-LIVE-STUDENT-'))
live_sessions = list(LiveAssessmentSession.objects.filter(id__startswith='concurrent-live-timeout'))
session_ids = {sid: live.pk for live in live_sessions for sid in live.student_ids}
def session_for(student):
    return session_ids[student.pk]

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
        return client.get(reverse('live_assessment_session_state', args=[session_for(student)])).status_code
    finally:
        close_old_connections()

def read_and_publish(student):
    close_old_connections()
    client = Client(raise_request_exception=False)
    client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
    statuses = []
    try:
        barrier.wait(timeout=10)
        response = client.get(reverse('live_assessment_session_state', args=[session_for(student)]))
        statuses.append(('login', response.status_code))
        for progress in (0.1, 0.2, 0.3):
            barrier.wait(timeout=10)
            response = client.post(reverse('live_assessment_student_state_update', args=[session_for(student)]),
                json.dumps({'status': 'reading', 'progress': progress, 'elapsed_seconds': 30,
                    'recovery_state': {'stage': 'words', 'task1_score': student.pk % 10}}),
                content_type='application/json')
            statuses.append(('publish', response.status_code))
            response = client.get(reverse('live_assessment_session_state', args=[session_for(student)]))
            statuses.append(('poll', response.status_code))
        statuses.append(('auth', 200 if client.session.get('user_id') == student.pk else 401))
        return statuses
    finally:
        close_old_connections()

assert len(students) == 20
assert Enrollment.objects.filter(student__in=students, is_active=True).count() == 20
# One provider wait and one foreground request per distinct student.
thread_count = 2 * len(students)
with ThreadPoolExecutor(max_workers=thread_count) as executor:
    speech_requests = [executor.submit(simulate_speech, student) for student in students]
    try:
        speech_ready.wait(timeout=10)
        login_checks = [executor.submit(check_login, student) for student in students]
        assert [request.result(timeout=10) for request in login_checks] == [200] * 20
        assert all(not request.done() for request in speech_requests)
    finally:
        release_speech.set()
    assert [request.result(timeout=10) for request in speech_requests] == [200] * 20
    outcomes = list(executor.map(read_and_publish, students))
failures = [(index, operation, status) for index, outcomes_for_student in enumerate(outcomes)
    for operation, status in outcomes_for_student if status != 200]
assert not failures, f'Concurrent student request failures: {failures}'
session = LiveAssessmentSession.objects.get(pk=sys.argv[2])
assert session.status == 'started'
states = {sid: state for live in LiveAssessmentSession.objects.filter(id__in=session_ids.values())
    for sid, state in live.student_states.items()}
assert len(states) == 20
assert all(states[str(student.pk)]['progress'] == 0.3 for student in students)
assert all(states[str(student.pk)]['recovery_state']['task1_score'] == student.pk % 10 for student in students)
assert all(Session.objects.filter(session_key=login_keys[student.pk]).exists() for student in students)
print('20 student logins preserved; 160 overlapping login, publish, poll and auth checks passed.')
print('Login checks stayed available while all 20 speech requests were waiting on provider I/O.')

# Real session/ticket authorization in worker threads must release DB slots on
# every reconnect and failed authorization, not only when an HTTP request ends.
from pabasa_app import crla_stream
from django.db import connection
from django.core import signing
from unittest.mock import patch
settings.CSRF_TRUSTED_ORIGINS = ['https://testserver']
material_id = session.material_id
def ticket_for(student):
    close_old_connections()
    try:
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
        response = client.post(reverse('crla_stream_ticket'), json.dumps({
            'material_id': material_id, 'mode': 'word', 'target_text': 'bata',
        }), content_type='application/json')
        if response.status_code != 200:
            from django.test import RequestFactory
            from pabasa_app import views
            diagnostic = RequestFactory().post('/api/reading/crla-stream/start/')
            diagnostic.session = client.session
            blocked = views._enforce_student_access_for_request(diagnostic, material=session.material, json_response=True)
            reason = json.loads(blocked.content).get('error') if blocked is not None else 'no block'
            raise AssertionError(f'Speech fixture authorization: {reason}; type={session.material.type}; has_assessment={bool(session.material.assessment_id)}')
        return response.json()['ticket']
    finally:
        close_old_connections()
with ThreadPoolExecutor(max_workers=20) as executor:
    tickets = list(executor.map(ticket_for, students))

async def verify_socket_workers():
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=20) as executor:
        loop.set_default_executor(executor)
        for round_index in range(3):
            opened = []
            ready = threading.Barrier(20)
            def load(student):
                result = crla_stream.socket_session({'headers': [(b'cookie',
                    (settings.SESSION_COOKIE_NAME + '=' + login_keys[student.pk]).encode())]})
                opened.append(connections['default'])
                ready.wait(timeout=20)
                return result
            sessions = await asyncio.gather(*(crla_stream.database_call(load, student) for student in students))
            assert all(db.connection is None for db in opened)
            assert [s.get('user_id') for s in sessions] == [s.pk for s in students]
            payloads = await asyncio.gather(*(crla_stream.database_call(crla_stream.validate_socket_ticket, ticket, login)
                for ticket, login in zip(tickets, sessions)))
            assert all(p['fields']['official_assessment_id'] == str(material_id) for p in payloads)
            failures = await asyncio.gather(*(crla_stream.database_call(crla_stream.validate_socket_ticket,
                tickets[(index + 1) % 20], login) for index, login in enumerate(sessions)), return_exceptions=True)
            assert all(isinstance(error, PermissionError) for error in failures)
asyncio.run(verify_socket_workers())
print('20 distinct enrolled students: session/ticket auth, three reconnect rounds and foreign-session rejection passed.')
print('All 20 worker DB connections returned after each simultaneous session lookup.')

if os.environ.get('PABASA_LIVE_GOOGLE_AUDIO'):
    sys.path.insert(0, str(Path.cwd().parent / 'tools'))
    from crla_twenty_google_probe import run
    run(students, login_keys, material_id)

# Exercise the actual reader endpoint and scoring with twenty simultaneous students.
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
            assert list(executor.map(lambda student: read_sentence_or_story(student, mode), students)) == [200] * 20
assert len(attempts) == 2 * len(students)
assert all(count == 2 for count in attempts.values())
print('20 simultaneous sentence and 20 story readings recovered provider 500s with isolated, accurate scores.')

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
        assert old_client.get(reverse('live_assessment_session_state', args=[session_for(student)])).status_code == 401
        assert client.get(reverse('live_assessment_session_state', args=[session_for(student)])).status_code == 200
        assert new_key != login_keys[student.pk]
        assert Session.objects.filter(session_key=new_key).exists()
        return 200
    finally:
        close_old_connections()

with ThreadPoolExecutor(max_workers=thread_count) as executor:
    login_statuses = list(executor.map(sign_in_again, students))
assert login_statuses == [200] * 20, f'Concurrent sign-in failures: {login_statuses}'
print('20 concurrent replacement logins kept sessions isolated and recovery intact.')
states = {sid: state for live in LiveAssessmentSession.objects.filter(id__in=session_ids.values())
    for sid, state in live.student_states.items()}
assert all(states[str(student.pk)]['progress'] == 0.3 for student in students)
'''


class LiveCrlaConcurrentRequestsTests(TransactionTestCase):
    def make_user(self, identifier, role='student'):
        return User.objects.create(custom_id=identifier, role=role, first_name=identifier,
            last_name='Concurrent', middle_initial='', suffix='', sex='female',
            birth_month=1, birth_day=1, birth_year=2012,
            email=identifier.lower() + '@example.com', password_hash=self.test_password_hash, school_record=self.school)

    def test_twenty_enrolled_students_can_reconnect_and_publish_concurrently(self):
        self.run_enrolled_students(20)

    def test_thirty_enrolled_students_can_reconnect_and_publish_concurrently(self):
        self.run_enrolled_students(30)

    def run_enrolled_students(self, client_count):
        cache.clear()
        self.test_password_hash = make_password('concurrent-test-password')
        self.school = School.objects.create(name='Concurrent Test School', code='CONCURRENT')
        calendar = SchoolCalendar.objects.create(school_year='Concurrent Year', current_term=1, is_active=True)
        teacher = self.make_user('CONCURRENT-LIVE-TEACHER', 'teacher')
        section = Section.objects.create(school=self.school, school_calendar=calendar, teacher=teacher,
            class_code='CONCURRENT', class_name='Concurrent Class', subject='Reading', assessment_week_enabled=True)
        today = timezone.localdate()
        for event_type, start, end in (
            ('school_opening', today - timedelta(days=2), today - timedelta(days=2)),
            ('pre_assessment', today - timedelta(days=1), today + timedelta(days=1)),
            ('school_closing', today + timedelta(days=20), today + timedelta(days=20)),
        ):
            CalendarEvent.objects.create(school_calendar=calendar, school=self.school,
                scope=CalendarEvent.SCOPE_SCHOOL, term=1, title=event_type,
                event_type=event_type, start_date=start, end_date=end)
        material = Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
        if material is None:
            material = Material.objects.create(title='CRLA BoSY', item_type='paragraph',
                is_system_owned=True, is_official_reading=True, assessment_kind='crla',
                system_assessment_key='bosy_crla_pretest', system_assessment_period='bosy',
                system_assessment_phase='pretest', official_term=1, type='assessment')
        assessment = Assessment.objects.create(teacher=teacher, section=section, title='Concurrent CRLA',
            code='CONCURRENT', assessment_type='paragraph', status='published',
            is_system_owned=True, system_assessment_key='bosy_crla_pretest')
        Material.objects.filter(pk=material.pk).update(assessment=assessment, section=None,
            language='Filipino', status='published', is_active=True, student_access=True, type='assessment')
        other_teacher = self.make_user('CONCURRENT-OTHER-TEACHER', 'teacher')
        other_section = Section.objects.create(school=self.school, school_calendar=calendar, teacher=other_teacher,
            class_code='CONCURRENT-B', class_name='Concurrent Class B', subject='Reading', assessment_week_enabled=True)
        sections = [section, other_section]
        teachers = [teacher, other_teacher]
        if client_count == 30:
            third_teacher = self.make_user('CONCURRENT-THIRD-TEACHER', 'teacher')
            sections.append(Section.objects.create(school=self.school, school_calendar=calendar, teacher=third_teacher,
                class_code='CONCURRENT-C', class_name='Concurrent Class C', subject='Reading', assessment_week_enabled=True))
            teachers.append(third_teacher)
        material.assigned_sections.add(*sections)
        students = []
        for index in range(client_count):
            student = self.make_user(f'CONCURRENT-LIVE-STUDENT-{index}')
            sections[index // 10].add_student(student)
            login = SessionStore()
            login.update({'user_id': student.pk, 'user_role': 'student'})
            login.create()
            students.append(student)
        # Preserve the product's ten-student batch limit: two legitimate classes
        # read simultaneously, for twenty distinct enrolled student clients.
        sessions = []
        for group in range(client_count // 10):
            members = students[group * 10:(group + 1) * 10]
            sessions.append(LiveAssessmentSession.objects.create(id=f'concurrent-live-timeout-{group}',
                teacher=teachers[group], section=sections[group], material=material,
                status='started', start_at=timezone.now(),
                student_ids=[student.pk for student in members], student_count=len(members), batch_size=10,
                batch_assignments={str(student.pk): 1 for student in members}, total_batches=1,
                student_states={str(student.pk): {'status': 'reading', 'progress': 0} for student in members}))
        # Separate connections in a child process use an actual on-disk DB,
        # isolating local concurrency from the in-memory SQLite test lock.
        with tempfile.TemporaryDirectory(prefix='pabasa-live-concurrency-') as directory:
            database = Path(directory) / 'live.sqlite3'
            with closing(sqlite3.connect(database)) as target:
                connection.connection.backup(target)
            code = CONCURRENT_REQUESTS if client_count == 20 else re.sub(r'\b20\b', '30', CONCURRENT_REQUESTS)
            result = subprocess.run([sys.executable, '-c', code, str(database), sessions[0].pk],
                cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'K_SERVICE': ''},
                capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
            self.assertIn(f'{client_count} student logins preserved', result.stdout)
            self.assertIn('Login checks stayed available', result.stdout)
            self.assertIn(f'{client_count} simultaneous sentence and {client_count} story readings recovered', result.stdout)
            self.assertIn(f'{client_count} concurrent replacement logins', result.stdout)
            for line in result.stdout.splitlines():
                if line.startswith('LIVE_GOOGLE_TWENTY:'):
                    print(line)
