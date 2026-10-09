import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import reading_transcribe_api


@override_settings(GOOGLE_STT_API_KEY='', GOOGLE_CLOUD_PROJECT_ID='test-project')
class Lesson27VerseRecognitionTests(SimpleTestCase):
    target = 'Who loved to chat with a fat bat'

    def setUp(self):
        for name, value in (('_check_auth', True), ('_enforce_student_access_for_request', None)):
            patcher = patch('pabasa_app.views.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('pabasa_app.views.transcribe_audio_bytes_with_model')
        self.transcribe = patcher.start()
        self.addCleanup(patcher.stop)

    def recognize(self, transcript, **fields):
        self.transcribe.return_value = (transcript, 'chirp_3', '')
        payload = {
            'audio': SimpleUploadedFile('verse.webm', b'audio', content_type='audio/webm'),
            'target_text': self.target, 'language': 'English', 'mode': 'sentence',
            'prescribed_activity_key': 'lesson-27-gawain-1',
        }
        payload.update(fields)
        request = RequestFactory().post('/api/reading/transcribe/', payload,
                                        HTTP_X_PABASA_STT_PROVIDER='google',
                                        HTTP_X_PABASA_STT_MODEL='chirp_3')
        request._dont_enforce_csrf_checks = True
        response = reading_transcribe_api(request)
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def test_accepts_love_for_loved_in_full_verse_and_preserves_transcript(self):
        transcript = 'Who love to chat with a fat bat?'
        result = self.recognize(transcript)
        self.assertTrue(result['complete'])
        self.assertEqual(result['correct_word_count'], 8)
        self.assertEqual(result['raw_transcript'], transcript)

    def test_original_verse_and_punctuation_remain_accepted(self):
        for transcript in (self.target, self.target + '?', self.target.upper() + '!'):
            with self.subTest(transcript=transcript):
                self.assertTrue(self.recognize(transcript)['complete'])

    def test_alias_works_when_continuing_after_first_word(self):
        result = self.recognize('love to chat with a fat bat?', current_syllable_index=1)
        self.assertTrue(result['complete'])

    def test_other_incorrect_or_missing_words_still_fail(self):
        for transcript in ('Who love to chat with a fat bath?', 'Who love to chat with a fat'):
            with self.subTest(transcript=transcript):
                self.assertFalse(self.recognize(transcript)['complete'])

    def test_alias_does_not_apply_to_other_activities_or_generic_reading(self):
        for activity_key in ('lesson-29-gawain-1', ''):
            with self.subTest(activity_key=activity_key):
                result = self.recognize('Who love to chat with a fat bat?',
                                        prescribed_activity_key=activity_key)
                self.assertFalse(result['complete'])

    def test_alias_is_limited_to_english_sentence_mode(self):
        for fields in ({'mode': 'reading'}, {'language': 'Filipino'}):
            with self.subTest(fields=fields):
                self.assertFalse(self.recognize('Who love to chat with a fat bat?', **fields)['complete'])
