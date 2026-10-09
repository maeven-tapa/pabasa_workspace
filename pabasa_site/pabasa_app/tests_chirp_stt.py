import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.template.loader import render_to_string
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.exceptions import InternalServerError, InvalidArgument, ServiceUnavailable

from .reading_stt import transcribe_audio_bytes_with_model, transcribe_audio_bytes_v1, v1_model_for_language
from .views import lesson_1_gawain_1_transcribe_api, reading_transcribe_api


class ChirpAdapterTests(SimpleTestCase):
    def setUp(self):
        credentials = patch('pabasa_app.reading_stt.google_stt_credentials', return_value=object())
        credentials.start()
        self.addCleanup(credentials.stop)
        client = patch('google.cloud.speech_v2.SpeechClient')
        self.client = client.start()
        self.addCleanup(client.stop)

    def transcribe(self, model='chirp_2', **kwargs):
        return transcribe_audio_bytes_with_model(
            b'audio', 'test-key', language_code=kwargs.pop('language_code', 'fil-PH'), model=model,
            project_id='test-project', location='us-central1' if model == 'chirp_2' else 'us',
            **kwargs,
        )

    def test_transient_provider_failure_retries_identical_audio_and_model(self):
        recognize = self.client.return_value.recognize
        provider_error = InternalServerError('500 Internal server error')
        # Google wraps an underlying gRPC error as the exception cause.
        provider_error.__cause__ = RuntimeError('transport details')
        recognize.side_effect = [provider_error,
            cloud_speech.RecognizeResponse(results=[{'alternatives': [{'transcript': 'bata'}]}])]
        self.assertEqual(self.transcribe('chirp_3'), ('bata', 'chirp_3', ''))
        self.assertEqual(recognize.call_count, 2)
        first, second = recognize.call_args_list
        self.assertEqual(first.kwargs['request'], second.kwargs['request'])
        self.assertEqual(first.kwargs['request'].content, b'audio')
        self.assertIsNone(first.kwargs['retry'])

    def test_provider_retries_are_bounded_and_do_not_retry_bad_audio(self):
        recognize = self.client.return_value.recognize
        for error, attempts in ((ServiceUnavailable('busy'), 2), (InvalidArgument('invalid audio'), 1)):
            with self.subTest(error=type(error).__name__):
                recognize.reset_mock()
                recognize.side_effect = error
                words = [{'word': 'stale'}]
                with self.assertRaises(type(error)):
                    self.transcribe('chirp_3', word_details=words)
                self.assertEqual(recognize.call_count, attempts)
                self.assertEqual(words, [])

    def test_chirp2_requests_word_values_and_keeps_all_segments(self):
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse(results=[
            {'alternatives': [{'transcript': 'bata', 'words': [
                {'word': 'bata', 'confidence': 0.84, 'start_offset': '0.200s', 'end_offset': '0.700s'},
            ]}]},
            {'alternatives': []},
            {'alternatives': [{'transcript': 'ako', 'words': [{'word': 'ako'}]}]},
        ])
        words = []
        self.assertEqual(self.transcribe(word_details=words), ('bata ako', 'chirp_2', ''))
        request = self.client.return_value.recognize.call_args.kwargs['request']
        self.assertEqual(request.config.model, 'chirp_2')
        self.assertTrue(request.config.features.enable_word_confidence)
        self.assertTrue(request.config.features.enable_word_time_offsets)
        self.assertEqual(list(request.config.language_codes), ['fil-PH'])
        self.assertEqual(request.recognizer, 'projects/test-project/locations/us-central1/recognizers/_')
        self.assertEqual(self.client.call_args.kwargs['client_options'].api_endpoint,
                         'us-central1-speech.googleapis.com')
        self.assertEqual([w['word'] for w in words], ['bata', 'ako'])
        self.assertAlmostEqual(words[0]['confidence'], 0.84, places=6)
        self.assertEqual(words[0]['start_seconds'], 0.2)
        self.assertEqual(words[0]['end_seconds'], 0.7)
        self.assertIsNone(words[1]['confidence'])

    def test_chirp3_does_not_request_unsupported_confidence(self):
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse(
            results=[{'alternatives': [{'transcript': 'bata'}]}])
        words = []
        self.assertEqual(self.transcribe('chirp_3', word_details=words), ('bata', 'chirp_3', ''))
        config = self.client.return_value.recognize.call_args.kwargs['request'].config
        self.assertEqual(config.model, 'chirp_3')
        self.assertFalse(config.features.enable_word_confidence)
        self.assertEqual(words, [])

    @patch('pabasa_app.reading_stt.transcribe_audio_bytes_v1')
    def test_filipino_default_has_no_adaptation_or_fallback(self, v1):
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
        self.assertEqual(self.transcribe('', phrase_hints=['bata']), ('', 'chirp_3', ''))
        config = self.client.return_value.recognize.call_args.kwargs['request'].config
        self.assertEqual(config.model, 'chirp_3')
        self.assertFalse(cloud_speech.RecognitionConfig.pb(config).HasField('adaptation'))
        self.client.return_value.recognize.side_effect = RuntimeError('Unavailable region')
        with self.assertRaisesRegex(RuntimeError, 'Unavailable region'):
            self.transcribe('', phrase_hints=['bata'])
        v1.assert_not_called()

    @patch('pabasa_app.reading_stt._post_google_stt', return_value='bata')
    def test_legacy_filipino_request_ignores_phrase_hints(self, post):
        transcribe_audio_bytes_v1(b'audio', 'test-key', 'fil-PH', ['bata'], '', 'audio/webm')
        payload = post.call_args.args[1]
        self.assertNotIn('speechContexts', payload['config'])

    @patch('pabasa_app.reading_stt.transcribe_audio_bytes_v1')
    def test_explicit_model_failure_and_silence_never_fall_back(self, v1):
        for model in ('chirp_2', 'chirp_3'):
            with self.subTest(model=model):
                self.client.return_value.recognize.side_effect = RuntimeError('Unavailable region')
                with self.assertRaisesRegex(RuntimeError, 'Unavailable region'):
                    self.transcribe(model, allow_fallback=False)
                self.client.return_value.recognize.side_effect = None
                self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
                self.assertEqual(self.transcribe(model, allow_fallback=False), ('', model, ''))
        v1.assert_not_called()

    @patch('pabasa_app.reading_stt.transcribe_audio_bytes_v1', return_value='bata')
    def test_default_fallback_retains_reason_and_has_no_chirp_word_values(self, v1):
        self.client.return_value.recognize.side_effect = RuntimeError('Unavailable region')
        words = [{'word': 'stale', 'confidence': 1}]
        self.assertEqual(self.transcribe(language_code='en-PH', word_details=words),
                         ('bata', 'stt_v1', 'Unavailable region'))
        self.assertEqual(words, [])
        self.assertEqual(v1.call_args.args[4], 'command_and_search')
        self.assertEqual(v1_model_for_language('chirp_2', 'en-PH'), 'command_and_search')


