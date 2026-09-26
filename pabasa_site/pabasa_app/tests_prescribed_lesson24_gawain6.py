from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G6_Z_WORD_PATHS,
    apply_event,
    get_activity,
    initial_l24_g6_state,
    normalize_l24_g6_state,
)


class Lesson24Gawain6WordSearchTests(SimpleTestCase):
    key = 'aral-l24-g6-z-word-search'

    def test_workbook_content_and_grid_are_exact(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.')
        self.assertEqual([item['text'] for item in activity['items']], [
            'zipper', 'zoo', 'zebra', 'zigzag', 'Perez',
            'Rizal', 'Zamora', 'Zam', 'Zoren', 'Zeny',
        ])
        self.assertEqual(len(activity['grid']), 8)
        self.assertTrue(all(len(row) == 9 for row in activity['grid']))
        self.assertEqual(sum(len(row) for row in activity['grid']), 72)
        self.assertEqual(activity['grid'][0], 'ZAMORATYZ')
        self.assertEqual(activity['grid'][-1], 'SMRIZALUK')
        self.assertEqual(activity['interaction_type'], 'search')

    def test_canonical_paths_cover_all_targets(self):
        activity = get_activity(self.key)
        expected = [item['text'] for item in activity['items']]
        self.assertEqual(list(L24_G6_Z_WORD_PATHS), expected)
        for word, path in L24_G6_Z_WORD_PATHS.items():
            self.assertEqual(''.join(activity['grid'][row][column] for row, column in path).casefold(), word.casefold())

    def test_valid_invalid_duplicate_completion_and_reset(self):
        activity = get_activity(self.key)
        state = initial_l24_g6_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'zipper', 'path': L24_G6_Z_WORD_PATHS['zipper']})
        self.assertEqual(set(state['found_words']), {'zipper'})
        self.assertFalse(state['completed'])
        apply_event(activity, state, {'action': 'select_word', 'word': 'zoo', 'path': [[0, 0], [0, 1], [0, 2]]})
        self.assertEqual(set(state['found_words']), {'zipper'})
        self.assertEqual(state['last_feedback'], 'Subukan muli.')
        apply_event(activity, state, {'action': 'select_word', 'word': 'zipper', 'path': L24_G6_Z_WORD_PATHS['zipper']})
        self.assertEqual(len(state['found_words']), 1)
        self.assertEqual(state['last_feedback'], 'Nahanap mo na ang salitang ito.')
        for word, path in L24_G6_Z_WORD_PATHS.items():
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': path})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['found_words']), 10)
        self.assertEqual(len(normalize_l24_g6_state(state)['found_words']), 10)
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l24_g6_state())

    def test_renderer_template_and_css_are_word_search_specific(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (root / 'static/pabasa_app/css/prescribed_l24_g6_search.css').read_text(encoding='utf-8')
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn('renderL24G6WordSearch()', js)
        self.assertIn('select_word', js)
        self.assertIn('wb-g6-grid', js)
        self.assertIn('PRESCRIBED-BG.jpg', css)
        self.assertIn('aral-l24-g6-z-word-search', template)
        self.assertNotIn('overflow:hidden', css)
