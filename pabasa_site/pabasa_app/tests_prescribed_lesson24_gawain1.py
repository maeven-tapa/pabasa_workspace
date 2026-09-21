from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G1_CANONICAL_WORDS,
    apply_event,
    get_activity,
    initial_l24_g1_state,
    l24_g1_pronunciation_match,
)


class Lesson24Gawain1Tests(SimpleTestCase):
    def test_workbook_instruction_grid_and_stable_coordinates_are_exact(self):
        activity = get_activity('aral-l24-g1-v-syllable-builder')
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.')
        self.assertEqual(activity['rows'], [
            ['lin', 'sa', 'van'], ['va', 'E', 'la'],
            ['I', 'Vi', 'Vio'], ['le', 'val', 'A'],
        ])
        self.assertEqual([item['id'] for item in activity['items']], [
            'r1c1', 'r1c2', 'r1c3', 'r2c1', 'r2c2', 'r2c3',
            'r3c1', 'r3c2', 'r3c3', 'r4c1', 'r4c2', 'r4c3',
        ])
        self.assertEqual(len(activity['items']), 12)
        self.assertNotEqual(activity['items'][3]['id'], activity['items'][2]['id'])
        self.assertNotEqual(activity['items'][10]['id'], activity['items'][2]['id'])
        self.assertNotEqual(activity['items'][6]['id'], activity['items'][7]['id'])
        self.assertNotEqual(activity['items'][8]['id'], activity['items'][7]['id'])

    def test_reading_is_sequential_retry_safe_and_unlocks_building_only(self):
        activity = get_activity('aral-l24-g1-v-syllable-builder')
        state = initial_l24_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'lin'}, True)
        self.assertEqual(state['index'], 1)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'lin'}, True)
        self.assertEqual(state['index'], 1)
        for index, item in enumerate(activity['items'][1:], start=1):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': index, 'transcript': item['text']}, True)
        self.assertTrue(state['read_aloud_completed'])
        self.assertEqual(state['reading_phase'], 'complete')
        self.assertFalse(state['completed'])

    def test_help_and_pronunciation_do_not_advance(self):
        activity = get_activity('aral-l24-g1-v-syllable-builder')
        state = initial_l24_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        self.assertEqual((state['index'], state['reading_phase']), (0, 'help'))
        apply_event(activity, state, {'action': 'read_aloud'})
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'retry_reading'})
        self.assertEqual((state['index'], state['reading_phase']), (0, 'read'))

    def test_single_letter_matching_is_scoped_and_answers_are_not_guessed(self):
        self.assertTrue(l24_g1_pronunciation_match('E', ' e '))
        self.assertTrue(l24_g1_pronunciation_match('I', 'I'))
        self.assertTrue(l24_g1_pronunciation_match('A', 'a'))
        self.assertFalse(l24_g1_pronunciation_match('E', 'bee'))
        self.assertEqual(L24_G1_CANONICAL_WORDS, ())
