from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L22_G6_F_WORDS,
    apply_event,
    get_activity,
    initial_l22_g6_state,
    l22_g6_pronunciation_match,
    normalize_l22_g6_state,
)


class PrescribedLesson22Gawain6Tests(SimpleTestCase):
    key = 'aral-l22-g6-f-word-reading'

    def test_exact_instruction_columns_and_reading_order(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ff.')
        self.assertEqual([row[0] for row in activity['rows']], list(L22_G6_F_WORDS[:5]))
        self.assertEqual([row[1] for row in activity['rows']], list(L22_G6_F_WORDS[5:]))
        self.assertEqual([item['text'] for item in activity['items']], list(L22_G6_F_WORDS))

    def test_second_word_and_all_later_words_reuse_reading_flow(self):
        activity = get_activity(self.key)
        state = initial_l22_g6_state()
        for index, word in enumerate(L22_G6_F_WORDS):
            apply_event(activity, state, {'action': 'reading_started'})
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': word}, True)
            self.assertEqual(state['sequence_index'], index + 1)
            self.assertIn(index, state['completed_words'])
        self.assertTrue(state['completed'])

    def test_wrong_unclear_help_retry_and_matching_are_scoped(self):
        activity = get_activity(self.key)
        state = initial_l22_g6_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for attempt in range(1, 4):
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'banana'}, False)
            self.assertEqual(state['reading_attempts'], attempt)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        self.assertEqual(state['reading_attempts'], 0)
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': ''}, None)
        self.assertEqual(state['reading_attempts'], 0)
        self.assertTrue(l22_g6_pronunciation_match('Felipe', 'felipe'))
        self.assertFalse(l22_g6_pronunciation_match('Felipe', 'banana'))

    def test_restore_is_contiguous_and_restart_isolated(self):
        restored = normalize_l22_g6_state({'completed_words': [0, 1, 3], 'reading_attempts': 2})
        self.assertEqual(restored['completed_words'], [0, 1, 2])
        self.assertEqual(restored['sequence_index'], 3)
        activity = get_activity(self.key)
        apply_event(activity, restored, {'action': 'restart'})
        self.assertEqual(restored, initial_l22_g6_state())

    def test_shared_page_has_exact_f_instruction_and_reusable_controls(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertIn('Simulan ang Pagbasa', source)
        self.assertIn('NARINIG KO', source)
        self.assertIn('stream?.getTracks().forEach(t=>t.stop())', source)
        self.assertNotIn('{ once: true }', source)
