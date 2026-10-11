from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G1_ACCEPTED_SPEECH,
    L24_G1_ACTIVITY_KEY,
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
        self.assertTrue(l24_g1_pronunciation_match('E', ' e ', L24_G1_ACTIVITY_KEY))
        self.assertTrue(l24_g1_pronunciation_match('I', 'I', L24_G1_ACTIVITY_KEY))
        self.assertTrue(l24_g1_pronunciation_match('A', 'a', L24_G1_ACTIVITY_KEY))
        self.assertFalse(l24_g1_pronunciation_match('E', 'bee', L24_G1_ACTIVITY_KEY))
        self.assertEqual(L24_G1_CANONICAL_WORDS, ())

    def test_each_reading_cell_keeps_its_canonical_whole_token_acceptance(self):
        activity = get_activity(L24_G1_ACTIVITY_KEY)
        self.assertEqual(
            [item['text'] for item in activity['items']],
            ['lin', 'sa', 'van', 'va', 'E', 'la', 'I', 'Vi', 'Vio', 'le', 'val', 'A'],
        )
        for item in activity['items']:
            canonical = item['text'].casefold()
            with self.subTest(expected=item['text']):
                self.assertIn(canonical, L24_G1_ACCEPTED_SPEECH[canonical])
                for alias in L24_G1_ACCEPTED_SPEECH[canonical]:
                    self.assertTrue(l24_g1_pronunciation_match(
                        item['text'], alias, L24_G1_ACTIVITY_KEY,
                    ))
                for other in activity['items']:
                    if other['id'] != item['id']:
                        self.assertFalse(l24_g1_pronunciation_match(
                            item['text'], other['text'], L24_G1_ACTIVITY_KEY,
                        ))

    def test_vi_accepts_only_the_approved_single_token_equivalent_in_scope(self):
        for transcript in ('vi', 'V', 'v', 'V.'):
            with self.subTest(transcript=transcript):
                self.assertTrue(l24_g1_pronunciation_match('Vi', transcript, L24_G1_ACTIVITY_KEY))
        for transcript in ('D', 'd', 'V V', 'vio', 'van'):
            with self.subTest(transcript=transcript):
                self.assertFalse(l24_g1_pronunciation_match('Vi', transcript, L24_G1_ACTIVITY_KEY))
        self.assertFalse(l24_g1_pronunciation_match('Vi', 'v', 'aral-l23-g1-n-syllable-builder'))
        self.assertFalse(l24_g1_pronunciation_match('Vio', 'v', L24_G1_ACTIVITY_KEY))
        self.assertFalse(l24_g1_pronunciation_match('van', 'v', L24_G1_ACTIVITY_KEY))

    def test_accepted_vi_alias_advances_once_without_an_incorrect_attempt(self):
        activity = get_activity(L24_G1_ACTIVITY_KEY)
        state = initial_l24_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for index, item in enumerate(activity['items'][:7]):
            accepted = l24_g1_pronunciation_match(item['text'], item['text'], L24_G1_ACTIVITY_KEY)
            apply_event(activity, state, {
                'action': 'reading_syllable_attempt', 'item_index': index, 'transcript': item['text'],
            }, accepted)
        self.assertEqual((state['index'], state['reading_attempts']), (7, 0))
        apply_event(activity, state, {
            'action': 'reading_syllable_attempt', 'item_index': 7, 'transcript': 'D',
        }, l24_g1_pronunciation_match('Vi', 'D', L24_G1_ACTIVITY_KEY))
        self.assertEqual((state['index'], state['reading_attempts'], state['last_feedback']), (7, 1, 'Subukan muli.'))
        apply_event(activity, state, {
            'action': 'reading_syllable_attempt', 'item_index': 7, 'transcript': 'V.',
        }, l24_g1_pronunciation_match('Vi', 'V.', L24_G1_ACTIVITY_KEY))
        self.assertEqual((state['index'], state['reading_attempts'], state['last_feedback']), (8, 0, 'Tama!'))
