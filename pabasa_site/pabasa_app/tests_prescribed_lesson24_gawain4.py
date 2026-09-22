from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G4_X_WORDS,
    apply_event,
    get_activity,
    initial_l24_g4_state,
    l24_g4_pronunciation_match,
)


class Lesson24Gawain4WorkbookTests(SimpleTestCase):
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
        for expected in ('wb-picture-reading', 'wb-picture-image', 'wb-picture-word', 'wb-picture-feedback', 'Pakinggan', 'Basahin ang Salita'):
            self.assertIn(expected, js)
        self.assertIn('wb-l24-g4-pictures-page', css)
        self.assertIn('SESSION 8 · LESSON 24 · GAWAIN 4', template)
        self.assertNotIn('overflow:hidden', css)
