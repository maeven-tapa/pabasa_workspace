import json
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from .models import PrescribedReadingAttempt, SchoolCalendar, StudentActivityProgress, StudentActivityRecordingSubmission, User
from .views import prescribed_activity_progress, session_5_lesson_14_gawain_4_recording, teacher_session_5_lesson_14_gawain_4_recordings


@override_settings(MEDIA_ROOT='/tmp/pabasa-e2e-media')
class Session5Gawain4E2ETests(TestCase):
    def setUp(self):
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        self.student = User.objects.create(custom_id='E2E-STUDENT', role='student', first_name='E2E', last_name='Student', sex='X', birth_month=1, birth_day=1, birth_year=2018, email='e2e-student@example.test', password_hash='x', school_calendar=self.calendar)
        self.teacher = User.objects.create(custom_id='E2E-TEACHER', role='teacher', first_name='E2E', last_name='Teacher', sex='X', birth_month=1, birth_day=1, birth_year=1980, email='e2e-teacher@example.test', password_hash='x')
        self.lifecycle = {'state': 'ARAL_ACTIVE', 'school_calendar': self.calendar, 'term': 1}
        self.rf = RequestFactory()

    def _request(self, user, method='post', path='/api/progress/', payload=None, **kwargs):
        if method.lower() == 'post':
            kwargs.setdefault('data', json.dumps(payload or {}))
            kwargs.setdefault('content_type', 'application/json')
        request = getattr(self.rf, method.lower())(path, **kwargs)
        request._dont_enforce_csrf_checks = True
        request.session = {'user_id': user.id, 'user_role': user.role}
        return request

    def test_student_to_teacher_persistence_flow(self):
        key = 'session-5-lesson-14-gawain-4'
        with patch('pabasa_app.views._current_learning_context', return_value=self.lifecycle), patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True):
            self.assertFalse(StudentActivityProgress.objects.filter(student=self.student, activity_key=key).exists())

            started = prescribed_activity_progress(self._request(self.student, payload={'state': {'current_index': 0, 'state_version': 1}}), key)
            self.assertEqual(started.status_code, 200, started.content)
            progress = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
            self.assertEqual(progress.current_index, 0)
            self.assertEqual(progress.school_calendar_id, self.calendar.id)
            self.assertEqual(progress.term, 1)

            skipped = prescribed_activity_progress(self._request(self.student, payload={'action': 'skip', 'item_index': 0, 'state_version': 1}), key)
            skipped_json = json.loads(skipped.content)
            self.assertEqual(skipped.status_code, 200)
            self.assertTrue(skipped_json['success'])
            progress.refresh_from_db()
            self.assertEqual(progress.state['statuses']['0'], 'not_read')
            self.assertEqual(progress.state['fluency_classifications']['0'], 'RED')
            self.assertEqual(progress.state['classification_sources']['0'], 'skipped')
            self.assertEqual(progress.current_index, 1)

            audio = SimpleUploadedFile('reading.webm', b'RIFF-e2e-audio', content_type='audio/webm')
            recording_request = self.rf.post('/api/recording/', data={'item_index': '1', 'transcript': 'buto', 'stt_match': 'true', 'attempt_id': str(uuid.uuid4()), 'audio': audio})
            recording_request.session = {'user_id': self.student.id, 'user_role': 'student'}
            recording_request._dont_enforce_csrf_checks = True
            recording = session_5_lesson_14_gawain_4_recording(recording_request)
            recording_json = json.loads(recording.content)
            self.assertEqual(recording.status_code, 200)
            self.assertTrue(recording_json['success'])
            self.assertEqual(StudentActivityRecordingSubmission.objects.filter(student=self.student, activity_key=key).count(), 1)
            self.assertEqual(PrescribedReadingAttempt.objects.filter(student=self.student, activity_key=key).count(), 1)

            for index in range(1, 22):
                progress.refresh_from_db()
                response = prescribed_activity_progress(self._request(self.student, payload={'action': 'skip', 'item_index': index, 'state_version': progress.state['state_version']}), key)
                self.assertEqual(response.status_code, 200, response.content)

            progress.refresh_from_db()
            self.assertTrue(progress.activity_completed)
            self.assertEqual(progress.current_index, 22)
            self.assertEqual(len(progress.state['classification_sources']), 22)

            with patch('pabasa_app.views._teacher_session4_student_ids', return_value={self.student.id}):
                teacher_request = self._request(self.teacher, method='get', path='/api/teacher/', payload=None, data={'student_id': self.student.id}, HTTP_ACCEPT='application/json')
                teacher_response = teacher_session_5_lesson_14_gawain_4_recordings(teacher_request)
            teacher_json = json.loads(teacher_response.content)
            self.assertEqual(teacher_response.status_code, 200)
            self.assertEqual(len(teacher_json['items']), 22)
            self.assertEqual(teacher_json['activity_status'], 'Completed')
            self.assertEqual(teacher_json['items'][0]['classification'], 'RED')
            self.assertTrue(teacher_json['items'][0]['classification_auto'])
            self.assertEqual(teacher_json['items'][1]['transcript'], 'buto')
            self.assertIsNotNone(teacher_json['items'][1]['recording_url'])
