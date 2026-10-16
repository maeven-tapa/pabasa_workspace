import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import reading_transcribe_api


@override_settings(GOOGLE_STT_API_KEY='test-key')
class BasahinReadingVerdictTests(SimpleTestCase):
    def transcribe(self, target, heard, *, model_used='stt_v1', **fields):
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            'target_text': target, 'language': 'Filipino', 'mode': 'reading', **fields,
        })
        request._dont_enforce_csrf_checks = True
        with (
            patch('pabasa_app.views._check_auth', return_value=True),
            patch('pabasa_app.views._enforce_student_access_for_request', return_value=None),
            patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(heard, model_used, '')),
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

    def test_session7_picture_tsokolate_provider_spellings(self):
        key = 'session-7-lesson-20-21-gawain-3'
        for heard in ('Choco Latte', 'chocolate'):
            with self.subTest(heard=heard):
                result = self.transcribe('tsokolate', heard, prescribed_activity_key=key)
                self.assertTrue(result['complete'])
                self.assertEqual(result['raw_transcript'], heard)
        self.assertFalse(self.transcribe('tsokolate', 'chocolate')['complete'])
        self.assertFalse(self.transcribe('tsokolate', 'chocolate bar', prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('kutsara', 'chocolate', prescribed_activity_key=key)['complete'])

    def test_session7_gawain1_tsokolate_provider_spellings(self):
        key = 'session-7-lesson-20-21-gawain-1'
        for heard in ('Choco Latte', 'chocolate'):
            with self.subTest(heard=heard):
                result = self.transcribe('tsokolate', heard, prescribed_activity_key=key)
                self.assertTrue(result['complete'])
                self.assertEqual(result['raw_transcript'], heard)
        self.assertFalse(self.transcribe('tsokolate', 'chocolate bar', prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('kutsara', 'chocolate', prescribed_activity_key=key)['complete'])

    def test_gawain_5_riles_accepts_reported_speech_spellings(self):
        for heard in ('rieles', 'reless', 'reles', 'reeles', 'realist', 'real price'):
            with self.subTest(heard=heard):
                result = self.transcribe(
                    'riles', heard, prescribed_activity_key='lesson-17-18-gawain-5',
                )
                self.assertTrue(result['complete'])
                self.assertEqual(result['transcript'], 'riles')
                self.assertEqual(result['raw_transcript'], heard)

    def test_gawain_5_riles_allowance_is_scoped_to_the_word_and_activity(self):
        key = 'lesson-17-18-gawain-5'
        for heard in ('rieles', 'realist', 'real price'):
            with self.subTest(heard=heard):
                self.assertFalse(self.transcribe('riles', heard)['complete'])
                self.assertFalse(self.transcribe('riles', heard, prescribed_activity_key='another-activity')['complete'])
                self.assertFalse(self.transcribe('puso', heard, prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('riles', 'ang rieles', prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('riles', 'railes', prescribed_activity_key=key)['complete'])

    def test_lesson7_mangga_accepts_chirp_single_g_transcript(self):
        result = self.transcribe(
            'mangga', 'manga', prescribed_activity_key='lesson7-gawain2b',
        )
        self.assertTrue(result['complete'])
        self.assertEqual(result['processed_transcript'], 'mangga')
        self.assertEqual(result['transcript'], 'mangga')
        self.assertEqual(result['raw_transcript'], 'manga')

    def test_mangga_alias_is_scoped_to_lesson7_target(self):
        self.assertFalse(self.transcribe('mangga', 'manga')['complete'])
        self.assertFalse(self.transcribe(
            'mangga', 'manga', prescribed_activity_key='another-activity',
        )['complete'])
        unchanged = self.transcribe(
            'manga', 'manga', prescribed_activity_key='lesson7-gawain2b',
        )
        self.assertEqual(unchanged['processed_transcript'], 'manga')
        self.assertEqual(unchanged['raw_transcript'], 'manga')

    def test_lesson4_medyas_chirp_spelling_counts_the_syllable(self):
        for heard in ('medias', 'Medias.'):
            with self.subTest(heard=heard):
                result = self.transcribe(
                    'medyas', heard, model_used='chirp_3',
                    prescribed_activity_key='session-2-lesson-4-gawain-2',
                )
                self.assertTrue(result['complete'])
                self.assertEqual(result['transcript'], 'medyas')
                self.assertEqual(result['processed_transcript'], 'medyas')
                self.assertEqual(result['raw_transcript'], heard)
                self.assertEqual(result['matched'], 1)
                self.assertEqual(result['current_syllable_index'], 1)
                self.assertEqual(result['progress'], 100.0)

    def test_lesson4_medyas_spelling_is_scoped_to_chirp_and_activity(self):
        key = 'session-2-lesson-4-gawain-2'
        for fields in ({}, {'prescribed_activity_key': 'another-activity'}):
            with self.subTest(fields=fields):
                self.assertFalse(self.transcribe('medyas', 'medias', model_used='chirp_3', **fields)['complete'])
        self.assertFalse(self.transcribe('medyas', 'medias', prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('medyas', 'medias sa bata', model_used='chirp_3',
                                         prescribed_activity_key=key)['complete'])
        self.assertFalse(self.transcribe('saya', 'medias', model_used='chirp_3',
                                         prescribed_activity_key=key)['complete'])
        self.assertTrue(self.transcribe('medyas', 'medyas', model_used='chirp_3',
                                        prescribed_activity_key=key)['complete'])

    def test_empty_speech_is_not_correct(self):
        self.assertFalse(self.transcribe('bata', '')['complete'])
