"""Dependency-free content and state regression tests (also run by Django)."""
import json
import unittest
from copy import deepcopy

from .prescribed_workbook import (ACTIVITIES, L22_G3_C_WORD_PATHS, L22_G5_F_WORD_PATHS, L23_G5_J_WORD_PATHS, apply_event,
                                  get_activity, initial_l22_g3_state, initial_l22_g5_state, initial_l23_g5_state, initial_l24_g1_state, initial_l24_g4_builder_state, initial_state,
                                  normalize_l22_g3_state, search_paths)


class PrescribedWorkbookDataTests(unittest.TestCase):
    def test_lesson24_has_two_explicit_bahagi_groups_and_unique_display_numbers(self):
        expected = [
            ('aral-l24-g1-v-syllable-builder', 'l24-bahagi1', 'Bahagi 1', '1'),
            ('aral-l24-g2-v-word-reading', 'l24-bahagi1', 'Bahagi 1', '2'),
            ('aral-l24-g3-x-repeat', 'l24-bahagi1', 'Bahagi 1', '3'),
            ('aral-l24-g4-x-pictures', 'l24-bahagi2', 'Bahagi 2', '2'),
            ('aral-l24-g3-x-word-reading', 'l24-bahagi2', 'Bahagi 2', '3'),
            ('aral-l24-g4-x-syllable-builder', 'l24-bahagi2', 'Bahagi 2', '4'),
            ('aral-l24-g5-z-syllabication', 'l24-bahagi2', 'Bahagi 2', '5'),
            ('aral-l24-g6-z-word-search', 'l24-bahagi2', 'Bahagi 2', '6'),
            ('aral-l24-g7-z-word-reading', 'l24-bahagi2', 'Bahagi 2', '7'),
        ]
        actual = [(key, ACTIVITIES[key]['section_key'], ACTIVITIES[key]['section_label'],
                   ACTIVITIES[key]['display_gawain_number']) for key, *_ in expected]
        self.assertEqual(actual, expected)
        self.assertEqual(len(expected), len({key for key, *_ in expected}))
        self.assertEqual(len(expected), len({(section, number) for _, section, _, number in expected}))
        self.assertTrue(all(ACTIVITIES[key]['section_display_label'].endswith(f'Gawain {number}')
                            for key, _, _, number in expected))

    def test_scope_counts_and_source_quirks(self):
        self.assertEqual(len(ACTIVITIES), 24)
        self.assertEqual([sum(a['session'] == s for a in ACTIVITIES.values()) for s in (8,9)], [22,2])
        for a in ACTIVITIES.values():
            self.assertIn(a['printed_page'], range(38,50))
            self.assertEqual(a['pdf_page'],a['printed_page']+3)
            self.assertEqual(a['session_key'], f"session-{a['session']}")
        self.assertEqual(ACTIVITIES['aral-l22-g3-c-word-search']['item_labels'], ['1.','2.','3.','4.','5.','3.','5.','7.','8.'])
        self.assertEqual(ACTIVITIES['aral-l24-g3-x-repeat']['display_label'],ACTIVITIES['aral-l24-g3-x-word-reading']['display_label'])
        self.assertEqual(ACTIVITIES['aral-l22-g2-c-word-reading']['rows'][-1],['Vic','Carlos'])

    def test_every_search_target_in_exact_grid(self):
        for a in ACTIVITIES.values():
            if a['interaction_type']=='search':
                self.assertEqual(len(set(map(len,a['grid']))),1)
                for item in a['items']:
                    self.assertTrue(search_paths(a,item['text']), (a['activity_key'], item['text']))

    def test_all_activities_save_reload_gate_and_complete(self):
        for a in ACTIVITIES.values():
            with self.subTest(activity=a['activity_key']):
                s=initial_state()
                if a['activity_key']=='aral-l22-g3-c-word-search':
                    s=initial_l22_g3_state()
                    for word, path in L22_G3_C_WORD_PATHS.items():
                        apply_event(a, s, {'action':'select_word','word':word,'path':path,'color':'#55a9df'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l22-g5-f-word-search':
                    s=initial_l22_g5_state()
                    for word, path in L22_G5_F_WORD_PATHS.items():
                        apply_event(a, s, {'action':'select_word','word':word,'path':path,'color':'#55a9df'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l23-g5-j-word-search':
                    s=initial_l23_g5_state()
                    for word, path in L23_G5_J_WORD_PATHS.items():
                        apply_event(a,s,{'action':'select_word','word':word,'path':path,'color':'#55a9df'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l22-g1-c-syllable-builder':
                    apply_event(a,s,{'action':'reading_started'})
                    apply_event(a,s,{'action':'reading_attempt'},True)
                    apply_event(a,s,{'action':'build_word','parts':['item-1','item-8']})
                    s=json.loads(json.dumps(s))
                    self.assertEqual(s['found_words'],['cactus'])
                    apply_event(a,s,{'action':'finish'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l23-g1-n-syllable-builder':
                    apply_event(a, s, {'action':'reading_started'})
                    for item in a['items']:
                        apply_event(a, s, {'action':'reading_syllable_attempt', 'transcript':item['text']}, True)
                    apply_event(a, s, {'action':'build_word','parts':['item-1','item-8']})
                    apply_event(a, s, {'action':'finish'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l24-g1-v-syllable-builder':
                    s = initial_l24_g1_state()
                    apply_event(a, s, {'action':'reading_started'})
                    for index, item in enumerate(a['items']):
                        apply_event(a, s, {'action':'reading_syllable_attempt', 'item_index': index, 'transcript':item['text']}, True)
                    self.assertTrue(s['read_aloud_completed'])
                    self.assertFalse(s['completed'])
                    continue
                if a['activity_key']=='aral-l24-g4-x-syllable-builder':
                    s = initial_l24_g4_builder_state()
                    apply_event(a, s, {'action': 'build_words', 'words': [['item-1', 'item-8']]})
                    apply_event(a, s, {'action': 'finish'})
                    self.assertTrue(s['completed'])
                    continue
                if a['activity_key']=='aral-l22-g2-c-word-reading':
                    for word in a['items']:
                        apply_event(a, s, {'action': 'reading_started'})
                        apply_event(a, s, {'action': 'reading_attempt', 'transcript': word['text']}, True)
                    self.assertTrue(s['completed'])
                    continue
                for i,item in enumerate(a['items']):
                    if a.get('model_first'):
                        with self.assertRaises(ValueError):apply_event(a,s,{'action':'reading'},True)
                        apply_event(a,s,{'action':'model_listened'})
                    if a['oral_flow']:
                        with self.assertRaises(ValueError):apply_event(a,s,{'action':'answer'})
                        for cycle in range(2):
                            for _ in range(3):apply_event(a,s,{'action':'reading'},False)
                            with self.assertRaises(ValueError):apply_event(a,s,{'action':'reading'},True)
                            for _ in range(3):apply_event(a,s,{'action':'listened'})
                        apply_event(a,s,{'action':'reading'},True)
                    answer=None
                    if a['interaction_type']=='search':answer=search_paths(a,item['text'])[0]
                    elif a['interaction_type']=='builder' and i==len(a['items'])-1:answer=[['item-1','item-2']]
                    elif a['interaction_type']=='syllables':answer={'text':a['syllable_answers'][i]}
                    elif a['interaction_type']=='fill':answer={'blanks':['cat']*a['blanks'][i]}
                    elif a['interaction_type']=='drawing':answer={'text':a['expected_writing'][0],'strokes':[{'color':'#123456','points':[[1,1],[2,2]]}]}
                    apply_event(a,s,{'action':'answer','answer':answer})
                    s=json.loads(json.dumps(s))
                    self.assertEqual(s['index'],i+1)
                    self.assertFalse(s['completed'])
                apply_event(a,s,{'action':'finish'})
                self.assertTrue(s['completed'])

    def test_incomplete_drawing_fill_and_syllables_are_not_finished(self):
        for key,answer in [('aral-s9-a1-family-drawing',{'text':'This is my family.','strokes':[]}),
                           ('aral-l23-g4-j-syllabication',{'text':'wrong'})]:
            a=get_activity(key);s=initial_state()
            if a['oral_flow']:apply_event(a,s,{'action':'reading'},True)
            with self.assertRaises(ValueError):apply_event(a,s,{'action':'answer','answer':answer})
            self.assertEqual(s['index'],0)
            with self.assertRaises(ValueError):apply_event(a,s,{'action':'finish'})

    def test_wrong_grid_path_rejected_and_color_saved(self):
        a=get_activity('aral-l22-g3-c-word-search');s=initial_state()
        s=initial_l22_g3_state()
        apply_event(a,s,{'action':'select_word','word':'computer','path':[[0,0],[0,1]],'color':'#ff0000'})
        self.assertFalse(s['found_words'])
        apply_event(a,s,{'action':'select_word','word':'computer','path':search_paths(a,'computer')[0],'color':'#ff0000'})
        self.assertEqual(s['found_words']['computer']['color'],'#ff0000')

    def test_lesson22_gawain3_exact_grid_words_and_coordinates(self):
        activity = get_activity('aral-l22-g3-c-word-search')
        self.assertEqual(activity['grid'], [
            'CARLAMREA', 'CAGAYANMS', 'ABCACTUSP', 'NAMHCARDO',
            'COMPUTERD', 'OCELESTEM', 'STCABINET', 'CEBUBRTDM', 'ABDCAMERA',
        ])
        self.assertEqual(list(activity['items'][i]['text'] for i in range(9)),
                         ['computer', 'Cagayan', 'camera', 'cabinet', 'Cebu', 'cactus', 'Cardo', 'Celeste', 'Carla'])
        for word, path in L22_G3_C_WORD_PATHS.items():
            self.assertEqual(search_paths(activity, word), [path])

    def test_lesson22_gawain3_any_order_invalid_and_duplicate_protection(self):
        activity = get_activity('aral-l22-g3-c-word-search')
        state = initial_l22_g3_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'Cebu', 'path': L22_G3_C_WORD_PATHS['Cebu'], 'color': '#f2c94c'})
        self.assertEqual(state['found_words']['Cebu']['color'], '#f2c94c')
        apply_event(activity, state, {'action': 'select_word', 'word': 'Cebu', 'path': L22_G3_C_WORD_PATHS['Cebu'], 'color': '#55a9df'})
        self.assertEqual(len(state['found_words']), 1)
        apply_event(activity, state, {'action': 'select_word', 'word': 'computer', 'path': [[0, 0], [0, 1]], 'color': '#55a9df'})
        self.assertEqual(len(state['found_words']), 1)
        apply_event(activity, state, {'action': 'select_word', 'word': 'computer', 'path': L22_G3_C_WORD_PATHS['computer'], 'color': '#55a9df'})
        self.assertEqual(len(state['found_words']), 2)
        self.assertEqual(normalize_l22_g3_state(state)['found_words']['Cebu']['color'], '#f2c94c')

    def test_lesson22_gawain3_completion_is_once_and_restorable(self):
        activity = get_activity('aral-l22-g3-c-word-search')
        state = initial_l22_g3_state()
        for word in L22_G3_C_WORD_PATHS:
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': L22_G3_C_WORD_PATHS[word], 'color': '#55a9df'})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['found_words']), 9)
        before = dict(state['found_words'])
        apply_event(activity, state, {'action': 'select_word', 'word': 'Carla', 'path': L22_G3_C_WORD_PATHS['Carla'], 'color': '#ef8d8d'})
        self.assertEqual(state['found_words'], before)
        self.assertTrue(normalize_l22_g3_state(state)['completed'])
