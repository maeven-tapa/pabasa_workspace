from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G3_REPEAT_X_ACCEPTED_SPEECH,
    apply_event,
    get_activity,
    initial_l24_g3_repeat_state,
    l24_g3_repeat_pronunciation_match,
)


class Lesson24Bahagi1Gawain3WorkbookTests(SimpleTestCase):
    activity_key = 'aral-l24-g3-x-repeat'

    def test_exact_workbook_content_and_order(self):
        activity = get_activity(self.activity_key)
        self.assertEqual((activity['session'], activity['session_key'], activity['lesson'], activity['activity_number']),
                         (8, 'session-8', 24, '3'))
        self.assertEqual(activity['instruction'],
                         'Pakinggang mabuti ang mga salitang bibigkasin ng guro pagkatapos ay ulitin ito.')
        self.assertEqual(tuple(item['text'] for item in activity['items']), ('Alex', 'Felix', 'x-factor', 'fixer'))

    def test_x_factor_accepts_only_narrow_hyphen_spacing_variants(self):
        self.assertTrue(l24_g3_repeat_pronunciation_match('x-factor', 'x factor'))
        self.assertTrue(l24_g3_repeat_pronunciation_match('x-factor', 'X-factor'))
        self.assertFalse(l24_g3_repeat_pronunciation_match('x-factor', 'factor'))
        self.assertFalse(l24_g3_repeat_pronunciation_match('fixer', 'fixed'))
        self.assertEqual(set(L24_G3_REPEAT_X_ACCEPTED_SPEECH), {'alex', 'felix', 'x-factor', 'fixer'})

    def test_model_must_be_heard_before_reading_and_next_word_resets_gate(self):
        activity = get_activity(self.activity_key)
        state = initial_l24_g3_repeat_state()
        with self.assertRaises(ValueError):
            apply_event(activity, state, {'action': 'reading'}, True)
        apply_event(activity, state, {'action': 'model_listened'})
        apply_event(activity, state, {'action': 'reading'}, True)
        apply_event(activity, state, {'action': 'answer', 'answer': None})
        self.assertEqual(state['index'], 1)
        with self.assertRaises(ValueError):
            apply_event(activity, state, {'action': 'reading'}, True)
        apply_event(activity, state, {'action': 'model_listened'})
        self.assertEqual(state['oral']['item-2']['phase'], 'read')

    def test_three_wrong_attempts_preserve_retry_flow(self):
        activity = get_activity(self.activity_key)
        state = initial_l24_g3_repeat_state()
        apply_event(activity, state, {'action': 'model_listened'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading'}, False)
        self.assertEqual(state['oral']['item-1']['attempts'], 3)
        self.assertEqual(state['oral']['item-1']['phase'], 'listen')

    def test_renderer_uses_prescribed_tts_stt_and_no_browser_tts(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_g3_repeat.js').read_text(encoding='utf-8')
        css = (Path(__file__).parent / 'static/pabasa_app/css/prescribed_l24_g3_repeat.css').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        dedicated_template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_l24_g3_repeat_page.html').read_text(encoding='utf-8')
        for expected in ('Pakinggan', 'Ulitin', 'model_listened', 'prescribed_activity_key', 'reading', 'session_key'):
            self.assertIn(expected, js)
        self.assertNotIn('speechSynthesis', js)
        self.assertNotIn('SpeechSynthesisUtterance', js)
        self.assertIn("prescribed_l24_g3_repeat.js", template)
        self.assertIn("prescribed_l24_g3_repeat.js", dedicated_template)
        self.assertIn("prescribed_l24_g3_repeat.css", dedicated_template)
        self.assertIn("PRESCRIBED-BG.jpg", css)
        self.assertIn('width:320px', css)
        self.assertNotIn('overflow: hidden', css)