@override_settings(GOOGLE_STT_API_KEY='', GOOGLE_CLOUD_PROJECT_ID='test-project',
                   GOOGLE_STT_LOCATION='us', GOOGLE_STT_CHIRP2_LOCATION='asia-southeast1')
class ChirpRoutingTests(SimpleTestCase):
    def setUp(self):
        for name, value in (('_check_auth', True), ('_enforce_student_access_for_request', None)):
            patcher = patch('pabasa_app.views.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, model, language='Filipino'):
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': SimpleUploadedFile('clip.webm', b'audio', content_type='audio/webm'),
            'target_text': 'bata', 'language': language, 'mode': 'reading',
            'activity_key': 'lesson-1-gawain-1',
        }, HTTP_X_PABASA_STT_PROVIDER='google', HTTP_X_PABASA_STT_MODEL=model)
        request._dont_enforce_csrf_checks = True
        return request

    @patch('pabasa_app.views._lesson1_ffmpeg_binary')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model')
    def test_both_routes_honor_chirp_selection_and_expose_word_values(self, transcribe, ffmpeg):
        def recognize(*args, **kwargs):
            if kwargs['model'] == 'chirp_2':
                kwargs['word_details'].append({'word': 'bata', 'confidence': 0.84})
            return 'bata', kwargs['model'], ''
        transcribe.side_effect = recognize
        for view in (reading_transcribe_api, lesson_1_gawain_1_transcribe_api):
            for model in ('chirp_2', 'chirp_3'):
                for language in ('Filipino', 'English'):
                    with self.subTest(view=view.__name__, model=model, language=language):
                        response = view(self.request(model, language))
                        self.assertEqual(response.status_code, 200)
                        result = json.loads(response.content)
                        self.assertEqual(result['stt_model'], model)
                        self.assertEqual(result['stt_provider'], 'google')
                        self.assertEqual(result['stt_word_confidence_type'],
                                         'provider_value_not_confidence' if model == 'chirp_2' else 'unavailable')
                        if model == 'chirp_2':
                            self.assertEqual(result['stt_words'][0]['confidence'], 0.84)
                        else:
                            self.assertEqual(result['stt_words'], [])
                        options = transcribe.call_args.kwargs
                        self.assertFalse(options['allow_fallback'])
                        self.assertEqual(options['location'], 'asia-southeast1' if model == 'chirp_2' else 'us')
        ffmpeg.assert_not_called()

    @patch('pabasa_app.views.uses_knowlez_stt', return_value=True)
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('bata', 'chirp_3', ''))
    def test_official_crla_forces_google_chirp3_over_saved_preferences(self, transcribe, knowlez):
        request = self.request('chirp_2', language='English')
        request.POST = request.POST.copy()
        request.POST['official_crla_assessment'] = '1'

        response = reading_transcribe_api(request)

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result['stt_provider'], 'google')
        self.assertEqual(result['stt_model'], 'chirp_3')
        self.assertEqual(transcribe.call_args.kwargs['model'], 'chirp_3')
        self.assertFalse(transcribe.call_args.kwargs['allow_fallback'])
        knowlez.assert_not_called()

    @override_settings(GOOGLE_STT_API_KEY='test-key')
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('bata', 'chirp_3', ''))
    def test_filipino_defaults_to_chirp3_without_hints_or_fallback(self, transcribe):
        for view in (reading_transcribe_api, lesson_1_gawain_1_transcribe_api):
            for model in ('', 'arbitrary-model'):
                with self.subTest(view=view.__name__, model=model):
                    response = view(self.request(model))
                    self.assertEqual(response.status_code, 200)
                    options = transcribe.call_args.kwargs
                    self.assertEqual(options['model'], 'chirp_3')
                    self.assertEqual(options['location'], 'us')
                    self.assertFalse(options.get('phrase_hints'))
                    self.assertFalse(options['allow_fallback'])

    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=RuntimeError('Chirp unavailable'))
    def test_explicit_model_error_is_reported(self, transcribe):
        for view in (reading_transcribe_api, lesson_1_gawain_1_transcribe_api):
            with self.assertLogs('pabasa_app.views', level='ERROR'):
                response = view(self.request('chirp_2'))
            self.assertEqual(response.status_code, 502)
            self.assertEqual(json.loads(response.content)['error'], 'Chirp unavailable')

    def test_shared_settings_render_both_models(self):
        html = render_to_string('pabasa_app/includes/prescribed_stt_settings.html')
        self.assertIn('value="chirp_2"', html)
        self.assertIn('value="chirp_3"', html)
        self.assertIn('value="knowlez"', html)
