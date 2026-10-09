import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from . import crla_stream, views


class CrlaStreamingTests(SimpleTestCase):
    """Preview transport and scoring must not write or even query the database here."""

    def setUp(self):
        self.factory = RequestFactory()
        self.session = SessionStore(session_key='a' * 32)
        self.session._session_cache = {'user_id': 1, 'user_role': 'admin'}
        self.material = SimpleNamespace(pk=12, language='Filipino', assessment_kind='crla')
        self.fields = {'official_assessment_id': '12', 'official_crla_assessment': '1',
                       'target_text': 'bata', 'mode': 'word', 'language': 'Filipino',
                       'crla_rhymes': '0', 'crla_sentence_word_scoring': '0', 'crla_story_reading': '0'}

    def request(self, data):
        request = self.factory.post('/api/reading/crla-stream/evaluate/', json.dumps(data), content_type='application/json')
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    def final(self, transcript='bata', fields=None, session=None):
        return signing.dumps({'session': crla_stream.session_binding(session or self.session),
                              'fields': fields or self.fields, 'transcript': transcript, 'id': 'stream:1'},
                             salt=crla_stream.FINAL_SALT)

    def test_start_binds_original_material_without_student_input_or_copy(self):
        request = self.request({'material_id': 12, 'mode': 'word', 'target_text': 'bata'})
        with patch.object(crla_stream, 'authorize', return_value=self.material) as authorize:
            response = crla_stream.crla_stream_ticket(request)
        result = json.loads(response.content)
        ticket = signing.loads(result['ticket'], salt=crla_stream.TICKET_SALT)
        self.assertEqual(ticket['fields']['official_assessment_id'], '12')
        self.assertEqual(ticket['fields']['language'], 'Filipino')
        self.assertEqual(result['path'], '/ws/reading/crla/')
        self.assertEqual(set(ticket), {'session', 'fields'})
        authorize.assert_called_once_with(request, 12)

    def test_ticket_requires_csrf(self):
        request = self.request({'material_id': 12, 'mode': 'word', 'target_text': 'bata'})
        request._dont_enforce_csrf_checks = False
        self.assertEqual(crla_stream.crla_stream_ticket(request).status_code, 403)

    @override_settings(CRLA_STREAMING_ENABLED=False)
    def test_disabled_streaming_leaves_clip_fallback_available(self):
        self.assertEqual(crla_stream.crla_stream_ticket(self.request({})).status_code, 503)

    def test_rejects_inactive_or_wrong_role(self):
        for user in (None, SimpleNamespace(is_archived=True),
                     SimpleNamespace(is_archived=False, account_status='active', role='student')):
            with patch.object(views, '_current_user', return_value=user):
                with self.assertRaises(PermissionError):
                    crla_stream.authorize(self.request({}), 12)

    def test_rejects_unpublished_or_non_crla_material(self):
        user = SimpleNamespace(is_archived=False, account_status='active', role='admin')
        with patch.object(views, '_current_user', return_value=user):
            for material in (None, SimpleNamespace(assessment_kind='regular')):
                with patch.object(views, '_admin_published_crla', return_value=material):
                    with self.assertRaises(PermissionError):
                        crla_stream.authorize(self.request({}), 12)

    def test_revoked_student_access_is_enforced(self):
        request = self.request({})
        request.session._session_cache['user_role'] = 'student'
        user = SimpleNamespace(is_archived=False, account_status='active', role='student')
        with patch.object(views, '_current_user', return_value=user), \
                patch.object(views, '_admin_published_crla', return_value=self.material), \
                patch.object(views, '_enforce_student_access_for_request', return_value=SimpleNamespace(status_code=403)):
            with self.assertRaises(PermissionError):
                crla_stream.authorize(request, 12)

    def test_foreign_session_cannot_use_signed_final(self):
        other = SessionStore(session_key='b' * 32)
        self.assertEqual(crla_stream.crla_stream_evaluate(self.request({'final_token': self.final(session=other)})).status_code, 403)

    def test_unsigned_browser_transcript_cannot_be_scored(self):
        self.assertEqual(crla_stream.crla_stream_evaluate(self.request({'final_token': 'forged', 'transcript': 'bata'})).status_code, 403)

    def test_expired_final_cannot_be_scored(self):
        with patch('django.core.signing.time.time', return_value=100):
            token = self.final()
        with patch('django.core.signing.time.time', return_value=500):
            self.assertEqual(crla_stream.crla_stream_evaluate(self.request({'final_token': token})).status_code, 403)

    def test_stream_and_clip_share_word_rhyme_sentence_and_story_analysis(self):
        cases = [
            ('word', 'bata', 'bata', {}),
            ('word', 'bata', 'bato', {}),
            ('word', 'tatay', 'ta tay', {'crla_rhymes': '1'}),
            ('sentence', 'Si Bibo ay bata.', 'Si Bibo', {'crla_sentence_word_scoring': '1'}),
            ('paragraph', 'Si Bibo ay bata.', 'Si Bibo ay bata.', {'crla_story_reading': '1'}),
            ('paragraph', "May iba't-ibang tao.", 'May ibat-ibang tao.', {'crla_story_reading': '1'}),
            ('paragraph', "May iba't-ibang tao.", 'May ibat ibang tao.', {'crla_story_reading': '1'}),
        ]
        for mode, target, transcript, flags in cases:
            fields = {**self.fields, 'mode': mode, 'target_text': target, **flags}
            with self.subTest(mode=mode, transcript=transcript), \
                    patch.object(crla_stream, 'authorize', return_value=self.material), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                    patch.object(views, 'transcribe_audio_bytes_with_model', return_value=(transcript, 'chirp_3', '')) as provider:
                clip = self.factory.post('/api/reading/transcribe/', {
                    **fields, 'audio': SimpleUploadedFile('clip.webm', b'audio', 'audio/webm')})
                clip.session = self.session
                clip._dont_enforce_csrf_checks = True
                expected = json.loads(views.reading_transcribe_api(clip).content)
                provider.reset_mock()
                result = json.loads(crla_stream.crla_stream_evaluate(self.request({
                    'final_token': self.final(transcript, fields), 'transcript': 'FORGED',
                    'target_text': 'FORGED', 'prescribed_activity_key': 'lesson-16-gawain-3',
                })).content)
                provider.assert_not_called()
                self.assertEqual(result, expected)
                if "iba't-ibang" in target:
                    self.assertEqual(result['word_alignment']['correct_words'], 3)
                    self.assertEqual(result['word_alignment']['miscues'], 0)
                    self.assertTrue(result['complete'])
                    self.assertEqual(result['current_word_index'], 3)
                    self.assertEqual(result['raw_transcript'], transcript)

    def test_sentence_self_correction_uses_prior_shared_results(self):
        fields = {**self.fields, 'mode': 'sentence', 'target_text': 'Si Bibo ay bata.', 'crla_sentence_word_scoring': '1'}
        with patch.object(crla_stream, 'authorize', return_value=self.material), \
                patch.object(views, '_enforce_student_access_for_request', return_value=None):
            first = json.loads(crla_stream.crla_stream_evaluate(self.request({'final_token': self.final('Si Bibo', fields)})).content)
            second = json.loads(crla_stream.crla_stream_evaluate(self.request({
                'final_token': self.final('ay bata', fields), 'sentence_word_results': first['word_results'],
                'current_syllable_index': first['current_syllable_index'],
            })).content)
        self.assertTrue(second['complete'])
        self.assertEqual(second['correct_word_count'], 4)

    @override_settings(ALLOWED_HOSTS=['testserver'], CSRF_TRUSTED_ORIGINS=['https://testserver'])
    async def test_websocket_only_finalizes_signed_provider_results_and_closes_client(self):
        from google.cloud.speech_v2.types import cloud_speech
        incoming = asyncio.Queue()
        output = []
        token = signing.dumps({'session': crla_stream.session_binding(self.session), 'fields': self.fields}, salt=crla_stream.TICKET_SALT)
        for event in ({'type': 'websocket.connect'},
                      {'type': 'websocket.receive', 'text': json.dumps({'ticket': token})},
                      {'type': 'websocket.receive', 'bytes': b'\0\0' * 3200},
                      {'type': 'websocket.receive', 'text': '{"type":"finish"}'}):
            await incoming.put(event)
        configs = []

        class Provider:
            def __init__(self, **kwargs):
                self.transport = SimpleNamespace(close=AsyncMock())

            async def streaming_recognize(self, requests, **kwargs):
                async def responses():
                    async for request in requests:
                        if request.streaming_config:
                            configs.append(request.streaming_config)
                        else:
                            yield cloud_speech.StreamingRecognizeResponse(results=[{
                                'alternatives': [{'transcript': 'ba'}], 'is_final': False}])
                            yield cloud_speech.StreamingRecognizeResponse(results=[{
                                'alternatives': [{'transcript': 'bata'}], 'is_final': True}])
                return responses()

        client = Provider()
        async def send(message):
            output.append(message)
        scope = {'path': crla_stream.STREAM_PATH, 'headers': [(b'origin', b'https://testserver'), (b'host', b'testserver')]}
        with patch.object(crla_stream, 'socket_session', return_value=self.session), \
                patch.object(crla_stream, 'authorize', return_value=self.material), \
                patch.object(crla_stream, 'speech_credentials', return_value=None), \
                patch('google.cloud.speech_v2.SpeechAsyncClient', return_value=client):
            await asyncio.wait_for(crla_stream.crla_websocket(scope, incoming.get, send), 3)
        messages = [json.loads(message['text']) for message in output if message['type'] == 'websocket.send']
        self.assertEqual([m['type'] for m in messages], ['ready', 'interim', 'final', 'finished'])
        self.assertNotIn('final_token', messages[1])
        final = signing.loads(messages[2]['final_token'], salt=crla_stream.FINAL_SALT)
        self.assertEqual(final['transcript'], 'bata')
        self.assertEqual(final['fields']['official_assessment_id'], '12')
        self.assertEqual(configs[0].config.model, 'chirp_3')
        self.assertEqual(list(configs[0].config.language_codes), ['fil-PH'])
        self.assertTrue(configs[0].streaming_features.interim_results)
        self.assertEqual(configs[0].config.explicit_decoding_config.sample_rate_hertz, 16000)
        client.transport.close.assert_awaited_once()

    async def test_foreign_origin_is_rejected_before_accept_or_google(self):
        messages = []
        async def send(message):
            messages.append(message)
        with patch('google.cloud.speech_v2.SpeechAsyncClient') as provider:
            await crla_stream.crla_websocket({'path': crla_stream.STREAM_PATH,
                'headers': [(b'origin', b'https://evil.example'), (b'host', b'testserver')]}, AsyncMock(), send)
        provider.assert_not_called()
        self.assertEqual(messages, [{'type': 'websocket.close', 'code': 1008}])

    async def test_invalid_ticket_never_opens_provider(self):
        incoming = asyncio.Queue()
        for event in ({'type': 'websocket.connect'}, {'type': 'websocket.receive', 'text': '{"ticket":"forged"}'}):
            await incoming.put(event)
        output = []
        async def send(message):
            output.append(message)
        with override_settings(CSRF_TRUSTED_ORIGINS=['https://testserver']), \
                patch.object(crla_stream, 'socket_session', return_value=self.session), \
                patch('google.cloud.speech_v2.SpeechAsyncClient') as provider:
            await crla_stream.crla_websocket({'path': crla_stream.STREAM_PATH,
                'headers': [(b'origin', b'https://testserver')]}, incoming.get, send)
        provider.assert_not_called()
        self.assertEqual(json.loads(output[1]['text'])['type'], 'error')
