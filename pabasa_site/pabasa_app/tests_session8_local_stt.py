import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import School, Section, StudentActivityProgress, User
from .prescribed_test_fixtures import prescribed_term_fixture
from .reading_stt import l22_c_pronunciation_match


class Session8LocalSttEndpointTests(SimpleTestCase):
    key = 'aral-l22-g1-c-syllable-builder'

    def request(self, *, host='127.0.0.1', key=None, local_mode=None):
        data = {
            'audio': SimpleUploadedFile('reading.webm', b'recorded-audio', content_type='audio/webm'),
            'target_text': 'cactus',
            'language': 'English',
            'mode': 'reading',
            'prescribed_activity_key': key or self.key,
            'l22_c_pronunciation': '1',
            'l22_c_syllable': 'cac',
            'l22_c_sound': 'hard',
        }
        if local_mode is not None:
            data['local_stt_test'] = local_mode
        request = RequestFactory().post('/api/reading/transcribe/', data, HTTP_HOST=host)
        request._dont_enforce_csrf_checks = True
        return request

    def setUp(self):
        self.auth = patch('pabasa_app.views._check_auth', return_value=True)
        self.access = patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
        self.auth.start()
        self.access.start()
        self.addCleanup(self.auth.stop)
        self.addCleanup(self.access.stop)

    @override_settings(DEBUG=True, GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model')
    def test_local_correct_transcript_uses_real_lesson22_matching(self, transcribe):
        from .views import reading_transcribe_api

        response = reading_transcribe_api(self.request(local_mode='correct'))
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(result['complete'])
        self.assertEqual(result['raw_transcript'], 'cactus')
        self.assertEqual(result['stt_provider'], 'local_test')
        transcribe.assert_not_called()
        self.assertTrue(l22_c_pronunciation_match('cac', 'cactus', result['raw_transcript'], 'hard'))

    @override_settings(DEBUG=True, GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=RuntimeError('Google STT unavailable'))
    def test_local_flag_is_ignored_for_adjacent_activity(self, transcribe):
        from .views import reading_transcribe_api

        response = reading_transcribe_api(self.request(key='aral-l23-g6-q-syllable-builder', local_mode='correct'))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(json.loads(response.content)['error'], 'Hindi magamit ang mikropono ngayon. Subukan muli mamaya.')
        transcribe.assert_called_once()

    @override_settings(DEBUG=False, GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=RuntimeError('Google STT unavailable'))
    def test_production_ignores_client_supplied_local_flag(self, transcribe):
        from .views import reading_transcribe_api

        response = reading_transcribe_api(self.request(local_mode='correct'))
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(result['error_code'], 'speech_service_unavailable')
        self.assertEqual(result['error'], 'Hindi makakonekta sa pagbasa. Subukan muli.')
        transcribe.assert_called_once()


class Session8LocalSttProgressTests(TestCase):
    key = 'aral-l22-g1-c-syllable-builder'

    def setUp(self):
        active_session = patch('pabasa_app.middleware.student_session_is_active', return_value=True)
        active_session.start()
        self.addCleanup(active_session.stop)
        school = School.objects.create(name='Local STT School', code='LSTT')
        self.student = User.objects.create(
            custom_id='LSTT-STUDENT', role='student', first_name='Test', last_name='Student',
            email='local-stt@example.com', password_hash='test', sex='N/A',
            birth_month=1, birth_day=1, birth_year=2016, school_record=school,
        )
        teacher = User.objects.create(
            custom_id='LSTT-TEACHER', role='teacher', first_name='Test', last_name='Teacher',
            email='local-stt-teacher@example.com', password_hash='test', sex='N/A',
            birth_month=1, birth_day=1, birth_year=1990, school_record=school,
        )
        section = Section.objects.create(
            school=school, class_code='LSTT-1', class_name='Local STT', subject='Reading',
            teacher=teacher, is_active=True,
        )
        section.add_student(self.student)
        prescribed_term_fixture(self.student, teacher=teacher, section=section)
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.client.defaults['HTTP_HOST'] = '127.0.0.1'
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})

    def post_event(self, payload, *, audio=False):
        if audio:
            payload = {
                **payload,
                'audio': SimpleUploadedFile('reading.webm', b'recorded-audio', content_type='audio/webm'),
            }
        return self.client.post(self.progress_url, payload)

    def start_reading(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.key}))
        state = page.context['workbook_payload']['state']
        response = self.post_event({'action': 'reading_started', 'revision': state['revision']})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['state']

    @override_settings(DEBUG=True, GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model')
    def test_real_progress_route_forwards_key_and_local_transcript_advances_once(self, transcribe):
        state = self.start_reading()
        response = self.post_event({
            'action': 'reading_syllable_attempt', 'revision': state['revision'],
            'local_stt_test': 'correct',
        }, audio=True)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result['stt_provider'], 'local_test')
        self.assertEqual(result['state']['index'], 1)
        self.assertEqual(result['state']['reading_attempts'], 0)
        transcribe.assert_not_called()

    @override_settings(DEBUG=True, GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=RuntimeError('Google STT unavailable'))
    def test_service_failure_returns_502_without_apply_event_or_progress_change(self, transcribe):
        state = self.start_reading()
        with patch('pabasa_app.prescribed_workbook.apply_event') as apply_event:
            response = self.post_event({'action': 'reading_syllable_attempt', 'revision': state['revision']}, audio=True)
        result = response.json()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(result['error_code'], 'speech_service_unavailable')
        apply_event.assert_not_called()
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual(progress.state['index'], state['index'])
        self.assertEqual(progress.state['reading_attempts'], state['reading_attempts'])

    @patch('pabasa_app.views.reading_transcribe_api', return_value=None)
    def test_valid_incorrect_transcript_keeps_existing_retry_behavior(self, transcribe):
        from django.http import JsonResponse

        transcribe.return_value = JsonResponse({'success': True, 'transcript': 'wrong', 'complete': False})
        state = self.start_reading()
        response = self.post_event({'action': 'reading_syllable_attempt', 'revision': state['revision']}, audio=True)
        self.assertEqual(response.status_code, 200, response.content)
        updated = response.json()['state']
        self.assertEqual(updated['index'], state['index'])
        self.assertEqual(updated['reading_attempts'], 1)
        self.assertEqual(updated['last_feedback'], 'Subukan muli.')
