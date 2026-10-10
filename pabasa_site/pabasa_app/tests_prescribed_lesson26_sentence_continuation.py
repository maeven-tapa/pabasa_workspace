import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .lesson26_reading import analyze_sentence_continuation
from .prescribed_activity_catalog import prescribed_activity
from .reading_stt import ReadingMatcher
from .views import reading_transcribe_api


def sentence(item):
    return ''.join(part + (' ' + item['answers'][index] + ' ' if index < len(item['answers']) else '')
                   for index, part in enumerate(item['parts']))


@override_settings(GOOGLE_STT_API_KEY='', GOOGLE_CLOUD_PROJECT_ID='test-project')
class Lesson26SentenceRecognitionTests(SimpleTestCase):
    def setUp(self):
        for name, value in (('_check_auth', True), ('_enforce_student_access_for_request', None)):
            patcher = patch('pabasa_app.views.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('pabasa_app.views.transcribe_audio_bytes_with_model')
        self.transcribe = patcher.start()
        self.addCleanup(patcher.stop)

    def recognize(self, text, transcript, expected_status=200, provider='google', **fields):
        self.transcribe.return_value = (transcript, 'chirp_3', '')
        data = {'audio': SimpleUploadedFile('sentence.webm', b'audio', content_type='audio/webm'),
                'target_text': text, 'language': 'English', 'mode': 'sentence',
                'prescribed_activity_key': 'lesson-26-gawain-2', **fields}
        request = RequestFactory().post('/api/reading/transcribe/', data,
                                       HTTP_X_PABASA_STT_PROVIDER=provider, HTTP_X_PABASA_STT_MODEL='chirp_3')
        request._dont_enforce_csrf_checks = True
        response = reading_transcribe_api(request)
        self.assertEqual(response.status_code, expected_status, response.content)
        return json.loads(response.content)

    def test_every_sentence_highlights_only_correct_prefix_and_resumes(self):
        for item in prescribed_activity('lesson-26-gawain-2')['items']:
            text = sentence(item)
            words = text.split()
            prefix, suffix = ' '.join(words[:2]), ' '.join(words[2:])
            with self.subTest(item=item['id']):
                partial = self.recognize(text, prefix)
                self.assertFalse(partial['complete'])
                self.assertFalse(partial['reading_mismatch'])
                self.assertEqual(partial['correct_word_count'], 2)
                self.assertEqual(partial['stt_provider'], 'google')
                self.assertEqual(partial['language_code'], 'en-PH')
                self.assertEqual(partial['raw_transcript'], prefix)
                wrong = self.recognize(text, prefix + ' banana ' + suffix)
                self.assertFalse(wrong['complete'])
                self.assertTrue(wrong['reading_mismatch'])
                self.assertEqual(wrong['current_syllable_index'], partial['current_syllable_index'])
                for continuation in (suffix, text.upper() + '?'):
                    completed = self.recognize(text, continuation, current_syllable_index=partial['current_syllable_index'])
                    self.assertTrue(completed['complete'])
                    self.assertEqual(completed['correct_word_count'], len(ReadingMatcher(text).words))

    def test_retry_never_removes_previous_correct_words(self):
        text = sentence(prescribed_activity('lesson-26-gawain-2')['items'][0])
        partial = self.recognize(text, 'The furry')
        wrong = self.recognize(text, 'banana on the warm mat', current_syllable_index=partial['current_syllable_index'])
        self.assertFalse(wrong['complete'])
        self.assertTrue(wrong['reading_mismatch'])
        self.assertEqual(wrong['correct_word_count'], 2)

    def test_selected_knowlez_provider_is_preserved(self):
        with patch('pabasa_app.views.transcribe_knowlez_audio', return_value=('The furry', 'knowlez', '')) as knowlez:
            result = self.recognize('The furry cat on the warm mat.', 'unused', provider='knowlez')
        knowlez.assert_called_once()
        self.transcribe.assert_not_called()
        self.assertEqual(result['stt_provider'], 'knowlez')
        self.assertEqual(result['correct_word_count'], 2)
        self.assertFalse(result['complete'])

    def test_official_crla_and_other_activity_keep_existing_scorer(self):
        text = 'The cat wore a hat'
        result = self.recognize(text, 'The cat ate a hat', official_crla_assessment='1', crla_sentence_word_scoring='1')
        self.assertNotIn('reading_mismatch', result)
        self.assertIn('word_results', result)
        result = self.recognize(text, 'The cat', prescribed_activity_key='lesson-31-gawain-2')
        self.assertNotIn('reading_mismatch', result)

    def test_word_reading_and_provider_failures_keep_existing_behavior(self):
        result = self.recognize('cat', 'cat', mode='reading')
        self.assertTrue(result['complete'])
        self.assertNotIn('reading_mismatch', result)
        self.transcribe.side_effect = RuntimeError('Provider unavailable')
        result = self.recognize('The cat', 'The cat', expected_status=502)
        self.assertFalse(result['success'])
        self.assertNotIn('complete', result)
        self.assertIn('Provider unavailable', result['error'])


class Lesson26SentenceProgressTests(TestCase):
    activity_key = 'lesson-26-gawain-1'

    def setUp(self):
        # Reuse the authenticated, enrolled student fixture without inheriting unrelated tests.
        from .tests_prescribed_lesson26_word_search import PrescribedLesson26WordSearchTests
        PrescribedLesson26WordSearchTests.setUp(self)
        self.items = prescribed_activity(self.activity2_key)['items']

    def post(self, **payload):
        return self.client.post(self.activity2_progress_url, json.dumps(payload), content_type='application/json')

    def prepare(self):
        for index in range(4):
            self.assertEqual(self.post(action='choice_read', choice_index=index, success=True).status_code, 200)
        self.fill(0)

    def fill(self, index):
        self.assertEqual(self.post(action='sentence_read').status_code, 200)
        for blank, word in enumerate(self.items[index]['answers']):
            response = self.post(action='place_word', item_index=index, blank_index=blank, word=word)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertTrue(response.json()['accepted'])

    def test_all_items_preserve_prefix_retry_sync_and_reset_at_next_sentence(self):
        self.prepare()
        for index, item in enumerate(self.items):
            text = sentence(item)
            partial = analyze_sentence_continuation(text, 0, ' '.join(text.split()[:2]), 'en-PH')
            response = self.post(action='sentence_progress', item_index=index, current_syllable_index=partial['current_syllable_index'])
            self.assertEqual(response.status_code, 200, response.content)
            saved = response.json()['progress']['state']
            self.assertEqual(saved['sentence_word_index'], 2)
            self.assertEqual(saved['sentence_attempts'], 0)
            self.assertEqual(saved['completed_items'], index)
            self.assertEqual(self.post(action='sentence_reading', success=False).status_code, 200)
            saved = self.post(action='state_sync').json()['progress']['state']
            self.assertEqual(saved['sentence_word_index'], 2)
            self.assertEqual(saved['sentence_attempts'], 1)
            page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.activity2_key}))
            self.assertEqual(page.context['prescribed_activity_data']['progress']['state']['sentence_word_index'], 2)
            response = self.post(action='sentence_reading', success=True)
            saved = response.json()['progress']['state']
            self.assertEqual(saved['sentence_syllable_index'], 0)
            self.assertEqual(saved['sentence_word_index'], 0)
            if index < 3:
                self.fill(index + 1)
        self.assertEqual(saved['phase'], 'complete')
        self.assertEqual(saved['completed_items'], 4)
        self.assertEqual(self.post(reset=True).json()['progress']['state'], {})

    def test_partial_progress_requires_current_completed_sentence_and_word_boundary(self):
        self.assertEqual(self.post(action='sentence_progress', item_index=0, current_syllable_index=1).status_code, 400)
        self.prepare()
        matcher = ReadingMatcher(sentence(self.items[0]), language_code='en-PH')
        prefix_cursor = matcher.word_syllable_ranges[1][1]
        self.assertEqual(self.post(action='sentence_progress', item_index=0, current_syllable_index=prefix_cursor).status_code, 200)
        for index, cursor in ((1, prefix_cursor), (0, 0), (0, 999), (0, 2)):
            response = self.post(action='sentence_progress', item_index=index, current_syllable_index=cursor)
            self.assertEqual(response.status_code, 400, (index, cursor, response.content))
        self.assertEqual(self.post(action='sentence_reading', success=True).status_code, 200)
        self.assertEqual(self.post(action='sentence_progress', item_index=1, current_syllable_index=1).status_code, 400)
