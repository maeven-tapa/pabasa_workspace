"""Signed supplementary/practice transport shares the existing reading rules."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from . import crla_stream, views


class MaterialStreamingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = SessionStore(session_key='a' * 32)
        self.session._session_cache = {'user_id': 1, 'user_role': 'student'}
        self.material = SimpleNamespace(pk=12, language='Filipino', content_json={})
        self.fields = {'material_id': '12', 'target_text': 'bata', 'mode': 'word', 'language': 'Filipino'}

    def request(self, data, json_body=True):
        request = self.factory.post('/api/reading/material-stream/start/',
                                    json.dumps(data) if json_body else data,
                                    **({'content_type': 'application/json'} if json_body else {}))
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    def payload(self, **kwargs):
        return {'session': crla_stream.session_binding(self.session), 'purpose': 'practice',
                'material_id': '12', 'fields': self.fields, 'complete_utterance': True,
                'transcript': 'bata', **kwargs}

    def token(self, **kwargs):
        return signing.dumps(self.payload(**kwargs), salt=crla_stream.MATERIAL_RESULT_SALT)

    def test_ticket_locks_material_language_and_keeps_official_flags_out(self):
        for purpose in ('practice', 'supplementary'):
            with self.subTest(purpose=purpose), patch.object(crla_stream, 'authorize_material', return_value=self.material):
                result = json.loads(crla_stream.material_stream_ticket(self.request({
                    'material_id': 'practice-12', 'purpose': purpose, 'mode': 'word',
                    'language': 'English', 'target_text': 'bata', 'complete_utterance': True,
                    'official_crla_assessment': '1', 'prescribed_activity_key': 'lesson-16-gawain-3',
                })).content)
                ticket = signing.loads(result['ticket'], salt=crla_stream.TICKET_SALT)
                self.assertEqual(ticket['fields'], self.fields)
                self.assertEqual(ticket['purpose'], purpose)

    def test_invalid_provider_and_csrf_do_not_open_stream(self):
        data = {'material_id': 12, 'purpose': 'practice', 'mode': 'word', 'target_text': 'bata'}
        for header, value in (('HTTP_X_PABASA_STT_PROVIDER', 'knowlez'), ('HTTP_X_PABASA_STT_MODEL', 'chirp_2')):
            request = self.request(data)
            request.META[header] = value
            with patch.object(crla_stream, 'authorize_material', return_value=self.material):
                self.assertEqual(crla_stream.material_stream_ticket(request).status_code, 409)
        request = self.request(data)
        request._dont_enforce_csrf_checks = False
        self.assertEqual(crla_stream.material_stream_ticket(request).status_code, 403)

    @override_settings(CRLA_STREAMING_ENABLED=False)
    def test_disabled_streaming_uses_clip_path(self):
        self.assertEqual(crla_stream.material_stream_ticket(self.request({})).status_code, 503)

    def test_completed_transcript_matches_clip_evaluation_without_second_provider_call(self):
        for mode, target, transcript in (('word', 'bata', 'bata'),
                                         ('sentence', 'Si Bibo ay bata.', 'Si Bibo ay bata.'),
                                         ('paragraph', 'Si Bibo ay bata.', 'Si Bibo ay bata.')):
            fields = {**self.fields, 'mode': mode, 'target_text': target}
            with self.subTest(mode=mode), patch.object(crla_stream, 'authorize_material', return_value=self.material), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                    patch.object(views, 'transcribe_audio_bytes_with_model', return_value=(transcript, 'chirp_3', '')) as provider:
                audio = SimpleUploadedFile('clip.webm', b'audio', 'audio/webm')
                expected = json.loads(views.reading_transcribe_api(self.request({**fields, 'audio': audio}, False)).content)
                provider.reset_mock()
                actual = json.loads(views.reading_transcribe_api(self.request({**fields,
                    'audio': SimpleUploadedFile('clip.webm', b'audio', 'audio/webm'),
                    'material_stream_token': self.token(fields=fields, transcript=transcript)}, False)).content)
                self.assertEqual(actual, expected)
                provider.assert_not_called()

    def test_rejects_changed_target_language_material_session_and_provider(self):
        for changes in ({'target_text': 'pusa'}, {'mode': 'sentence'}, {'material_id': '13'},
                        {'language': 'English'}, {'official_crla_assessment': '1'},
                        {'prescribed_activity_key': 'lesson-16-gawain-3'}):
            with self.subTest(changes=changes), patch.object(crla_stream, 'authorize_material', return_value=self.material), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None):
                result = views.reading_transcribe_api(self.request({**self.fields, **changes,
                    'audio': SimpleUploadedFile('clip.webm', b'audio', 'audio/webm'),
                    'material_stream_token': self.token()}, False))
                self.assertEqual(result.status_code, 403)
        for changes in ({'session': 'other'}, {'transcript': ''}, {'purpose': 'prescribed'}):
            request = self.request({'material_stream_token': self.token(**changes)}, False)
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                crla_stream.material_stream_transcript(request, 12, 'bata', 'word', 'fil-PH')
        request = self.request({'material_stream_token': self.token()}, False)
        request.META['HTTP_X_PABASA_STT_PROVIDER'] = 'knowlez'
        with patch.object(crla_stream, 'authorize_material', return_value=self.material), self.assertRaises(PermissionError):
            crla_stream.material_stream_transcript(request, 12, 'bata', 'word', 'fil-PH')

    def test_publication_is_rechecked_at_evaluation_and_socket_start(self):
        with patch.object(crla_stream, 'authorize_material', side_effect=PermissionError('revoked')):
            request = self.request({'material_stream_token': self.token()}, False)
            with self.assertRaises(PermissionError):
                crla_stream.material_stream_transcript(request, 12, 'bata', 'word', 'fil-PH')
            ticket = signing.dumps(self.payload(), salt=crla_stream.TICKET_SALT)
            with self.assertRaises(PermissionError):
                crla_stream.validate_socket_ticket(ticket, self.session)

    def test_authorization_rejects_wrong_class_teacher_and_locked_practice(self):
        material = SimpleNamespace(pk=12, section_id=3, source_type='template', content_json={}, difficulty_level='hard')
        user = SimpleNamespace(role='student', is_archived=False, account_status='active')
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = material
        query.exists.return_value = False
        with patch.object(views, '_current_user', return_value=user), \
                patch.object(views.Material.objects, 'filter', return_value=query), \
                patch.object(views, '_is_official_crla_material', return_value=False), \
                patch.object(views, '_is_supplementary_material', return_value=False), \
                patch.object(views.Enrollment.objects, 'filter', return_value=query):
            with self.assertRaisesRegex(PermissionError, 'class'):
                crla_stream.authorize_material(self.request({}), 12, 'supplementary')
        self.session['user_role'] = 'teacher'
        user.role = 'teacher'
        with patch.object(views, '_current_user', return_value=user), \
                patch.object(views.Material.objects, 'filter', return_value=query), \
                patch.object(views, '_is_official_crla_material', return_value=False), \
                patch.object(views, '_teacher_can_access_material', return_value=False):
            with self.assertRaises(PermissionError):
                crla_stream.authorize_material(self.request({}), 12, 'supplementary')
        self.session['user_role'] = 'student'
        user.role = 'student'
        with patch.object(views, '_current_user', return_value=user), \
                patch.object(views, '_systemwide_practice_queryset', return_value=query), \
                patch.object(views, '_practice_difficulty_is_accessible', return_value=False):
            with self.assertRaisesRegex(PermissionError, 'level'):
                crla_stream.authorize_material(self.request({}), 12, 'practice')
        self.session['teacher_access_mode'] = True
        with patch.object(views, '_current_user', return_value=user), self.assertRaisesRegex(PermissionError, 'teacher access'):
            crla_stream.authorize_material(self.request({}), 12, 'practice')

    def test_supplementary_requires_current_aral_lifecycle(self):
        material = SimpleNamespace(pk=12, source_type='template')
        user = SimpleNamespace(role='student', is_archived=False, account_status='active')
        query = MagicMock()
        query.first.return_value = material
        with patch.object(views, '_current_user', return_value=user), \
                patch.object(views.Material.objects, 'filter', return_value=query), \
                patch.object(views, '_is_official_crla_material', return_value=False), \
                patch.object(views, '_is_supplementary_material', return_value=True), \
                patch.object(views, '_current_supplementary_lifecycle_guard', return_value=object()):
            with self.assertRaises(PermissionError):
                crla_stream.authorize_material(self.request({}), 12, 'supplementary')

    def test_word_decoding_consumes_signed_result_without_uploading_to_provider_again(self):
        material = SimpleNamespace(pk=12, language='Filipino', content_json={'items': [{'word': 'bata'}]})
        query = MagicMock()
        query.first.return_value = material
        request = self.request({'material_id': '12', 'target_word': 'bata',
            'audio': SimpleUploadedFile('clip.webm', b'audio', 'audio/webm'),
            'material_stream_token': self.token(purpose='supplementary')}, False)
        with patch.object(views.Material.objects, 'filter', return_value=query), \
                patch.object(views, '_is_word_decoding_material', return_value=True), \
                patch.object(views, '_enforce_student_access_for_request', return_value=None), \
                patch.object(crla_stream, 'authorize_material', return_value=material), \
                patch.object(views, 'transcribe_audio_bytes_with_model') as provider:
            result = json.loads(views.word_decoding_transcribe_api(request).content)
        self.assertEqual(result, {'success': True, 'transcript': 'bata', 'stt_model': 'chirp_3'})
        provider.assert_not_called()

    def test_fluency_stream_preserves_clip_scoring_and_one_result_write(self):
        fields = {**self.fields, 'language': 'English', 'mode': 'paragraph', 'target_text': 'The cat sat.'}
        material = SimpleNamespace(pk=12, language='English', content_json={'passage': 'The cat sat.'},
                                   record_assessment_result=MagicMock())
        query = MagicMock()
        query.first.return_value = SimpleNamespace(pk=1, role='student', is_archived=False, account_status='active',
                                                  preference={})
        query.get.return_value = material
        attempts = []
        for streamed in (False, True):
            material.record_assessment_result.reset_mock()
            request = self.request({'material_id': '12', 'duration_seconds': '30',
                'audio': SimpleUploadedFile('clip.webm', b'audio', 'audio/webm'),
                **({'material_stream_token': self.token(purpose='supplementary', fields=fields,
                                                        transcript='The cat sat.')} if streamed else {})}, False)
            with patch.object(views, '_aral_request_material', return_value=material), \
                    patch.object(views.User.objects, 'filter', return_value=query), \
                    patch.object(views.Material.objects, 'select_for_update', return_value=query), \
                    patch.object(views.transaction, 'atomic'), \
                    patch.object(views, '_student_can_complete_assessment', return_value=True), \
                    patch.object(views, '_fluency_reading_completed_result', side_effect=[None, None, object()]), \
                    patch.object(views, '_serialize_aral_result', return_value={}), \
                    patch.object(crla_stream, 'authorize_material', return_value=material), \
                    patch.object(views, 'transcribe_audio_bytes_with_model', return_value=('The cat sat.', 'chirp_3', '')) as provider:
                response = views.aral_template_activity_complete(request, 'fluency-reading')
            self.assertEqual(response.status_code, 200)
            material.record_assessment_result.assert_called_once()
            attempts.append(material.record_assessment_result.call_args.kwargs)
            if streamed:
                provider.assert_not_called()
            else:
                provider.assert_called_once()
        self.assertEqual(attempts[0], attempts[1])
        self.assertEqual(attempts[1]['wpm'], 6.0)
        self.assertEqual(attempts[1]['accuracy'], 100.0)

    def test_live_final_uses_generic_rules_and_rejects_official_token(self):
        for purpose, status in (('supplementary', 200), ('practice', 200), ('prescribed', 403), ('official', 403)):
            token = signing.dumps(self.payload(purpose=purpose, complete_utterance=False), salt=crla_stream.FINAL_SALT)
            with self.subTest(purpose=purpose), patch.object(crla_stream, 'authorize_material', return_value=self.material), \
                    patch.object(views, '_enforce_student_access_for_request', return_value=None):
                response = crla_stream.material_stream_evaluate(self.request({'final_token': token, 'target_text': 'FORGED'}))
                self.assertEqual(response.status_code, status)
                if status == 200:
                    self.assertTrue(json.loads(response.content)['complete'])

    @override_settings(ALLOWED_HOSTS=['testserver'], CSRF_TRUSTED_ORIGINS=['https://testserver'])
    async def test_complete_utterance_flushes_all_finals_and_never_scores_interims(self):
        from google.cloud.speech_v2.types import cloud_speech
        incoming, output = asyncio.Queue(), []
        ticket = signing.dumps(self.payload(), salt=crla_stream.TICKET_SALT)
        for event in ({'type': 'websocket.connect'}, {'type': 'websocket.receive', 'text': json.dumps({'ticket': ticket})},
                      {'type': 'websocket.receive', 'bytes': b'\0\0' * 3200},
                      {'type': 'websocket.receive', 'text': '{"type":"finish"}'}):
            await incoming.put(event)
        client = SimpleNamespace(transport=SimpleNamespace(close=AsyncMock()))
        async def recognize(requests, **kwargs):
            async def responses():
                async for request in requests:
                    if request.streaming_config:
                        self.assertEqual(list(request.streaming_config.config.language_codes), ['fil-PH'])
                    else:
                        for text, final in (('unconfirmed', False), ('Si Bibo', True), ('ay bata.', True)):
                            yield cloud_speech.StreamingRecognizeResponse(results=[{
                                'alternatives': [{'transcript': text}], 'is_final': final}])
            return responses()
        client.streaming_recognize = recognize
        async def send(message):
            output.append(message)
        with patch.object(crla_stream, 'socket_session', return_value=self.session), \
                patch.object(crla_stream, 'authorize_material', return_value=self.material), \
                patch.object(crla_stream, 'speech_credentials', return_value=None), \
                patch('google.cloud.speech_v2.SpeechAsyncClient', return_value=client):
            await asyncio.wait_for(crla_stream.crla_websocket({'path': crla_stream.STREAM_PATH,
                'headers': [(b'origin', b'https://testserver'), (b'host', b'testserver')]}, incoming.get, send), 3)
        messages = [json.loads(m['text']) for m in output if m['type'] == 'websocket.send']
        self.assertFalse(any(m['type'] == 'final' for m in messages))
        result = signing.loads(messages[-1]['result_token'], salt=crla_stream.MATERIAL_RESULT_SALT)
        self.assertEqual(result['transcript'], 'Si Bibo ay bata.')
        self.assertTrue(messages[-1]['has_speech'])
        client.transport.close.assert_awaited_once()
