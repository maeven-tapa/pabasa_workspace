from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G4_X_WORDS,
    L24_G4_X_CANONICAL_WORDS,
    apply_event,
    get_activity,
    initial_l24_g4_state,
    initial_l24_g4_builder_state,
    normalize_l24_g4_builder_state,
    l24_g4_pronunciation_match,
)


class Lesson24Gawain4WorkbookTests(SimpleTestCase):
    def test_big_box_activity_uses_exact_four_by_three_source_grid(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        self.assertEqual(activity['interaction_type'], 'builder')
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertEqual([item['text'] for item in activity['items']], [
            'A', 'Fe', 'xe', 'xy', 'phone', 'sax',
            'rox', 'lex', 'o', 'lix', 'lo', 'phone',
        ])
        self.assertEqual(len(activity['items']), 12)
        self.assertEqual(sum(item['text'] == 'phone' for item in activity['items']), 2)
        self.assertEqual(L24_G4_X_CANONICAL_WORDS, ())

    def test_big_box_builds_by_stable_cell_ids_and_resets(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        state = initial_l24_g4_builder_state()
        apply_event(activity, state, {
            'action': 'draft',
            'draft': {'builder': ['item-1', 'item-8'], 'words': [['item-1', 'item-8']]},
        })
        self.assertEqual(state['draft']['builder'], ['item-1', 'item-8'])
        apply_event(activity, state, {'action': 'build_words', 'words': [['item-1', 'item-8']]})
        restored = normalize_l24_g4_builder_state(state)
        self.assertEqual(restored['built_words'], [['item-1', 'item-8']])
        apply_event(activity, restored, {'action': 'finish'})
        self.assertTrue(restored['completed'])
        apply_event(activity, restored, {'action': 'restart'})
        self.assertEqual(restored, initial_l24_g4_builder_state())

    def test_builder_renderer_is_not_the_generic_oral_reading_path(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn("if(l24G4Builder&&!preview){renderBuilder();lock();return;}", js)
        self.assertIn("button('Isumite ang mga salita',()=>perform({action:'build_words',words}),true)", js)
        self.assertIn("(!l24G4Builder&&!oral().passed)", js)

    def test_identity_content_order_and_assets(self):
        activity = get_activity('aral-l24-g4-x-pictures')
        self.assertEqual((activity['session'], activity['lesson'], activity['activity_number']), (8, 24, '4'))
        self.assertEqual(activity['instruction'], 'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.')
        self.assertEqual(tuple(item['text'] for item in activity['items']), L24_G4_X_WORDS)
        self.assertEqual(len(activity['items']), 3)
        self.assertEqual(activity['images'], {
            'item-1': '/static/pabasa_app/images/aral_workbook/x-ray.png',
            'item-2': '/static/pabasa_app/images/aral_workbook/fax-machine.png',
            'item-3': '/static/pabasa_app/images/aral_workbook/fox.png',
        })

    def test_speech_matching_is_exact_with_safe_x_ray_hyphen_normalization(self):
        self.assertTrue(l24_g4_pronunciation_match('x-ray', 'X ray'))
        self.assertTrue(l24_g4_pronunciation_match('fax machine', 'fax machine'))
        self.assertTrue(l24_g4_pronunciation_match('fox', 'FOX'))
        self.assertFalse(l24_g4_pronunciation_match('fax machine', 'fax'))
        self.assertFalse(l24_g4_pronunciation_match('fox', 'foxes'))

    def test_progress_advances_once_and_stale_item_is_ignored(self):
        activity = get_activity('aral-l24-g4-x-pictures')
        state = initial_l24_g4_state()
        for index, word in enumerate(L24_G4_X_WORDS):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': index, 'transcript': word}, True)
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': index, 'transcript': word}, True)
            self.assertEqual(state['index'], index + 1)
        self.assertTrue(state['completed'])
        self.assertEqual(state['completed_words'], [0, 1, 2])

        state = initial_l24_g4_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 1, 'transcript': 'fax machine'}, True)
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['completed_words'], [])

    def test_standardized_picture_reading_hooks_are_scoped(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (Path(__file__).parent / 'static/pabasa_app/css/prescribed_l24_g4_pictures.css').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        for expected in ('wb-picture-reading', 'wb-picture-image', 'wb-picture-word', 'wb-picture-feedback', 'Pakinggan', 'Basahin'):
            self.assertIn(expected, js)
        self.assertIn('wb-l24-g4-pictures-page', css)
        self.assertIn('section_display_label', template)
        self.assertIn('aral-l24-g4-x-pictures', template)
        self.assertNotIn('overflow:hidden', css)
