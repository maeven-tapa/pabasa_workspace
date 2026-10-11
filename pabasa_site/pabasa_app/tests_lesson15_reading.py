"""Isolated L15 G3 endpoint regressions; speech provider is simulated."""
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import lesson15_reading as reading
from .models import Enrollment, PrescribedReadingAttempt, School, SchoolCalendar, Section, User


class Lesson15ReadingTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory(prefix='pabasa-l15-media-')
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name, GOOGLE_STT_API_KEY='test-key')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        def user(role, number):
            return User.objects.create(custom_id=f'L15-{number}', role=role, first_name='Test', last_name=role,
                sex='male', birth_month=1, birth_day=1, birth_year=2018,
                email=f'l15-{number}@example.invalid', password_hash='!')
        self.student, self.teacher, self.other = user('student', 1), user('teacher', 2), user('teacher', 3)
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
        school = School.objects.create(name='Disposable L15 School')
        section = Section.objects.create(school=school, school_calendar=self.calendar, teacher=self.teacher,
            class_code='L15', class_name='Disposable', subject='Reading')
        Enrollment.objects.create(student=self.student, section=section, school=school,
            school_calendar=self.calendar, assigned_teacher=self.teacher)
        self.scope = {'state': 'ARAL_ACTIVE', 'school_calendar': self.calendar, 'term': 1}
        for target, value in (
            ('_current_learning_context', self.scope), ('_student_can_open_prescribed_activity', True),
            ('_enforce_student_access_for_request', None), ('uses_knowlez_stt', False),
        ):
            mock = patch('pabasa_app.views.' + target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        self.student_client = self.client_for(self.student)
        self.teacher_client = self.client_for(self.teacher)

    def client_for(self, user):
        client = Client()
        session = client.session
        session.update({'user_id': user.pk, 'user_role': user.role})
        session.save()
        return client

    def current(self):
        from . import views
        return views._current_progress_queryset(self.student, self.scope).filter(activity_key=reading.KEY).first()

    def record(self, transcript='tawa', attempt_id=None, body=None):
        progress = self.current()
        index = progress.current_index if progress else 0
        fields = dict(target_text=reading.TEXTS[index], language='Filipino', mode='word',
            prescribed_activity_key=reading.KEY, item_index=index,
            state_version=reading.state_for(progress)['state_version'], attempt_id=str(attempt_id or uuid.uuid4()),
            audio=SimpleUploadedFile('reading.webm', body or b'\x1aE\xdf\xa3disposable-audio', content_type='audio/webm'))
        with patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(transcript, 'chirp_3', '')):
            return self.student_client.post(reverse('reading_transcribe_api'), fields)

    def skip(self, **overrides):
        progress = self.current()
        payload = {'activity_key': reading.KEY, 'item_index': progress.current_index if progress else 0,
                   'state_version': reading.state_for(progress)['state_version'], 'request_id': str(uuid.uuid4())}
        payload.update(overrides)
        return self.student_client.post(reverse('lesson15_reading_skip'), payload, content_type='application/json')

    def grade(self, classification, client=None, **overrides):
        result = reading.item_result(reading.state_for(self.current()), 0)
        payload = dict(student_id=self.student.pk, item_index=0, classification=classification,
                       attempt_id=result.get('attempt_id'), review_version=result.get('review_version'))
        payload.update(overrides)
        return (client or self.teacher_client).post(reverse('lesson15_reading_classify'), payload, content_type='application/json')

    def test_success_evidence_pending_and_progress(self):
        response = self.record()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['evidence_saved'])
        self.assertEqual(self.current().current_index, 1)
        attempt = PrescribedReadingAttempt.objects.get()
        self.assertEqual((attempt.term, attempt.school_calendar_id, attempt.expected_text), (1, self.calendar.pk, 'tawa'))
        self.assertTrue(attempt.stt_match)
        self.assertTrue(Path(attempt.audio_file.path).exists())
        self.assertEqual(reading.item_result(self.current().state, 0)['classification'], 'PENDING_REVIEW')

    def test_failure_retains_evidence_without_advancing(self):
        self.assertEqual(self.record('mali').status_code, 200)
        self.assertEqual(self.current().current_index, 0)
        self.assertFalse(PrescribedReadingAttempt.objects.get().stt_match)
        self.assertEqual(self.record().status_code, 200)
        self.assertEqual(PrescribedReadingAttempt.objects.count(), 2)

    def test_pending_review_does_not_block_completion_or_next_unlock(self):
        from . import views
        self.record()
        for _ in range(1, len(reading.TEXTS)):
            self.assertEqual(self.skip().status_code, 200)
        self.assertTrue(self.current().activity_completed)
        self.assertEqual(reading.item_result(self.current().state, 0)['classification'], 'PENDING_REVIEW')
        keys = views._prescribed_activity_order()
        position = keys.index(reading.KEY)
        for key in keys[:position]:
            views._current_progress_update_or_create(self.student, self.scope, key,
                defaults={'activity_completed': True})
        with patch('pabasa_app.views._lesson14_gawain4_fully_evaluated', return_value=True):
            self.assertIn(keys[position + 1], views._unlocked_prescribed_activity_keys(self.student, self.scope))

    def test_empty_transcript_attempt_preserves_retry_state(self):
        self.assertEqual(self.record('').status_code, 200)
        self.assertEqual(self.current().current_index, 0)
        self.assertEqual(self.record().status_code, 200)
        self.assertEqual(self.current().current_index, 1)

    def test_duplicate_failed_attempt_is_saved_once(self):
        attempt_id = uuid.uuid4()
        self.assertEqual(self.record('mali', attempt_id).status_code, 200)
        self.assertEqual(self.record('mali', attempt_id).status_code, 200)
        self.assertEqual(PrescribedReadingAttempt.objects.count(), 1)

    def test_current_reading_retains_all_clips_for_teacher(self):
        attempt_id = uuid.uuid4()
        self.record('mali', attempt_id, b'\x1aE\xdf\xa3clip-one')
        self.record('tawa', attempt_id, b'\x1aE\xdf\xa3clip-two')
        rows = self.teacher_client.get(reverse('lesson15_reading_reviews'), {'student_id': self.student.pk}).json()
        self.assertEqual(len(rows['items'][0]['recordings']), 2)
        self.assertEqual(rows['items'][0]['transcript'], 'mali tawa')

    def test_skip_idempotency_stale_and_last_completion(self):
        request_id = str(uuid.uuid4())
        self.assertEqual(self.skip(request_id=request_id).status_code, 200)
        self.assertEqual(self.skip(request_id=request_id, item_index=0, state_version=1).status_code, 200)
        self.assertEqual(self.current().current_index, 1)
        self.assertEqual(self.skip(item_index=0).status_code, 409)
        self.assertEqual(self.skip(state_version=1).status_code, 409)
        for index in range(1, len(reading.TEXTS)):
            self.assertEqual(self.skip().status_code, 200)
        progress = self.current()
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 22)
        self.assertEqual(PrescribedReadingAttempt.objects.count(), 0)
        rows = self.teacher_client.get(reverse('lesson15_reading_reviews'), {'student_id': self.student.pk}).json()
        self.assertEqual(rows['graded'], 22)
        self.assertTrue(all(row['classification'] == 'RED' and row['review_status'] == 'skipped' for row in rows['items']))
        self.assertEqual(self.grade('GREEN').status_code, 403)
        self.assertEqual(self.student_client.post(reverse('prescribed_activity_complete', args=[reading.KEY])).status_code, 200)

    def test_manual_grades_totals_refresh_and_conflict(self):
        self.record()
        for classification in ('GREEN', 'YELLOW', 'RED'):
            result = self.grade(classification)
            self.assertEqual(result.status_code, 200, result.content)
            self.assertEqual((result.json()['graded'], result.json()['pending'], result.json()['total']), (1, 0, 22))
            self.assertEqual(result.json()['items'][0]['classification'], classification)
        self.assertEqual(self.grade('GREEN', review_version=1).status_code, 409)
        refresh = self.teacher_client.get(reverse('lesson15_reading_reviews'), {'student_id': self.student.pk}).json()
        self.assertEqual(refresh['items'][0]['classification'], 'RED')
        self.assertEqual(len(self.current().state['review_history']), 3)

    def test_new_audio_cannot_inherit_teacher_grade(self):
        self.record('mali')
        self.assertEqual(self.grade('YELLOW').status_code, 200)
        first = PrescribedReadingAttempt.objects.get()
        self.record('mali')
        self.assertEqual(reading.item_result(self.current().state, 0)['classification'], 'PENDING_REVIEW')
        first.refresh_from_db()
        self.assertEqual(first.classification, 'PENDING_REVIEW')
        self.assertEqual(self.current().state['review_history'][-1]['classification'], 'YELLOW')

    def test_private_audio_and_term_isolation(self):
        self.record()
        url = reverse('lesson15_reading_audio', args=[PrescribedReadingAttempt.objects.get().pk])
        allowed = self.teacher_client.get(url)
        self.assertEqual(allowed.status_code, 200)
        self.assertGreater(sum(len(chunk) for chunk in allowed.streaming_content), 0)
        self.assertEqual(self.client_for(self.other).get(url).status_code, 403)
        self.assertEqual(self.grade('GREEN', client=self.client_for(self.other)).status_code, 403)
        self.scope['term'] = 2
        self.assertEqual(self.teacher_client.get(url).status_code, 403)
        data = self.teacher_client.get(reverse('lesson15_reading_reviews'), {'student_id': self.student.pk}).json()
        self.assertEqual(data['graded'], 0)

    def test_upload_failure_and_invalid_audio_do_not_advance(self):
        with patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('Disposable failure')):
            self.assertEqual(self.record().status_code, 502)
        self.assertEqual(PrescribedReadingAttempt.objects.count(), 0)
        self.assertIsNone(self.current())
        self.assertEqual(self.record(body=b'not audio').status_code, 400)
        self.assertEqual(self.record().status_code, 200)

    def test_client_cannot_forge_classification_or_advance(self):
        self.student_client.post(reverse('prescribed_activity_progress', args=[reading.KEY]),
            {'state': {'state_version': 1, 'current_index': 22, 'item_results': {'0': {'classification': 'GREEN'}}}}, content_type='application/json')
        self.assertEqual(self.current().current_index, 0)
        self.assertEqual(reading.item_result(self.current().state, 0)['classification'], '')

    def test_legacy_progress_and_restart_preserve_evidence(self):
        self.record()
        self.grade('GREEN')
        response = self.student_client.post(reverse('prescribed_activity_progress', args=[reading.KEY]),
            {'reset': True}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.current().current_index, 0)
        self.assertEqual(PrescribedReadingAttempt.objects.count(), 1)
        self.assertEqual(self.current().state['restart_history'][0]['item_results']['0']['classification'], 'GREEN')
        progress = self.current()
        progress.current_index = 3
        progress.completed_items = 3
        progress.state = {'current_index': 3}
        progress.save()
        state = reading.state_for(progress)
        self.assertEqual(state['completed_reading_items'], [0, 1, 2])
        self.assertEqual(reading.item_result(state, 0)['classification'], '')
