from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_activity_catalog import PRESCRIBED_ACTIVITIES
from .prescribed_workbook import (
    L23_G5_J_WORD_PATHS, apply_event, get_activity, initial_l23_g5_state,
    normalize_l23_g5_state,
)


class PrescribedLesson23Gawain5Tests(SimpleTestCase):
    key = 'aral-l23-g5-j-word-search'

    def test_exact_workbook_content_and_identity(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.')
        self.assertEqual([item['text'] for item in activity['items']], ['jacket', 'pajama', 'jam', 'Jonathan', 'Jennifer'])
        self.assertEqual(activity['grid'], [['Z','J','O','N','A','T','H','A','N'], ['J','A','M','L','T','Y','Z','S','I'], ['J','A','C','K','E','T','E','R','G'], ['B','Z','O','P','A','J','A','M','A'], ['J','E','N','N','I','F','E','R','M']])
        self.assertEqual(activity['activity_key'], self.key)
        self.assertNotEqual(self.key, 'aral-l22-g3-c-word-search')
        self.assertIn(self.key, PRESCRIBED_ACTIVITIES)
        self.assertEqual(L23_G5_J_WORD_PATHS['Jonathan'], [[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[0,7],[0,8]])
        self.assertEqual(L23_G5_J_WORD_PATHS['jam'], [[1,0],[1,1],[1,2]])
        self.assertEqual(L23_G5_J_WORD_PATHS['jacket'], [[2,0],[2,1],[2,2],[2,3],[2,4],[2,5]])
        self.assertEqual(L23_G5_J_WORD_PATHS['pajama'], [[3,3],[3,4],[3,5],[3,6],[3,7],[3,8]])
        self.assertEqual(L23_G5_J_WORD_PATHS['Jennifer'], [[4,0],[4,1],[4,2],[4,3],[4,4],[4,5],[4,6],[4,7]])

    def test_only_canonical_paths_count_once_and_complete_at_five(self):
        activity = get_activity(self.key)
        state = initial_l23_g5_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'jam', 'path': [[1,0],[1,1]]})
        self.assertFalse(state['found_words'])
        for word, path in L23_G5_J_WORD_PATHS.items():
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': path})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['found_words']), 5)
        before = dict(state['found_words'])
        apply_event(activity, state, {'action': 'select_word', 'word': 'jam', 'path': L23_G5_J_WORD_PATHS['jam'], 'color': '#ff0000'})
        self.assertEqual(state['found_words'], before)

    def test_wrong_path_and_restored_state_are_safe(self):
        state = normalize_l23_g5_state({'found_words': {
            'jam': {'path': L23_G5_J_WORD_PATHS['jam'], 'color': '#55a9df'},
            'stale': {'path': L23_G5_J_WORD_PATHS['jam'], 'color': '#55a9df'},
            'jacket': {'path': [[2,0],[2,1]], 'color': '#55a9df'},
        }, 'completed': True})
        self.assertEqual(set(state['found_words']), {'jam'})
        self.assertFalse(state['completed'])

    def test_instruction_audio_is_exact_and_no_microphone_answer(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l23_g5_j_word_search.js').read_text(encoding='utf-8')
        self.assertIn("const instruction = 'Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.';", source)
        self.assertNotIn('getUserMedia', source)
        self.assertNotIn('MediaRecorder', source)
