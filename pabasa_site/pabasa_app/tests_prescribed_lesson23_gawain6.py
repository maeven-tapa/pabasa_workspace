from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L23_G6_CANONICAL_WORDS,
    apply_event,
    get_activity,
    initial_l23_g6_state,
    l23_g6_pronunciation_match,
    normalize_l23_g6_state,
)


class PrescribedLesson23Gawain6Tests(SimpleTestCase):
    key = 'aral-l23-g6-q-syllable-builder'

    def test_exact_instruction_grid_and_order(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salitang.')
        expected = [['Que', 'En', 'Qui', 'tos'], ['no', 'A', 'Quin', 'An'], ['ta', 'ja', 'na', 'to'], ['ri', 'zon', 'que', 'ti']]
        self.assertEqual(activity['rows'], expected)
        self.assertEqual([item['text'] for item in activity['items']], sum(expected, []))
        self.assertEqual(len(activity['items']), 16)
        self.assertEqual(activity['bigbox_cells'][0][0], ['item-1'])
        self.assertEqual(activity['bigbox_cells'][3][2], ['item-15'])

    def test_reading_gate_advances_once_and_phase_two_is_not_complete(self):
        activity = get_activity(self.key)
        state = initial_l23_g6_state()
        apply_event(activity, state, {'action': 'reading_started'}, None)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'Que'}, True)
        self.assertEqual(state['index'], 1)
        with self.assertRaisesMessage(ValueError, 'kasalukuyang pantig'):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'Que'}, True)
        for index, text in enumerate([item['text'] for item in activity['items'][1:]], start=1):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': index, 'transcript': text}, True)
        self.assertTrue(state['read_aloud_completed'])
        self.assertEqual(state['reading_phase'], 'complete')
        self.assertFalse(state['completed'])

    def test_help_and_replay_do_not_advance(self):
        activity = get_activity(self.key)
        state = initial_l23_g6_state()
        apply_event(activity, state, {'action': 'reading_started'}, None)
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0, 'transcript': 'banana'}, False)
        self.assertEqual((state['index'], state['reading_phase']), (0, 'help'))
        apply_event(activity, state, {'action': 'read_aloud'}, None)
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'retry_reading'}, None)
        self.assertEqual((state['index'], state['reading_phase']), (0, 'read'))

    def test_duplicate_text_cells_are_distinct_and_answer_key_is_not_fabricated(self):
        activity = get_activity(self.key)
        self.assertNotEqual(activity['items'][0]['id'], activity['items'][14]['id'])
        self.assertEqual(activity['items'][0]['text'].casefold(), activity['items'][14]['text'].casefold())
        self.assertEqual(L23_G6_CANONICAL_WORDS, ())
        self.assertFalse(l23_g6_pronunciation_match('Que', 'banana'))
        restored = normalize_l23_g6_state({'index': 8, 'draft': {'builder': ['item-1', 'item-15']}})
        self.assertEqual(restored['index'], 8)
        self.assertEqual(restored['draft']['builder'], ['item-1', 'item-15'])

    def test_reference_uses_shared_builder_and_no_static_django_url(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn("aral-l23-g6-q-syllable-builder", source)
        self.assertNotIn('{% url', source)
