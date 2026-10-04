import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .reading_stt import analyze_reading
from .views import reading_transcribe_api


@override_settings(
    GOOGLE_STT_API_KEY='test-key',
    GOOGLE_CLOUD_PROJECT_ID='test-project',
    GOOGLE_STT_MODEL='chirp_3',
    GOOGLE_STT_CREDENTIALS_FILE='missing-service-account.json',
)
class LocalSttFallbackTests(SimpleTestCase):
    def request(self, host='127.0.0.1', headers=None, target='heard'):
        data = {
            'audio': SimpleUploadedFile('reading.webm', b'recorded-audio', content_type='audio/webm'),
            'target_text': target,
            'language': 'Filipino',
            'mode': 'reading',
        }
        request = RequestFactory().post('/api/reading/transcribe/', data, HTTP_HOST=host, **(headers or {}))
        request._dont_enforce_csrf_checks = True
        return request

    def setUp(self):
        self.auth = patch('pabasa_app.views._check_auth', return_value=True)
        self.access = patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
        self.auth.start()
        self.access.start()
        self.addCleanup(self.auth.stop)
        self.addCleanup(self.access.stop)

    @override_settings(DEBUG=True)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('heard', 'stt_v1', ''))
    def test_local_missing_credentials_selects_real_api_key_fallback(self, transcribe, credentials):
        response = reading_transcribe_api(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['complete'])
        self.assertEqual(transcribe.call_args.kwargs['model'], 'latest_short')
        credentials.assert_called_once()

    @override_settings(DEBUG=False)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('heard', 'chirp_3', ''))
    def test_production_does_not_select_local_fallback(self, transcribe, credentials):
        response = reading_transcribe_api(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(transcribe.call_args.kwargs['model'], 'chirp_3')
        credentials.assert_not_called()

    @override_settings(DEBUG=True)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=True)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('heard', 'chirp_3', ''))
    def test_service_account_credentials_keep_chirp_authoritative(self, transcribe, credentials):
        response = reading_transcribe_api(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(transcribe.call_args.kwargs['model'], 'chirp_3')
        credentials.assert_called_once()

    @override_settings(DEBUG=True)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('heard', 'chirp_3', ''))
    def test_explicit_chirp_selection_is_preserved(self, transcribe, credentials):
        response = reading_transcribe_api(self.request(headers={'HTTP_X_PABASA_STT_MODEL': 'chirp_3'}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(transcribe.call_args.kwargs['model'], 'chirp_3')
        credentials.assert_not_called()

    @override_settings(DEBUG=True, GOOGLE_STT_API_KEY='')
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=RuntimeError('provider unavailable'))
    def test_missing_api_key_does_not_claim_success(self, transcribe, credentials):
        response = reading_transcribe_api(self.request())

        self.assertGreaterEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content).get('success', False))
        self.assertEqual(transcribe.call_args.kwargs['model'], 'chirp_3')
        credentials.assert_not_called()

    def test_existing_matcher_behavior_remains_unchanged(self):
        correct = analyze_reading('bata', 0, 'bata', 'fil-PH')
        incorrect = analyze_reading('bata', 0, 'mali', 'fil-PH')

        self.assertTrue(correct['complete'])
        self.assertFalse(incorrect['complete'])
