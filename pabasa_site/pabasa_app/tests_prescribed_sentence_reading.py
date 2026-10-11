import json

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import StudentActivityProgress
from .prescribed_activity_catalog import prescribed_activity
from .prescribed_sentence_reading import ACTIVITY_KEYS
from . import tests_prescribed_lesson29_oral_blank as lesson29_tests
from . import tests_prescribed_lesson26_sentence_continuation as lesson26_tests


class PrescribedSentenceContinuationTests(TestCase):
    setUp = lesson29_tests.PrescribedLesson29OralBlankTests.setUp

    def seed(self, key, index=0):
        activity = prescribed_activity(key)
        story = key == 'lesson-30-gawain-2'
        item = activity['lines'][index] if story else activity['items'][index]
        state = {'phase': 'reading' if story else 'sentence_reading' if key == 'lesson-29-gawain-1'
                 else 'reading_sentence', 'current_line' if story else 'current_item': index,
                 'completed_items': index, 'sentence_syllable_index': 0, 'sentence_word_index': 0}
        if key == 'lesson-31-gawain-2':
            state.update(placed_word=item['answer'], choice_index=len(activity['word_choices']))
        elif key == 'lesson-31-gawain-3':
            state.update(placements=item['ordered_words'], word_index=len(item['jumbled_words']))
        StudentActivityProgress.objects.filter(student=self.student, activity_key=key).delete()
        StudentActivityProgress.objects.create(student=self.student, activity_key=key,
                                              current_index=index, completed_items=index, state=state)
        return item if story else (f"{item['before']}{item['answer']}{item['after']}"
                                   if key == 'lesson-29-gawain-1' else item['sentence'])

    def send(self, key, heard, index=0, **extra):
        return self.client.post(reverse('prescribed_activity_progress', kwargs={'activity_key': key}),
                                data=json.dumps({'action': 'sentence_continuation', 'item_index': index,
                                                 'heard': heard, **extra}), content_type='application/json')

    def test_every_sentence_partial_mistake_suffix_and_completion(self):
        for key in sorted(ACTIVITY_KEYS):
            activity = prescribed_activity(key)
            count = len(activity['lines'] if key == 'lesson-30-gawain-2' else activity['items'])
            for index in range(count):
                with self.subTest(key=key, index=index):
                    words = self.seed(key, index).split()
                    prefix, suffix = ' '.join(words[:2]), ' '.join(words[2:])
                    partial = self.send(key, prefix, index)
                    self.assertEqual(partial.status_code, 200, partial.content)
                    result = partial.json()
                    self.assertTrue(result['continue_prompt'])
                    self.assertFalse(result['accepted'])
                    self.assertEqual(result['progress']['state']['sentence_word_index'], 2)
                    self.assertEqual(result['progress']['completed_items'], index)
                    wrong = self.send(key, 'banana ' + suffix, index).json()
                    self.assertFalse(wrong['continue_prompt'])
                    self.assertFalse(wrong['accepted'])
                    self.assertEqual(wrong['progress']['state']['sentence_word_index'], 2)
                    final = self.send(key, suffix, index).json()
                    self.assertTrue(final['accepted'])
                    self.assertEqual(final['progress']['completed_items'], index + 1)
                    self.assertEqual(final['progress']['state']['sentence_word_index'], 0)
                    self.assertEqual(final['progress']['activity_completed'], index + 1 == count)

    def test_mistake_stops_at_correct_prefix_and_rereading_can_finish(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                text = self.seed(key)
                words = text.split()
                wrong = self.send(key, ' '.join(words[:2] + ['banana'] + words[3:])).json()
                self.assertFalse(wrong['accepted'])
                self.assertFalse(wrong['continue_prompt'])
                self.assertEqual(wrong['progress']['state']['sentence_word_index'], 2)
                self.assertTrue(self.send(key, text).json()['accepted'])

    def test_extra_words_do_not_pass_and_empty_speech_does_not_change_state(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                text = self.seed(key)
                self.assertEqual(self.send(key, '').status_code, 400)
                progress = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
                self.assertEqual(progress.state['sentence_word_index'], 0)
                result = self.send(key, text + ' banana').json()
                self.assertFalse(result['accepted'])
                self.assertTrue(result['reading']['reading_mismatch'])
                self.assertTrue(self.send(key, text).json()['accepted'])

    def test_phase_and_item_guards_and_idempotent_save_retry(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                text = self.seed(key)
                self.assertEqual(self.send(key, text, 1).status_code, 400)
                first = self.send(key, text, request_id='same-clip').json()
                second = self.send(key, text, request_id='same-clip').json()
                self.assertEqual(first, second)
                self.assertEqual(first['progress']['completed_items'], 1)
                self.assertEqual(self.send(key, text).status_code, 400)
                StudentActivityProgress.objects.filter(student=self.student, activity_key=key).update(state={'phase': 'arranging'})
                self.assertEqual(self.send(key, text).status_code, 400)

    def test_matt_alias_does_not_accept_mad(self):
        key = 'lesson-29-gawain-1'
        for name in ('Mat', 'Math', 'Matt', 'Mad'):
            with self.subTest(name=name):
                text = self.seed(key).replace('Matt', name)
                self.assertEqual(self.send(key, text).json()['accepted'], name != 'Mad')

    def test_reset_clears_reading_cursor(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                text = self.seed(key)
                self.send(key, ' '.join(text.split()[:2]))
                response = self.client.post(reverse('prescribed_activity_progress', kwargs={'activity_key': key}),
                                            data=json.dumps({'reset': True}), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['progress']['state'], {})


class Lesson31PlaybackSaveTests(TestCase):
    setUp = lesson29_tests.PrescribedLesson29OralBlankTests.setUp
    key = 'lesson-31-gawain-2'

    def seed(self, phase='sentence_listen', index=0):
        activity = prescribed_activity(self.key)
        return StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.key, current_index=index,
            completed_items=index, total_items=len(activity['items']),
            state={'phase': phase, 'current_item': index, 'completed_items': index,
                   'choice_index': len(activity['word_choices'])})

    def post(self, **data):
        return self.client.post(reverse('prescribed_activity_progress', kwargs={'activity_key': self.key}),
                                data=json.dumps(data), content_type='application/json')

    def test_lost_playback_acknowledgement_can_be_retried_without_changing_progress(self):
        self.seed()
        payload = {'action': 'sentence_played', 'item_index': 0, 'request_id': 'played-first'}
        first = self.post(**payload)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()['progress']['state']['phase'], 'dragging')
        self.assertEqual(self.post(**payload).json(), first.json())
        answer = prescribed_activity(self.key)['items'][0]['answer']
        placed = self.post(action='place_word', word=answer).json()['progress']
        retry = self.post(**payload)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json()['progress'], placed)
        self.assertEqual(placed['state']['phase'], 'reading_sentence')

    def test_old_receipt_does_not_skip_the_next_sentence_or_clear_reading_progress(self):
        self.seed()
        payload = {'action': 'sentence_played', 'item_index': 0, 'request_id': 'played-first'}
        self.post(**payload)
        item = prescribed_activity(self.key)['items'][0]
        self.post(action='place_word', word=item['answer'])
        partial = self.post(action='sentence_continuation', item_index=0, heard=' '.join(item['sentence'].split()[:2])).json()['progress']
        self.assertEqual(self.post(**payload).json()['progress']['state'], partial['state'])
        self.post(action='sentence_continuation', item_index=0, heard=item['sentence'])
        before = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key).state
        retry = self.post(**payload)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json()['progress']['state'], before)
        self.assertEqual(before['phase'], 'sentence_listen')
        self.assertEqual(before['current_item'], 1)

    def test_playback_receipt_cannot_bypass_phase_or_item_guards(self):
        progress = self.seed('reading_choices')
        payload = {'action': 'sentence_played', 'item_index': 0, 'request_id': 'played-first'}
        self.assertEqual(self.post(**payload).status_code, 400)
        progress.state['phase'] = 'sentence_listen'
        progress.save(update_fields=['state'])
        self.assertEqual(self.post(**{**payload, 'item_index': 1}).status_code, 400)
        self.assertEqual(self.post(**{**payload, 'request_id': ''}).status_code, 400)
        self.assertEqual(self.post(**payload).status_code, 200)
        self.assertEqual(self.post(**{**payload, 'item_index': 1}).status_code, 400)
        self.assertEqual(self.post(**{**payload, 'request_id': 'unplayed'}).status_code, 400)
        self.assertEqual(self.post(action='sentence_played').status_code, 400)

    def test_legacy_playback_save_still_requires_listening(self):
        self.seed()
        result = self.post(action='sentence_played')
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()['progress']['state']['phase'], 'dragging')

    def test_receipt_retry_preserves_completion_and_reset_invalidates_it(self):
        activity = prescribed_activity(self.key)
        index = len(activity['items']) - 1
        self.seed(index=index)
        payload = {'action': 'sentence_played', 'item_index': index, 'request_id': 'played-last'}
        self.post(**payload)
        self.post(action='place_word', word=activity['items'][index]['answer'])
        completed = self.post(action='sentence_continuation', item_index=index,
                              heard=activity['items'][index]['sentence']).json()['progress']
        self.assertTrue(completed['activity_completed'])
        self.assertEqual(self.post(**payload).json()['progress']['state'], completed['state'])
        self.post(reset=True)
        self.assertEqual(self.post(**payload).status_code, 400)
        self.assertFalse(StudentActivityProgress.objects.filter(student=self.student, activity_key=self.key).exists())


