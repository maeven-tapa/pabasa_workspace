import base64
import json
from unittest.mock import Mock, patch

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.template.loader import render_to_string

from .knowlez_stt import KnowlezSpeechError, transcribe_knowlez_audio
from .views import lesson_1_gawain_1_transcribe_api, reading_transcribe_api


def recording(content=b'browser audio', mime='audio/webm'):
    return SimpleUploadedFile('reading.webm', content, content_type=mime)


@override_settings(AZURE_SPEECH_KEY='private-test-key')
class KnowlezSpeechAdapterTests(SimpleTestCase):
    @patch('pabasa_app.knowlez_stt.requests.post')
    def test_browser_formats_and_locales_are_sent_to_knowlez(self, post):
        post.return_value = Mock(status_code=201)
        post.return_value.json.return_value = {'text': 'Si Bibo ay bata.', 'language': 'tl', 'segments': []}
        for mime in ('audio/webm;codecs=opus', 'audio/ogg', 'audio/mp4', 'audio/wav'):
            for locale in ('fil-PH', 'en-PH'):
                with self.subTest(mime=mime, locale=locale):
                    self.assertEqual(transcribe_knowlez_audio(recording(mime=mime), locale),
                                     ('Si Bibo ay bata.', 'knowlez_stt', ''))
                    args, kwargs = post.call_args
                    self.assertEqual(args[0], 'https://api-stt.knowlez.com/v1/stt/transcribe')
                    self.assertEqual(kwargs['headers']['X-API-Key'], 'private-test-key')
                    self.assertEqual(kwargs['json']['language'], 'tl' if locale == 'fil-PH' else 'en')
                    self.assertEqual(base64.b64decode(kwargs['json']['audio_base64']), b'browser audio')
                    self.assertTrue(kwargs['json']['filename'].startswith('recording.'))
                    self.assertNotIn('audio_url', kwargs['json'])
                    self.assertNotIn('files', kwargs)
                    self.assertEqual(kwargs['timeout'], (5, 25))
                    self.assertFalse(kwargs['allow_redirects'])

    @patch('pabasa_app.knowlez_stt.requests.post')
    def test_configuration_and_clip_validation_prevent_network_requests(self, post):
        with override_settings(AZURE_SPEECH_KEY=''):
            with self.assertRaises(KnowlezSpeechError) as error:
                transcribe_knowlez_audio(recording(), 'fil-PH')
            self.assertEqual(error.exception.status, 503)
        for audio, status in ((recording(b''), 400), (Mock(size=12 * 1024 * 1024 + 1), 413)):
            with self.assertRaises(KnowlezSpeechError) as error:
                transcribe_knowlez_audio(audio, 'fil-PH')
            self.assertEqual(error.exception.status, status)
        post.assert_not_called()

    @patch('pabasa_app.knowlez_stt.requests.post')
    def test_errors_do_not_disclose_provider_details(self, post):
        for status in (302, 400, 401, 403, 429, 500):
            post.return_value = Mock(status_code=status, text='private-test-key')
            with self.subTest(status=status), self.assertRaises(KnowlezSpeechError) as error:
                transcribe_knowlez_audio(recording(), 'fil-PH')
            self.assertNotIn('private-test-key', str(error.exception))
        post.side_effect = requests.Timeout('private-test-key')
        with self.assertRaises(KnowlezSpeechError) as error:
            transcribe_knowlez_audio(recording(), 'fil-PH')
        self.assertNotIn('private-test-key', str(error.exception))

    @patch('pabasa_app.knowlez_stt.requests.post')
    def test_silence_and_invalid_responses(self, post):
        post.return_value = Mock(status_code=201)
        post.return_value.json.return_value = {'text': ''}
        self.assertEqual(transcribe_knowlez_audio(recording(), 'fil-PH')[0], '')
        for data in ({}, None, {'text': None}, {'text': []}, {'text': 12}):
            post.return_value.json.return_value = data
            with self.subTest(data=data), self.assertRaises(KnowlezSpeechError):
                transcribe_knowlez_audio(recording(), 'fil-PH')
        post.return_value.json.side_effect = ValueError('invalid JSON')
        with self.assertRaises(KnowlezSpeechError):
            transcribe_knowlez_audio(recording(), 'fil-PH')


