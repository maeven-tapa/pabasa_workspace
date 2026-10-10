"""Prescribed streaming uses authenticated finals and the existing graders."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from . import crla_stream, views


class PrescribedStreamingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = SessionStore(session_key='a' * 32)
        self.session._session_cache = {'user_id': 1, 'user_role': 'admin'}
        self.key = 'lesson-13-gawain-3'
        self.payload = {'session': crla_stream.session_binding(self.session), 'purpose': 'prescribed',
                        'activity_key': self.key, 'fields': {'language': 'fil-PH', 'mode': 'reading'}}

    def start(self, **fields):
        request = self.factory.post('/api/reading/prescribed-stream/start/',
                                    json.dumps({'activity_key': self.key, **fields}), content_type='application/json')
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    def clip(self, transcript='Si Bibo ay bata.', *, payload=None, token=None, path='/api/reading/transcribe/', **fields):
        if token is None:
            token = signing.dumps({**(payload or self.payload), 'transcript': transcript}, salt=crla_stream.PRESCRIBED_RESULT_SALT)
        request = self.factory.post(path, {
            'audio': SimpleUploadedFile('reading.webm', b'audio', 'audio/webm'),
            'target_text': 'Si Bibo ay bata.', 'mode': 'sentence', 'language': 'Filipino',
            'prescribed_stream_token': token, 'prescribed_stream_activity': self.key, **fields,
        })
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    @override_settings(GOOGLE_STT_MODEL='chirp_3')
    def test_ticket_has_recognition_context_but_no_grading_or_write_flags(self):
        request = self.start(language='English', official_crla_assessment='1', target_text='FORGED')
        with patch.object(crla_stream, 'authorize_prescribed', return_value={}):
            result = json.loads(crla_stream.prescribed_stream_ticket(request).content)
        payload = signing.loads(result['ticket'], salt=crla_stream.TICKET_SALT)
        self.assertEqual(payload['fields'], {'language': 'en-PH', 'mode': 'reading'})
        self.assertEqual(payload['activity_key'], self.key)
        self.assertEqual(payload['purpose'], 'prescribed')

    def test_ticket_requires_csrf_and_rejects_invalid_language(self):
        request = self.start()
        request._dont_enforce_csrf_checks = False
        self.assertEqual(crla_stream.prescribed_stream_ticket(request).status_code, 403)
        with patch.object(crla_stream, 'authorize_prescribed', return_value={}):
            self.assertEqual(crla_stream.prescribed_stream_ticket(self.start(language='unknown')).status_code, 400)

    @override_settings(CRLA_STREAMING_ENABLED=False)
    def test_disabled_streaming_uses_clip_path(self):
        self.assertEqual(crla_stream.prescribed_stream_ticket(self.start()).status_code, 503)

    def test_explicit_provider_selection_is_preserved(self):
        for header, value in [('X-Pabasa-STT-Provider', 'knowlez'), ('X-Pabasa-STT-Model', 'chirp_2')]:
            request = self.start()
            request.META['HTTP_' + header.upper().replace('-', '_')] = value
            with patch.object(crla_stream, 'authorize_prescribed', return_value={}):
                self.assertEqual(crla_stream.prescribed_stream_ticket(request).status_code, 409)

    def test_access_checks_preserve_activity_and_student_lifecycle_boundaries(self):
        request = self.start()
        user = SimpleNamespace(is_archived=False, account_status='active', role='student')
        self.session._session_cache['user_role'] = 'student'
        with patch.object(views, '_current_user', return_value=user):
            with self.assertRaises(PermissionError):
                crla_stream.authorize_prescribed(request, 'unknown')
            with patch.object(views, '_student_can_open_prescribed_activity', return_value=False):
                with self.assertRaises(PermissionError):
                    crla_stream.authorize_prescribed(request, self.key)
            with patch.object(views, '_student_can_open_prescribed_activity', return_value=True):
                self.assertTrue(crla_stream.authorize_prescribed(request, self.key))

    def test_signed_utterances_share_clip_verdicts_for_aliases_sentences_and_exact_rhymes(self):
        cases = [
            ('bata', 'bata', {'mode': 'reading'}),
            ('bata', 'bato', {'mode': 'reading'}),
            ('tatay', 'ta tay', {'mode': 'reading', 'salitang_magkatugma_exact': '1'}),
            ('Si Bibo ay bata.', 'Si Bibo', {'mode': 'sentence'}),
            ('Si Bibo ay bata.', 'Si Bibo ay bata.', {'mode': 'sentence'}),
            ('salamin ni Ana', 'salamin ni Anna', {'mode': 'reading', 'prescribed_activity_key': 'session-5-lesson-14-gawain-4'}),
            ('tsek', 'check', {'mode': 'reading', 'prescribed_activity_key': 'session-7-lesson-20-21-gawain-1'}),
        ]
        for target, transcript, fields in cases:
            key = fields.get('prescribed_activity_key', self.key)
            with self.subTest(target=target, transcript=transcript), \
                    patch.object(crla_stream, 'authorize_prescribed', return_value={}), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                    patch.object(views, 'transcribe_audio_bytes_with_model', return_value=(transcript, 'chirp_3', '')) as provider:
                clip = self.clip(transcript, target_text=target, **fields)
                clip.POST = clip.POST.copy()
                clip.POST.pop('prescribed_stream_token')
                expected = json.loads(views.reading_transcribe_api(clip).content)
                provider.reset_mock()
                streamed = self.clip(transcript, payload={**self.payload, 'activity_key': key},
                                     prescribed_stream_activity=key, target_text=target, **fields)
                result = json.loads(views.reading_transcribe_api(streamed).content)
                provider.assert_not_called()
                self.assertEqual(result, expected)

    def test_forged_expired_foreign_or_changed_context_never_calls_any_provider(self):
        with patch('django.core.signing.time.time', return_value=100):
            expired = signing.dumps({**self.payload, 'transcript': 'bata'}, salt=crla_stream.PRESCRIBED_RESULT_SALT)
        cases = [self.clip(token='forged'), self.clip(token=expired), self.clip(transcript=''),
                 self.clip(payload={**self.payload, 'session': 'foreign'}),
                 self.clip(prescribed_stream_activity='other'),
                 self.clip(prescribed_activity_key='other'), self.clip(language='English'),
                 self.clip(official_crla_assessment='1'),
                 self.clip(path='/api/dashboard/assessment/activity/prescribed/other/progress/')]
        knowlez = self.clip()
        knowlez.META['HTTP_X_PABASA_STT_PROVIDER'] = 'knowlez'
        cases.append(knowlez)
        for request in cases:
            with patch.object(crla_stream, 'authorize_prescribed', return_value={}), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                    patch.object(views, 'transcribe_audio_bytes_with_model') as google, \
                    patch.object(views, 'transcribe_knowlez_audio') as knowlez:
                self.assertEqual(views.reading_transcribe_api(request).status_code, 403)
                google.assert_not_called()
                knowlez.assert_not_called()

    def test_revoked_access_rechecked_when_final_is_used(self):
        with patch.object(crla_stream, 'authorize_prescribed', side_effect=PermissionError), \
                patch.object(views, '_enforce_student_access_for_request', return_value=None):
            self.assertEqual(views.reading_transcribe_api(self.clip()).status_code, 403)

    def test_english_final_retains_language_and_existing_word_alias_verdict(self):
        with patch.object(crla_stream, 'authorize_prescribed', return_value={}), \
                patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                patch.object(views, 'transcribe_audio_bytes_with_model') as provider:
            request = self.clip('math', payload={**self.payload, 'fields': {'language': 'en-PH', 'mode': 'reading'}},
                                target_text='mat', language='English', mode='reading')
            response = views.reading_transcribe_api(request)
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result['language_code'], 'en-PH')
        self.assertTrue(result['complete'])
        self.assertEqual(result['stt_model'], 'chirp_3')
        provider.assert_not_called()

    @override_settings(ALLOWED_HOSTS=['testserver'], CSRF_TRUSTED_ORIGINS=['https://testserver'])
    async def test_socket_signs_complete_final_sequence_only_after_flush(self):
        from google.cloud.speech_v2.types import cloud_speech
        incoming = asyncio.Queue()
        output, configs = [], []
        token = signing.dumps(self.payload, salt=crla_stream.TICKET_SALT)
        for event in ({'type': 'websocket.connect'},
                      {'type': 'websocket.receive', 'text': json.dumps({'ticket': token})},
                      {'type': 'websocket.receive', 'bytes': b'\0\0' * 3200},
                      {'type': 'websocket.receive', 'text': '{"type":"finish"}'}):
            await incoming.put(event)

        class Provider:
            def __init__(self, **kwargs):
                self.transport = SimpleNamespace(close=AsyncMock())

            async def streaming_recognize(self, requests, **kwargs):
                async def responses():
                    async for request in requests:
                        if request.streaming_config:
                            configs.append(request.streaming_config.config)
                        else:
                            for text, final in [('FORGED INTERIM', False), ('Si Bibo', True), ('ay bata.', True)]:
                                yield cloud_speech.StreamingRecognizeResponse(results=[{
                                    'alternatives': [{'transcript': text}], 'is_final': final}])
                return responses()

        client = Provider()
        async def send(message):
            output.append(message)
        with patch.object(crla_stream, 'socket_session', return_value=self.session), \
                patch.object(crla_stream, 'authorize_prescribed', return_value={}), \
                patch.object(crla_stream, 'speech_credentials', return_value=None), \
                patch('google.cloud.speech_v2.SpeechAsyncClient', return_value=client):
            await asyncio.wait_for(crla_stream.crla_websocket(
                {'path': crla_stream.STREAM_PATH,
                 'headers': [(b'origin', b'https://testserver'), (b'host', b'testserver')]},
                incoming.get, send), 3)
        messages = [json.loads(message['text']) for message in output if message['type'] == 'websocket.send']
        self.assertEqual([message['type'] for message in messages], ['ready', 'interim', 'interim', 'interim', 'finished'])
        result = signing.loads(messages[-1]['result_token'], salt=crla_stream.PRESCRIBED_RESULT_SALT)
        self.assertEqual(result['transcript'], 'Si Bibo ay bata.')
        self.assertTrue(messages[-1]['has_speech'])
        self.assertEqual(configs[0].language_codes, ['fil-PH'])
        self.assertEqual(configs[0].model, 'chirp_3')
        client.transport.close.assert_awaited_once()