@override_settings(GOOGLE_STT_API_KEY='', GOOGLE_CLOUD_PROJECT_ID='test-project')
class PrescribedSentenceRecognitionTests(SimpleTestCase):
    setUp = lesson26_tests.Lesson26SentenceRecognitionTests.setUp
    recognize = lesson26_tests.Lesson26SentenceRecognitionTests.recognize

    def test_selected_provider_partial_and_continuation_for_each_activity(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                text = 'The cat wore a hat.'
                partial = self.recognize(text, 'The cat', prescribed_activity_key=key)
                self.assertEqual(partial['stt_provider'], 'google')
                self.assertEqual(partial['language_code'], 'en-PH')
                self.assertEqual(partial['raw_transcript'], 'The cat')
                self.assertFalse(partial['complete'])
                self.assertEqual(partial['correct_word_count'], 2)
                wrong = self.recognize(text, 'banana a hat', prescribed_activity_key=key,
                                       current_syllable_index=partial['current_syllable_index'])
                self.assertFalse(wrong['complete'])
                self.assertTrue(wrong['reading_mismatch'])
                self.assertEqual(wrong['correct_word_count'], 2)
                rest = self.recognize(text, 'wore a hat', prescribed_activity_key=key,
                                      current_syllable_index=partial['current_syllable_index'])
                self.assertTrue(rest['complete'])

    def test_official_crla_word_mode_and_provider_failure_keep_their_behavior(self):
        for key in ACTIVITY_KEYS:
            with self.subTest(key=key):
                result = self.recognize('The cat wore a hat', 'The cat ate a hat',
                                        prescribed_activity_key=key, official_crla_assessment='1',
                                        crla_sentence_word_scoring='1')
                self.assertNotIn('reading_mismatch', result)
                self.assertIn('word_results', result)
                result = self.recognize('cat', 'cat', prescribed_activity_key=key, mode='reading')
                self.assertTrue(result['complete'])
                self.assertNotIn('reading_mismatch', result)
        self.transcribe.side_effect = RuntimeError('Provider unavailable')
        result = self.recognize('The cat', 'The cat', prescribed_activity_key='lesson-30-gawain-2',
                                expected_status=502)
        self.assertFalse(result['success'])
        self.assertNotIn('complete', result)
