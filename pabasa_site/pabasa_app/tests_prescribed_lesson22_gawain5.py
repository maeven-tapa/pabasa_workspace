import json
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from .prescribed_activity_catalog import PRESCRIBED_ACTIVITIES
from .prescribed_workbook import (
    L22_G5_F_WORD_PATHS,
    apply_event,
    get_activity,
    initial_l22_g5_state,
    normalize_l22_g5_state,
)


class PrescribedLesson22Gawain5Tests(SimpleTestCase):
    key = 'aral-l22-g5-f-word-search'

    def test_exact_workbook_payload_and_canonical_coordinates(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Hanapin at bilugan sa loob ng Big Box ang mga salita sa ibaba.')
        self.assertEqual(activity['grid'], ['MTGFINAE', 'FELIPEGR', 'MFRIESMD', 'FILIPINO', 'FREEZERH', 'SADFELIX'])
        self.assertEqual([item['text'] for item in activity['items']], ['freezer', 'fries', 'Fina', 'Filipino', 'Felix'])
        self.assertEqual(L22_G5_F_WORD_PATHS['Fina'], [[0, 3], [0, 4], [0, 5], [0, 6]])
        self.assertEqual(L22_G5_F_WORD_PATHS['fries'], [[2, 1], [2, 2], [2, 3], [2, 4], [2, 5]])
        self.assertEqual(L22_G5_F_WORD_PATHS['Filipino'], [[3, 0], [3, 1], [3, 2], [3, 3], [3, 4], [3, 5], [3, 6]])
        self.assertEqual(L22_G5_F_WORD_PATHS['freezer'], [[4, 0], [4, 1], [4, 2], [4, 3], [4, 4], [4, 5], [4, 6]])
        self.assertEqual(L22_G5_F_WORD_PATHS['Felix'], [[5, 3], [5, 4], [5, 5], [5, 6], [5, 7]])

    def test_only_exact_left_to_right_canonical_paths_are_accepted(self):
        activity = get_activity(self.key)
        state = initial_l22_g5_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'Fina', 'path': [[0, 3], [0, 4]], 'color': '#55a9df'})
        self.assertFalse(state['found_words'])
        for word, path in (
            ('Fina', L22_G5_F_WORD_PATHS['Fina']),
            ('fries', L22_G5_F_WORD_PATHS['fries']),
            ('Filipino', L22_G5_F_WORD_PATHS['Filipino']),
            ('freezer', L22_G5_F_WORD_PATHS['freezer']),
            ('Felix', L22_G5_F_WORD_PATHS['Felix']),
        ):
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': path, 'color': '#55a9df'})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['found_words']), 5)
        before = json.loads(json.dumps(state))
        apply_event(activity, state, {'action': 'select_word', 'word': 'Fina', 'path': L22_G5_F_WORD_PATHS['Fina'], 'color': '#ef8d8d'})
        self.assertEqual(state['found_words'], before['found_words'])

    def test_rejects_reversed_vertical_diagonal_and_cross_row_paths(self):
        activity = get_activity(self.key)
        rejected = [
            ('Fina', [[0, 6], [0, 5], [0, 4], [0, 3]]),
            ('Fina', [[0, 3], [1, 4], [2, 5], [3, 6]]),
            ('Fina', [[0, 3], [1, 3], [2, 3], [3, 3]]),
            ('Fina', [[0, 3], [0, 4], [1, 5], [1, 6]]),
        ]
        for word, path in rejected:
            state = initial_l22_g5_state()
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': path, 'color': '#55a9df'})
            self.assertEqual(state['found_words'], {})

    def test_restoration_sanitizes_stale_targets_and_completion_is_derived(self):
        restored = normalize_l22_g5_state({'found_words': {
            'Fina': {'path': L22_G5_F_WORD_PATHS['Fina'], 'color': '#55a9df'},
            'stale': {'path': L22_G5_F_WORD_PATHS['Fina'], 'color': '#55a9df'},
            'fries': {'path': [[2, 1], [2, 2]], 'color': '#55a9df'},
        }, 'completed': True, 'revision': 4})
        self.assertEqual(set(restored['found_words']), {'Fina'})
        self.assertFalse(restored['completed'])
        restored['found_words']['fries'] = {'path': L22_G5_F_WORD_PATHS['fries'], 'color': '#55a9df'}
        self.assertFalse(normalize_l22_g5_state(restored)['completed'])

    def test_restart_is_gawain5_scoped_and_next_activity_is_canonical(self):
        activity = get_activity(self.key)
        state = initial_l22_g5_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'Fina', 'path': L22_G5_F_WORD_PATHS['Fina']})
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l22_g5_state())
        self.assertIn('aral-l22-g6-f-word-reading', PRESCRIBED_ACTIVITIES)
        self.assertEqual(reverse('prescribed_activity_page', kwargs={'activity_key': 'aral-l22-g6-f-word-reading'}), '/dashboard/assessment/activity/prescribed/aral-l22-g6-f-word-reading/')

    def test_instruction_audio_is_exact_single_server_side_path_without_microphone_code(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g5_f_word_search.js').read_text(encoding='utf-8')
        self.assertEqual(source.count("const instruction = 'Hanapin at bilugan sa loob ng Big Box ang mga salita sa ibaba.';"), 1)
        self.assertIn("form.append('target_text', instruction)", source)
        self.assertNotIn('speechSynthesis', source)
        self.assertNotIn('getUserMedia', source)
        self.assertNotIn('MediaRecorder', source)
