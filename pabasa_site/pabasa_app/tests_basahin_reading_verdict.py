import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import reading_transcribe_api


@override_settings(GOOGLE_STT_API_KEY='test-key')
class BasahinReadingVerdictTests(SimpleTestCase):
    def transcribe(self, target, heard, **fields):
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            'target_text': target, 'language': 'Filipino', 'mode': 'reading', **fields,
        })
        request._dont_enforce_csrf_checks = True
        with (
            patch('pabasa_app.views._check_auth', return_value=True),
            patch('pabasa_app.views._enforce_student_access_for_request', return_value=None),
            patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(heard, 'stt_v1', '')),
        ):
            response = reading_transcribe_api(request)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_word_inside_longer_word_is_not_correct(self):
        self.assertFalse(self.transcribe('lata', 'latag')['complete'])

    def test_segmented_word_is_accepted_with_raw_speech_preserved(self):
        result = self.transcribe('kabayo', 'ka ba yo')
        self.assertTrue(result['complete'])
        self.assertEqual(result['raw_transcript'], 'ka ba yo')

    def test_sentence_attempt_carries_backend_progress(self):
        first = self.transcribe('Si Bibo ay bata.', 'Si Bibo', mode='sentence')
        self.assertFalse(first['complete'])
        second = self.transcribe('Si Bibo ay bata.', 'ay bata', mode='sentence',
                                 current_syllable_index=first['current_syllable_index'])
        self.assertTrue(second['complete'])

    def test_incomplete_sentence_is_not_accepted_by_old_client_exception(self):
        self.assertFalse(self.transcribe('Uubo si Bibo.', 'Ubo si Bibo', mode='sentence')['complete'])

    def test_exact_rhyme_policy_stays_strict(self):
        self.assertTrue(self.transcribe('tatay', 'ta tay', salitang_magkatugma_exact='1')['complete'])
        self.assertFalse(self.transcribe('tatay', 'ang tatay', salitang_magkatugma_exact='1')['complete'])
        self.assertFalse(self.transcribe('tatay', 'ta bay', salitang_magkatugma_exact='1')['complete'])

    def test_cluster_check_alias_is_graded_by_backend(self):
        result = self.transcribe('tsek', 'check', prescribed_activity_key='session-7-lesson-20-21-gawain-1')
        self.assertTrue(result['complete'])
        self.assertEqual(result['transcript'], 'tsek')
        self.assertEqual(result['raw_transcript'], 'check')

    def test_cluster_alias_does_not_apply_to_other_activities_or_substrings(self):
        self.assertFalse(self.transcribe('tsek', 'check')['complete'])
        self.assertFalse(self.transcribe('tsek', 'check', prescribed_activity_key='another-activity')['complete'])
        self.assertFalse(self.transcribe('tsek', 'checker', prescribed_activity_key='session-7-lesson-20-21-gawain-1')['complete'])

    def test_empty_speech_is_not_correct(self):
        self.assertFalse(self.transcribe('bata', '')['complete'])
