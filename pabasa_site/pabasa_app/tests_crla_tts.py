import base64
from email.message import Message
from io import BytesIO
import json
import socket
import urllib.error
from unittest.mock import ANY, MagicMock, patch

from django.http import JsonResponse
from django.core.cache import cache
from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from .elevenlabs_tts import (
    CRLA_TTS_VOICE_ID, _cooldown_cache_key, normalize_api_keys, synthesize_crla_read_aloud_audio,
)
from .reading_stt import synthesize_read_aloud_audio
from .views import reading_read_aloud_api


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'crla-tts-tests',
}})
class CrlaTeacherVoiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def audio_response(self, audio=b'ID3-test-audio', content_type='audio/mpeg'):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = Message()
        response.headers['Content-Type'] = content_type
        response.read.return_value = audio
        return response

    @patch('pabasa_app.reading_stt._post_google_tts')
    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_crla_uses_alice_v4_language_delivery_tags_and_settings(self, urlopen, google):
        self.assertEqual(CRLA_TTS_VOICE_ID, 'Xb7hH8MSUJpSbSDYk0k2')
        urlopen.return_value = self.audio_response()
        for language, expected in (('fil-PH', 'fil'), ('tl-PH', 'fil'), ('en-PH', 'en')):
            with self.subTest(language=language):
                result = synthesize_read_aloud_audio(
                    '  Si Bibo ay bata.  Ano ang ginagawa niya? ', 'google-key',
                    language_code=language, tts_profile='crla', voice_gender='MALE',
                    elevenlabs_api_key='test-elevenlabs-key',
                )
                request = urlopen.call_args.args[0]
                self.assertEqual(request.full_url,
                    f'https://api.elevenlabs.io/v1/text-to-speech/{CRLA_TTS_VOICE_ID}?output_format=mp3_44100_128')
                self.assertEqual(request.get_method(), 'POST')
                self.assertEqual(request.get_header('Xi-api-key'), 'test-elevenlabs-key')
                self.assertGreater(urlopen.call_args.kwargs['timeout'], 0)
                self.assertLessEqual(urlopen.call_args.kwargs['timeout'], 20)
                payload = json.loads(request.data)
                self.assertEqual(payload['text'],
                    '[filipino teacher accent][slow][Cheerful and Encouraging] '
                    'Si Bibo ay bata. Ano ang ginagawa niya?')
                self.assertEqual(payload['language_code'], expected)
                self.assertEqual(payload['model_id'], 'eleven_v4')
                self.assertEqual(payload['voice_settings'], {'stability': 0.5, 'similarity_boost': 0.75})
                self.assertEqual(base64.b64decode(result), b'ID3-test-audio')
        google.assert_not_called()

    @patch('pabasa_app.reading_stt._post_google_tts', return_value='audio')
    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_other_profiles_keep_existing_voice_and_rates(self, elevenlabs, google):
        synthesize_read_aloud_audio('Magandang araw.', 'test-key', language_code='fil-PH')
        payload = google.call_args.args[1]
        self.assertEqual(payload['voice']['name'], 'fil-PH-Wavenet-A')
        self.assertIn('rate="92%"', payload['input']['ssml'])
        self.assertEqual(payload['audioConfig']['speakingRate'], 0.95)
        elevenlabs.assert_not_called()

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_invalid_inputs_do_not_call_provider(self, provider):
        for text, key, language, message in (
            ('   ', 'key', 'fil-PH', 'Text is required'),
            ('Bibo', '  ', 'fil-PH', 'ELEVENLABS_API_KEY'),
            ('Bibo', 'key', 'es-ES', 'Filipino and English'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                synthesize_crla_read_aloud_audio(text, key, language)
        provider.assert_not_called()

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_http_errors_do_not_expose_body_or_credentials(self, provider):
        for status in (401, 403, 404, 429, 500):
            with self.subTest(status=status):
                cache.clear()
                provider.side_effect = urllib.error.HTTPError(
                    'https://api.elevenlabs.io', status, 'Failure', {},
                    BytesIO(b'{"detail":"private-reading-text secret-key"}'),
                )
                with self.assertRaisesRegex(RuntimeError, f'ElevenLabs TTS HTTP {status}') as error:
                    synthesize_crla_read_aloud_audio('Bibo', 'secret-key', 'fil-PH')
                self.assertNotIn('private-reading-text', str(error.exception))
                self.assertNotIn('secret-key', str(error.exception))
                self.assertTrue(error.exception.__suppress_context__)

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_network_errors_are_retryable_messages(self, provider):
        for failure in (urllib.error.URLError('private detail'), socket.timeout('timeout')):
            with self.subTest(failure=type(failure).__name__):
                cache.clear()
                provider.side_effect = failure
                with self.assertRaisesRegex(RuntimeError, 'Unable to reach ElevenLabs'):
                    synthesize_crla_read_aloud_audio('Bibo', 'key', 'fil-PH')

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_empty_and_non_audio_responses_fail(self, provider):
        for audio, content_type, message in (
            (b'', 'audio/mpeg', 'no audio'),
            (b'{"detail":"error"}', 'application/json', 'invalid audio'),
        ):
            with self.subTest(message=message):
                cache.clear()
                provider.return_value = self.audio_response(audio, content_type)
                with self.assertRaisesRegex(RuntimeError, message):
                    synthesize_crla_read_aloud_audio('Bibo', 'key', 'fil-PH')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'crla-key-failover-tests',
}})
class CrlaKeyFailoverTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def error(self, status, code='', modern=False):
        body = {'code': code} if modern else {'detail': {'status': code, 'message': 'private text'}}
        return urllib.error.HTTPError('https://api.elevenlabs.io', status, 'Failure', {},
            BytesIO(json.dumps(body).encode()))

    def audio_response(self):
        return CrlaTeacherVoiceTests().audio_response()

    def used_keys(self, provider):
        return [call.args[0].get_header('Xi-api-key') for call in provider.call_args_list]

    def test_key_pool_parsing_preserves_order_and_removes_blank_duplicates(self):
        self.assertEqual(normalize_api_keys('first, second\nfirst\tthird , '), ('first', 'second', 'third'))
        self.assertEqual(normalize_api_keys((' first ', '', 'second', 'first')), ('first', 'second'))
        self.assertEqual(normalize_api_keys(''), ())

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_quota_failure_tries_next_key_for_both_error_formats(self, provider):
        for status, modern in ((400, False), (401, False), (402, True)):
            with self.subTest(status=status, modern=modern):
                cache.clear()
                provider.reset_mock()
                provider.side_effect = [self.error(status, 'quota_exceeded', modern), self.audio_response()]
                result = synthesize_crla_read_aloud_audio('Pito', ('first', 'second', 'third'), 'fil-PH')
                self.assertEqual(base64.b64decode(result), b'ID3-test-audio')
                self.assertEqual(self.used_keys(provider), ['first', 'second'])
                first, second = [call.args[0] for call in provider.call_args_list]
                self.assertEqual(first.data, second.data)
                self.assertEqual(first.full_url, second.full_url)
                self.assertTrue(cache.get(_cooldown_cache_key('first')))

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_failed_credentials_voice_access_and_rate_limit_try_next(self, provider):
        for status, code in ((401, 'invalid_api_key'), (403, 'missing_permissions'),
                             (404, 'voice_not_found'), (429, 'concurrent_limit_exceeded'),
                             (400, 'voice_not_found')):
            with self.subTest(status=status, code=code):
                cache.clear()
                provider.reset_mock()
                provider.side_effect = [self.error(status, code), self.audio_response()]
                synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
                self.assertEqual(self.used_keys(provider), ['first', 'second'])

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_exhausted_key_is_skipped_on_next_request_and_can_recover(self, provider):
        provider.side_effect = [self.error(401, 'quota_exceeded'), self.audio_response(), self.audio_response()]
        synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
        synthesize_crla_read_aloud_audio('Binti', ['first', 'second'], 'fil-PH')
        self.assertEqual(self.used_keys(provider), ['first', 'second', 'second'])
        cache.delete(_cooldown_cache_key('first'))
        provider.side_effect = None
        provider.return_value = self.audio_response()
        synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
        self.assertEqual(self.used_keys(provider)[-1], 'first')

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_all_keys_fail_without_exposing_credentials(self, provider):
        keys = ['private-first-key', 'private-second-key', 'private-third-key']
        provider.side_effect = [self.error(401, 'quota_exceeded') for _ in keys]
        with self.assertRaisesRegex(RuntimeError, 'All configured ElevenLabs keys') as error:
            synthesize_crla_read_aloud_audio('Pito', keys, 'fil-PH')
        self.assertEqual(self.used_keys(provider), keys)
        for key in keys:
            self.assertNotIn(key, str(error.exception))
            self.assertNotIn(key, _cooldown_cache_key(key))
        self.assertNotIn('private text', str(error.exception))
        # Every key is cooling down; a new request sends no provider calls.
        provider.reset_mock()
        with self.assertRaisesRegex(RuntimeError, 'All configured ElevenLabs keys'):
            synthesize_crla_read_aloud_audio('Pito', keys, 'fil-PH')
        provider.assert_not_called()

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_validation_and_account_restriction_errors_do_not_rotate(self, provider):
        for status, code in ((400, 'max_character_limit_exceeded'), (422, 'validation_error'),
                             (401, 'detected_unusual_activity')):
            with self.subTest(status=status, code=code):
                cache.clear()
                provider.reset_mock()
                provider.side_effect = [self.error(status, code), self.audio_response()]
                with self.assertRaises(RuntimeError):
                    synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
                self.assertEqual(self.used_keys(provider), ['first'])
                self.assertIsNone(cache.get(_cooldown_cache_key('first')))

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_network_service_and_invalid_audio_failures_try_next(self, provider):
        empty = CrlaTeacherVoiceTests().audio_response(b'')
        invalid = CrlaTeacherVoiceTests().audio_response(b'{}', 'application/json')
        for failure in (socket.timeout(), urllib.error.URLError('private reason'),
                        self.error(503, 'system_busy'), empty, invalid):
            with self.subTest(failure=type(failure).__name__):
                cache.clear()
                provider.reset_mock()
                provider.side_effect = [failure, self.audio_response()]
                result = synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
                self.assertEqual(base64.b64decode(result), b'ID3-test-audio')
                self.assertEqual(self.used_keys(provider), ['first', 'second'])

    @patch('pabasa_app.elevenlabs_tts.time.monotonic', side_effect=[0, 1, 61])
    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen', side_effect=socket.timeout())
    def test_failover_stops_starting_requests_after_time_budget(self, provider, _clock):
        with self.assertRaisesRegex(RuntimeError, 'All configured ElevenLabs keys'):
            synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
        self.assertEqual(self.used_keys(provider), ['first'])
        self.assertEqual(provider.call_args.kwargs['timeout'], 20)

    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_quota_and_rate_limit_have_different_cooldowns(self, provider):
        for status, code, seconds in ((401, 'quota_exceeded', 900), (429, 'rate_limit_exceeded', 30)):
            with self.subTest(code=code):
                cache.clear()
                provider.side_effect = [self.error(status, code), self.audio_response()]
                with patch('pabasa_app.elevenlabs_tts.cache.set', wraps=cache.set) as mark_failed:
                    synthesize_crla_read_aloud_audio('Pito', ['first', 'second'], 'fil-PH')
                    mark_failed.assert_called_once_with(_cooldown_cache_key('first'), True, timeout=seconds)


