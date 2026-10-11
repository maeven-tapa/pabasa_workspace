"""L14 G2 speech regressions. Provider responses/audio are simulated."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from google.cloud.speech_v2.types import cloud_speech
from . import crla_stream, reading_stt, views
from .prescribed_activity_catalog import prescribed_activity

KEY = 'lesson-14-gawain-2'


@override_settings(DEBUG=False, GOOGLE_CLOUD_PROJECT_ID='test-project', GOOGLE_STT_MODEL='chirp_3',
                   GOOGLE_STT_LOCATION='us', GOOGLE_STT_API_KEY='test-key')
class Lesson14Gawain2SpeechTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = SessionStore(session_key='a' * 32)
        self.session._session_cache = {'user_id': 1, 'user_role': 'admin'}
        for target, value in [('pabasa_app.views._check_auth', True),
                ('pabasa_app.views._enforce_student_access_for_request', None),
                ('pabasa_app.views.uses_knowlez_stt', False),
                ('pabasa_app.crla_stream.authorize_prescribed', prescribed_activity(KEY)),
                ('pabasa_app.reading_stt.google_stt_credentials', object())]:
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        client = patch('google.cloud.speech_v2.SpeechClient')
        self.client = client.start()
        self.addCleanup(client.stop)

    def request(self, **fields):
        request = self.factory.post('/api/reading/transcribe/', {'target_text': 'mata',
            'language': 'Filipino', 'mode': 'word', 'prescribed_activity_key': KEY,
            'audio': SimpleUploadedFile('clip.webm', b'disposable-audio', 'audio/webm'), **fields},
            HTTP_X_PABASA_STT_MODEL='chirp_3')
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    def recognize(self, transcript, response_language='fil-PH', **fields):
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse(results=[{
            'language_code': response_language, 'alternatives': [{'transcript': transcript}]}])
        response = views.reading_transcribe_api(self.request(**fields))
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def config(self):
        return self.client.return_value.recognize.call_args.kwargs['request'].config

    def test_six_words_have_only_filipino_and_current_word_context(self):
        for item in prescribed_activity(KEY)['items']:
            word = item['word']
            result = self.recognize(word, target_text=word, language='English')
            self.assertTrue(result['complete'])
            self.assertEqual(list(self.config().language_codes), ['fil-PH'])
            self.assertEqual(self.config().model, 'chirp_3')
            hints = self.config().adaptation.phrase_sets[0].inline_phrase_set.phrases
            self.assertEqual([hint.value for hint in hints], [word])
            self.assertEqual(hints[0].boost, 0)
            self.assertEqual(result['stt_response_language_codes'], ['fil-PH'])
            self.assertFalse(result['stt_language_autodetection'])

    def test_latin_segmentation_and_alias_matching_unchanged(self):
        for target, heard in [('mata', 'ma ta'), ('nipa', 'ni pa'), ('tubo', 'tu bo'),
                              ('nota', 'no ta'), ('mata', 'marta'), ('buto', 'butu')]:
            baseline = reading_stt.analyze_reading(target, 0, heard, 'fil-PH')
            result = self.recognize(heard, target_text=target)
            self.assertEqual(result['complete'], baseline['complete'])
            self.assertEqual(result['current_syllable_index'], baseline['current_syllable_index'])
            self.assertEqual(result['raw_transcript'], heard)

    def test_hangul_and_mixed_script_cannot_pass_or_reuse_tass(self):
        for heard in ['마타', 'mata 한국', '한국 mata', 'ma\u1100ta', '\u3131', '\uffa1']:
            result = self.recognize(heard, syllable_context='ma')
            self.assertFalse(result['complete'])
            self.assertFalse(result['matched'])
            self.assertEqual(result['current_syllable_index'], 0)
            self.assertEqual(result['syllable_context'], '')
            self.assertEqual(result['raw_transcript'], heard)
            self.assertEqual(result['recognition_rejected_reason'], 'non_filipino_language')

    def test_guard_closes_confirmed_ascii_normalization_false_positive(self):
        self.assertTrue(reading_stt.analyze_reading('mata', 0, 'mata 한국', 'fil-PH')['complete'])
        self.assertFalse(self.recognize('mata 한국')['complete'])

    def test_provider_language_metadata_is_preserved_not_invented(self):
        result = self.recognize('mata', response_language='ko-KR')
        self.assertFalse(result['complete'])
        self.assertEqual(result['stt_response_language_codes'], ['ko-KR'])
        result = self.recognize('mata', response_language='')
        self.assertTrue(result['complete'])
        self.assertEqual(result['stt_response_language_codes'], [])

    def test_short_fragments_do_not_complete_word_and_retry_passes(self):
        for heard in ['o', 'ya', 'y', 'o ya y', 'ma']:
            self.assertFalse(self.recognize(heard)['complete'])
        self.assertTrue(self.recognize('mata')['complete'])

    def test_unrelated_hints_are_rejected_before_provider_call(self):
        for target in ['o', 'ya', 'y', 'mata unrelated', 'unrelated']:
            self.assertEqual(views.reading_transcribe_api(self.request(target_text=target)).status_code, 400)
        self.client.return_value.recognize.assert_not_called()

    @override_settings(DEBUG=True)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    def test_target_does_not_silently_fall_back_to_v1(self, credentials):
        request = self.request()
        request.META.pop('HTTP_X_PABASA_STT_MODEL')
        request.META['HTTP_HOST'] = 'localhost'
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
        response = views.reading_transcribe_api(request)
        self.assertEqual(json.loads(response.content)['stt_model'], 'chirp_3')
        credentials.assert_not_called()

    def test_explicit_chirp2_and_knowlez_selection_are_preserved(self):
        request = self.request()
        request.META['HTTP_X_PABASA_STT_MODEL'] = 'chirp_2'
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
        self.assertEqual(views.reading_transcribe_api(request).status_code, 200)
        self.assertEqual(self.config().model, 'chirp_2')
        with patch.object(views, 'uses_knowlez_stt', return_value=True), \
                patch.object(views, 'transcribe_knowlez_audio', return_value=('mata', 'knowlez_stt', '')) as provider:
            result = json.loads(views.reading_transcribe_api(self.request()).content)
            self.assertTrue(result['complete'])
            self.assertEqual(result['stt_provider'], 'knowlez')
            self.assertEqual(provider.call_args.args[1], 'fil-PH')

    def ticket(self, **fields):
        request = self.factory.post('/api/reading/prescribed-stream/start/',
            json.dumps({'activity_key': KEY, 'target_text': 'mata', **fields}), content_type='application/json')
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return crla_stream.prescribed_stream_ticket(request)

    def test_stream_ticket_pins_filipino_and_ignores_arbitrary_hint_input(self):
        for language in ['auto', 'English', 'ko-KR', 'Filipino', 'fil-PH']:
            response = self.ticket(language=language, phrase_hints=['unrelated'], target_text='buto')
            self.assertEqual(response.status_code, 200)
            payload = signing.loads(json.loads(response.content)['ticket'], salt=crla_stream.TICKET_SALT)
            self.assertEqual(payload['fields'], {'language': 'fil-PH', 'mode': 'reading',
                'target_text': 'buto', 'recognition_context': ['buto']})
        self.assertEqual(self.ticket(target_text='unrelated').status_code, 400)

    def test_signed_finals_preserve_language_and_cannot_be_used_for_another_word(self):
        payload = signing.loads(json.loads(self.ticket().content)['ticket'], salt=crla_stream.TICKET_SALT)
        token = signing.dumps({**payload, 'transcript': 'mata 한국', 'response_language_codes': ['ko-KR']},
                             salt=crla_stream.PRESCRIBED_RESULT_SALT)
        request = self.request(prescribed_stream_token=token, prescribed_stream_activity=KEY)
        result = json.loads(views.reading_transcribe_api(request).content)
        self.assertFalse(result['complete'])
        self.assertEqual(result['stt_response_language_codes'], ['ko-KR'])
        self.client.return_value.recognize.assert_not_called()
        changed = self.request(target_text='buto', prescribed_stream_token=token, prescribed_stream_activity=KEY)
        self.assertEqual(views.reading_transcribe_api(changed).status_code, 403)

    def test_other_activities_do_not_get_new_hints_or_metadata(self):
        result = self.recognize('mata', prescribed_activity_key='lesson-13-gawain-2')
        self.assertTrue(result['complete'])
        self.assertFalse(cloud_speech.RecognitionConfig.pb(self.config()).HasField('adaptation'))
        self.assertNotIn('stt_response_language_codes', result)

    @override_settings(ALLOWED_HOSTS=['testserver'], CSRF_TRUSTED_ORIGINS=['https://testserver'])
    async def test_stream_request_context_and_signed_response_language(self):
        payload = {'session': crla_stream.session_binding(self.session), 'purpose': 'prescribed',
                   'activity_key': KEY, 'fields': {'language': 'fil-PH', 'mode': 'reading',
                   'target_text': 'mata', 'recognition_context': ['mata']}}
        incoming, output, configs = asyncio.Queue(), [], []
        token = signing.dumps(payload, salt=crla_stream.TICKET_SALT)
        for event in [{'type': 'websocket.connect'},
                      {'type': 'websocket.receive', 'text': json.dumps({'ticket': token})},
                      {'type': 'websocket.receive', 'bytes': b'\0\0' * 3200},
                      {'type': 'websocket.receive', 'text': '{"type":"finish"}'}]:
            await incoming.put(event)
        async def streaming(requests, **kwargs):
            async def responses():
                async for request in requests:
                    if request.streaming_config:
                        configs.append(request.streaming_config.config)
                    else:
                        yield cloud_speech.StreamingRecognizeResponse(results=[{
                            'alternatives': [{'transcript': '마타'}], 'language_code': 'ko-KR', 'is_final': True}])
            return responses()
        client = SimpleNamespace(streaming_recognize=streaming, transport=SimpleNamespace(close=AsyncMock()))
        async def send(message):
            output.append(message)
        with patch.object(crla_stream, 'socket_session', return_value=self.session), \
                patch.object(crla_stream, 'speech_credentials', return_value=None), \
                patch('google.cloud.speech_v2.SpeechAsyncClient', return_value=client):
            await asyncio.wait_for(crla_stream.crla_websocket({'path': crla_stream.STREAM_PATH,
                'headers': [(b'origin', b'https://testserver'), (b'host', b'testserver')]}, incoming.get, send), 3)
        self.assertEqual(list(configs[0].language_codes), ['fil-PH'])
        self.assertEqual(configs[0].model, 'chirp_3')
        self.assertEqual([p.value for p in configs[0].adaptation.phrase_sets[0].inline_phrase_set.phrases], ['mata'])
        messages = [json.loads(message['text']) for message in output if message['type'] == 'websocket.send']
        result = signing.loads(messages[-1]['result_token'], salt=crla_stream.PRESCRIBED_RESULT_SALT)
        self.assertEqual(result['response_language_codes'], ['ko-KR'])
        self.assertEqual(result['transcript'], '마타')