@override_settings(GOOGLE_STT_API_KEY='google-test-key', AZURE_SPEECH_KEY='')
class KnowlezSpeechRoutingTests(SimpleTestCase):
    def setUp(self):
        for name, value in (('_check_auth', True), ('_enforce_student_access_for_request', None)):
            patcher = patch('pabasa_app.views.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, provider='', language='Filipino'):
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': recording(), 'target_text': 'bata', 'language': language,
            'mode': 'reading', 'activity_key': 'lesson-1-gawain-1',
        }, HTTP_X_PABASA_STT_PROVIDER=provider)
        request._dont_enforce_csrf_checks = True
        return request

    @override_settings(GOOGLE_STT_API_KEY='')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model')
    @patch('pabasa_app.views.transcribe_knowlez_audio', return_value=('bata', 'knowlez_stt', ''))
    def test_knowlez_and_legacy_selection_bypass_google_configuration(self, knowlez, google):
        for provider, language, locale in (('azure', 'Filipino', 'fil-PH'), ('knowlez', 'English', 'en-PH')):
            response = reading_transcribe_api(self.request(provider, language))
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertTrue(result['complete'])
            self.assertEqual(result['stt_provider'], 'knowlez')
            self.assertEqual(result['stt_model'], 'knowlez_stt')
            self.assertEqual(knowlez.call_args.args[1], locale)
        google.assert_not_called()

    @patch('pabasa_app.views.transcribe_knowlez_audio')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('bata', 'stt_v1', ''))
    def test_google_is_default_and_restored_when_off(self, google, knowlez):
        for provider in ('', 'google', 'unknown'):
            response = reading_transcribe_api(self.request(provider))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)['stt_provider'], 'google')
        self.assertEqual(google.call_count, 3)
        knowlez.assert_not_called()

    @patch('pabasa_app.views.transcribe_audio_bytes_with_model')
    def test_missing_knowlez_configuration_does_not_fall_back(self, google):
        response = reading_transcribe_api(self.request('azure'))
        self.assertEqual(response.status_code, 503)
        self.assertIn('Knowlez', json.loads(response.content)['error'])
        google.assert_not_called()

    @patch('pabasa_app.views._lesson1_ffmpeg_binary')
    @patch('pabasa_app.views.transcribe_knowlez_audio', return_value=('A B K', 'knowlez_stt', ''))
    def test_lesson_one_uses_knowlez_without_ffmpeg(self, knowlez, ffmpeg):
        response = lesson_1_gawain_1_transcribe_api(self.request('azure'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['raw_transcript'], 'A B K')
        ffmpeg.assert_not_called()

    @patch('pabasa_app.views.transcribe_knowlez_audio')
    def test_authentication_and_student_access_still_apply(self, knowlez):
        from django.http import JsonResponse
        for view in (reading_transcribe_api, lesson_1_gawain_1_transcribe_api):
            with patch('pabasa_app.views._check_auth', return_value=False):
                self.assertEqual(view(self.request('azure')).status_code, 401)
            with patch('pabasa_app.views._enforce_student_access_for_request', return_value=JsonResponse({}, status=403)):
                self.assertEqual(view(self.request('azure')).status_code, 403)
        knowlez.assert_not_called()

    def test_settings_render_without_credentials(self):
        with override_settings(AZURE_SPEECH_KEY='must-not-reach-browser'):
            html = render_to_string('pabasa_app/session1_prescribed_controls.html', {'prefix': 'lesson'})
        self.assertIn('data-prescribed-stt-toggle', html)
        self.assertNotIn('must-not-reach-browser', html)
