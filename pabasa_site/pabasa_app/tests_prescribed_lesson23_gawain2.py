from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L23_G2_TARGETS,
    apply_event,
    get_activity,
    initial_l23_g2_state,
    l23_g2_pronunciation_match,
    normalize_l23_g2_state,
)


class Lesson23Gawain2Tests(SimpleTestCase):
    key = 'aral-l23-g2-n-word-reading'

    def test_exact_workbook_content_and_order(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ññ.')
        self.assertEqual(tuple(item['text'] for item in activity['items']), L23_G2_TARGETS)
        self.assertEqual(tuple(activity['reading_words']), L23_G2_TARGETS)
        self.assertEqual(activity['rows'], [[word] for word in L23_G2_TARGETS])
        self.assertIn('España', activity['items'][0]['text'])
        self.assertIn('Ññ', activity['instruction'])

    def test_target_aware_matching_preserves_multi_word_targets(self):
        self.assertTrue(l23_g2_pronunciation_match('Biñan Cendaña', 'Biñan Cendaña'))
        self.assertTrue(l23_g2_pronunciation_match('Castañeda Orduña', 'Castaneda Orduna'))
        self.assertFalse(l23_g2_pronunciation_match('Biñan Cendaña', 'Niña'))

    def test_all_six_targets_progress_once_and_complete(self):
        activity = get_activity(self.key)
        state = initial_l23_g2_state()
        for index, target in enumerate(L23_G2_TARGETS):
            apply_event(activity, state, {'action': 'reading_started'})
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': target}, True)
            self.assertEqual(state['sequence_index'], index + 1)
            self.assertEqual(state['completed_words'], list(range(index + 1)))
        self.assertTrue(state['completed'])
        self.assertEqual(state['reading_phase'], 'complete')

    def test_wrong_unclear_retry_and_technical_errors_are_scoped(self):
        activity = get_activity(self.key)
        state = initial_l23_g2_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': ''}, None)
        self.assertEqual(state['reading_attempts'], 0)
        for attempt in range(1, 4):
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'banana'}, False)
            self.assertEqual(state['reading_attempts'], attempt)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        self.assertEqual((state['reading_attempts'], state['reading_phase']), (0, 'read'))

    def test_restore_is_contiguous_and_restart_isolated(self):
        restored = normalize_l23_g2_state({'completed_words': [0, 1, 3], 'reading_attempts': 2})
        self.assertEqual(restored['completed_words'], [0, 1, 2])
        self.assertEqual(restored['sequence_index'], 3)
        activity = get_activity(self.key)
        apply_event(activity, restored, {'action': 'restart'})
        self.assertEqual(restored, initial_l23_g2_state())

    def test_page_uses_prescribed_tts_and_safe_reusable_controls(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l23_g2_reading.js').read_text(encoding='utf-8')
        self.assertIn("const INSTRUCTION='Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ññ.'", source)
        self.assertIn('prescribed_activity_key:a.activity_key', source)
        self.assertIn('fil-PH-Wavenet-A', source)
        self.assertIn('Pakinggan ang Panuto', source)
        self.assertIn('stopStream()', source)
        self.assertNotIn('speechSynthesis', source)
        self.assertNotIn('{ once: true }', source)
