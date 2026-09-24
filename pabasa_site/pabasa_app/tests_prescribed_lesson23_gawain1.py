from django.test import SimpleTestCase

from .prescribed_workbook import (
    ACTIVITIES, L23_G1_WORDS, apply_event, get_activity, initial_l23_g1_state,
    l23_g1_pronunciation_match,
)


class Lesson23Gawain1Tests(SimpleTestCase):
    def test_workbook_instruction_and_big_box_are_exact(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertEqual(activity['rows'], [
            ['Ni', 'La', 'ña'], ['Cas', 'Bi', 'da'],
            ['El', 'ño', 'ñan'], ['Cen', 'ta', 'ñe'],
        ])
        self.assertEqual([item['text'] for item in activity['items']], [
            'Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe',
        ])

    def test_reading_is_sequential_and_only_real_errors_consume_attempts(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        state = initial_l23_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': ''}, None)
        self.assertEqual(state['reading_attempts'], 0)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual((state['index'], state['reading_attempts']), (0, 1))
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'ni'}, True)
        self.assertEqual((state['index'], state['reading_attempts']), (1, 0))
        for item in activity['items'][1:]:
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
        self.assertTrue(state['read_aloud_completed'])
        self.assertEqual(state['index'], 12)

    def test_help_retry_and_word_build_completion_require_both_phases(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        state = initial_l23_g1_state()
        with self.assertRaisesMessage(ValueError, 'Basahin muna'):
            apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        apply_event(activity, state, {'action': 'reading_started'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        for item in activity['items']:
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(state['found_words'], list(L23_G1_WORDS))
        apply_event(activity, state, {'action': 'finish'})
        self.assertTrue(state['completed'])

    def test_ntilde_pronunciation_is_scoped_to_current_target(self):
        self.assertTrue(l23_g1_pronunciation_match('ño', 'nyo'))
        self.assertTrue(l23_g1_pronunciation_match('ña', 'na'))
        self.assertFalse(l23_g1_pronunciation_match('ño', 'ni'))
        self.assertFalse(l23_g1_pronunciation_match('La', 'ño'))