@override_settings(ELEVENLABS_API_KEY='test-elevenlabs-key', ELEVENLABS_API_KEYS=(), CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'crla-tts-api-tests',
}})
class CrlaReadAloudApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def request(self, text='Si Bibo ay bata.', **fields):
        request = RequestFactory().post('/api/reading/read-aloud/', {
            'target_text': text, 'language': 'Filipino', 'mode': 'paragraph',
            'tts_profile': 'crla', **fields,
        })
        request._dont_enforce_csrf_checks = True
        return request

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    @override_settings(GOOGLE_STT_API_KEY='')
    def test_endpoint_synthesizes_using_only_the_server_elevenlabs_key(self, provider, _access, _auth):
        provider.return_value = CrlaTeacherVoiceTests().audio_response()
        response = reading_read_aloud_api(self.request())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(base64.b64decode(data['audio_content']), b'ID3-test-audio')
        self.assertEqual(provider.call_args.args[0].get_header('Xi-api-key'), 'test-elevenlabs-key')
        self.assertEqual(json.loads(provider.call_args.args[0].data)['text'],
            '[filipino teacher accent][slow][Cheerful and Encouraging] Si Bibo ay bata.')
        self.assertEqual(data['voice_id'], CRLA_TTS_VOICE_ID)

    @override_settings(ELEVENLABS_API_KEYS=('private-first', 'private-second'))
    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.elevenlabs_tts.urllib.request.urlopen')
    def test_endpoint_uses_pool_before_legacy_key_and_fails_over(self, provider, _access, _auth):
        provider.side_effect = [CrlaKeyFailoverTests().error(401, 'quota_exceeded'),
                                CrlaTeacherVoiceTests().audio_response()]
        response = reading_read_aloud_api(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([call.args[0].get_header('Xi-api-key') for call in provider.call_args_list],
                         ['private-first', 'private-second'])
        self.assertNotIn('private-first', response.content.decode())
        self.assertNotIn('private-second', response.content.decode())
        self.assertEqual(json.loads(response.content)['voice_id'], CRLA_TTS_VOICE_ID)

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='audio')
    def test_all_crla_stages_report_actual_provider_and_voice(self, synthesize, _access, _auth):
        for mode, text in (('word', 'pito'), ('sentence', 'Si Bibo ay bata.'),
                           ('paragraph', 'Si Bibo ay bata.'), ('paragraph', 'Ano ang ginagawa ni Bibo?')):
            for language, locale in (('Filipino', 'fil-PH'), ('English', 'en-US')):
                with self.subTest(mode=mode, language=language):
                    response = reading_read_aloud_api(self.request(text, mode=mode, language=language))
                    self.assertEqual(response.status_code, 200)
                    data = json.loads(response.content)
                    self.assertEqual(data['tts_language'], locale)
                    self.assertEqual(data['voice_name'], CRLA_TTS_VOICE_ID)
                    self.assertEqual(data['voice_id'], CRLA_TTS_VOICE_ID)
                    self.assertEqual(data['tts_provider'], 'elevenlabs')
                    self.assertEqual(data['model_id'], 'eleven_v4')
                    self.assertNotIn('test-elevenlabs-key', response.content.decode())
                    synthesize.assert_called_with(text, ANY, ANY, credentials_file=ANY,
                        tts_profile='crla', elevenlabs_api_key='test-elevenlabs-key')

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='audio')
    def test_non_crla_assessment_preserves_previous_pace(self, synthesize, _access, _auth):
        response = reading_read_aloud_api(self.request('Magandang araw.', tts_profile='assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['voice_name'], 'fil-PH-Wavenet-A')
        synthesize.assert_called_once_with('Magandang araw.', ANY, 'fil-PH', credentials_file=ANY,
                                          speaking_rate=1.0, prosody_rate='100%')

    @override_settings(ELEVENLABS_API_KEY='')
    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.logger')
    @patch('pabasa_app.reading_stt._post_google_tts')
    def test_missing_key_fails_without_google_fallback(self, google, _logger, _access, _auth):
        response = reading_read_aloud_api(self.request())
        self.assertEqual(response.status_code, 502)
        self.assertFalse(json.loads(response.content)['success'])
        self.assertIn('ELEVENLABS_API_KEY', json.loads(response.content)['error'])
        google.assert_not_called()

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', side_effect=RuntimeError('ElevenLabs TTS HTTP 429'))
    @patch('pabasa_app.views.logger')
    def test_provider_failure_returns_no_successful_audio(self, _logger, _synthesize, _access, _auth):
        response = reading_read_aloud_api(self.request())
        self.assertEqual(response.status_code, 502)
        self.assertFalse(json.loads(response.content)['success'])
        self.assertNotIn('audio_content', json.loads(response.content))

    @patch('pabasa_app.views._check_auth', return_value=False)
    @patch('pabasa_app.views.synthesize_read_aloud_audio')
    def test_authentication_still_required(self, synthesize, _auth):
        self.assertEqual(reading_read_aloud_api(self.request()).status_code, 401)
        synthesize.assert_not_called()

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request')
    @patch('pabasa_app.views.synthesize_read_aloud_audio')
    def test_student_access_denial_still_blocks_provider(self, synthesize, access, _auth):
        access.return_value = JsonResponse({'success': False}, status=403)
        self.assertEqual(reading_read_aloud_api(self.request()).status_code, 403)
        synthesize.assert_not_called()

    def test_csrf_still_required(self):
        response = Client(enforce_csrf_checks=True).post('/api/reading/read-aloud/', {
            'target_text': 'pito', 'tts_profile': 'crla',
        })
        self.assertEqual(response.status_code, 403)
