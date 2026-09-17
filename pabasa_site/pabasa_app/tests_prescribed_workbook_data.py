"""Dependency-free content and state regression tests (also run by Django)."""
import json
import unittest
from copy import deepcopy

from .prescribed_workbook import ACTIVITIES, apply_event, get_activity, initial_state, search_paths


class PrescribedWorkbookDataTests(unittest.TestCase):
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
                if a['activity_key']=='aral-l22-g1-c-syllable-builder':
                    apply_event(a,s,{'action':'reading_started'})
                    apply_event(a,s,{'action':'reading_attempt'},True)
                    apply_event(a,s,{'action':'build_word','parts':['item-1','item-8']})
                    s=json.loads(json.dumps(s))
                    self.assertEqual(s['found_words'],['cactus'])
                    apply_event(a,s,{'action':'finish'})
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
        apply_event(a,s,{'action':'reading'},True)
        with self.assertRaises(ValueError):apply_event(a,s,{'action':'answer','answer':[[0,0],[0,1]]})
        apply_event(a,s,{'action':'draft','draft':{'color':'#ff0000'}})
        apply_event(a,s,{'action':'answer','answer':search_paths(a,'computer')[0]})
        self.assertEqual(s['mark_colors']['item-1'],'#ff0000')
