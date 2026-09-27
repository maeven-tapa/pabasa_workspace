from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G7_Z_WORDS,
    apply_event,
    get_activity,
    initial_l24_g7_state,
    l24_g7_pronunciation_match,
    normalize_l24_g7_state,
)


class Lesson24Gawain7WordReadingTests(SimpleTestCase):
    key = 'aral-l24-g7-z-word-reading'

    def test_exact_content_grouping_and_column_major_sequence(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Basahin ang mga salita sa ibaba na may hiram na letrang Zz.')
        self.assertEqual([item['text'] for item in activity['items']], list(L24_G7_Z_WORDS))
        self.assertEqual(len(activity['rows']), 8)
        self.assertEqual([sum(bool(row[column]) for row in activity['rows']) for column in range(3)], [8, 8, 7])
        self.assertEqual(activity['items'][0]['text'], 'zigzag')
        self.assertEqual(activity['items'][-1]['text'], 'Hernandez')
        self.assertEqual(activity['interaction_type'], 'reading')
        self.assertEqual(activity['oral_flow'], True)

    def test_progression_attempts_reset_and_stale_index_guard(self):
        activity = get_activity(self.key)
        state = initial_l24_g7_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        self.assertEqual(state['reading_attempts'], 3)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'}, None)
        apply_event(activity, state, {'action': 'retry_reading'}, None)
        self.assertEqual(state['reading_attempts'], 0)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 99, 'transcript': 'zigzag'}, True)
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'zigzag'}, True)
        self.assertEqual(state['completed_words'], [0])
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['reading_attempts'], 0)
        self.assertEqual(state['last_feedback'], 'Tama!')

    def test_completion_reset_and_pronunciation_match(self):
        activity = get_activity(self.key)
        state = initial_l24_g7_state()
        for index, word in enumerate(L24_G7_Z_WORDS):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': index, 'transcript': word}, True)
        self.assertTrue(state['completed'])
        self.assertEqual(state['index'], 23)
        self.assertEqual(state['completed_words'], list(range(23)))
        self.assertTrue(normalize_l24_g7_state(state)['completed'])
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l24_g7_state())
        self.assertTrue(l24_g7_pronunciation_match('Zaragosa', 'zaragosa'))
        self.assertFalse(l24_g7_pronunciation_match('Zaragosa', 'Zamora'))

    def test_renderer_template_and_css_are_gawain7_specific(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (root / 'static/pabasa_app/css/prescribed_l24_g7_word_reading.css').read_text(encoding='utf-8')
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn('renderL24G7WordReading()', js)
        self.assertIn('recordL24G7Reading', js)
        self.assertIn('wb-g7-columns', js)
        self.assertIn('PRESCRIBED-BG.jpg', css)
        self.assertIn('aral-l24-g7-z-word-reading', template)
        self.assertNotIn('overflow:hidden', css)
