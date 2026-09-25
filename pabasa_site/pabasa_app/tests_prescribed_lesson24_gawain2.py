from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G2_V_WORDS,
    apply_event,
    get_activity,
    initial_l22_g2_state,
    initial_l24_g2_state,
    l24_g2_pronunciation_match,
)


class Lesson24Gawain2WorkbookTests(SimpleTestCase):
    def test_exact_workbook_content_and_order(self):
        activity = get_activity('aral-l24-g2-v-word-reading')
        self.assertEqual(activity['session'], 8)
        self.assertEqual(activity['lesson'], 24)
        self.assertEqual(activity['activity_number'], '2')
        self.assertEqual(activity['instruction'], 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv.')
        self.assertEqual(tuple(item['text'] for item in activity['items']), L24_G2_V_WORDS)
        self.assertEqual(activity['column_headers'], ['V', 'v'])
        self.assertEqual(len(L24_G2_V_WORDS), 14)
        self.assertEqual(L24_G2_V_WORDS[8], 'vila')
        self.assertEqual(L24_G2_V_WORDS[13], 'volleybal')

    def test_exact_speech_matching_protects_collisions(self):
        self.assertTrue(l24_g2_pronunciation_match('Vina', ' vina! '))
        self.assertFalse(l24_g2_pronunciation_match('Victoria', 'Victor'))
        self.assertFalse(l24_g2_pronunciation_match('Victor', 'Victoria'))
        self.assertFalse(l24_g2_pronunciation_match('vanilla', 'van'))
        self.assertFalse(l24_g2_pronunciation_match('van', 'a van is here'))

    def test_progress_advances_once_and_requires_all_fourteen_targets(self):
        activity = get_activity('aral-l24-g2-v-word-reading')
        state = initial_l24_g2_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'Vina'}, True)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'Vina'}, True)
        self.assertEqual(state['sequence_index'], 1)
        self.assertEqual(state['completed_words'], [0])
        self.assertFalse(state['completed'])
        for word in L24_G2_V_WORDS[1:]:
            apply_event(activity, state, {'action': 'reading_started'})
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': word}, True)
        self.assertTrue(state['completed'])
        self.assertEqual(state['sequence_index'], 14)
        self.assertEqual(state['completed_words'], list(range(14)))

    def test_activity_identity_is_not_lesson22(self):
        self.assertNotEqual(
            get_activity('aral-l22-g2-c-word-reading')['activity_key'],
            get_activity('aral-l24-g2-v-word-reading')['activity_key'],
        )
        self.assertEqual(initial_l22_g2_state()['completed_words'], [])
        self.assertEqual(initial_l24_g2_state()['completed_words'], [])

    def test_intro_uses_payload_instruction_and_does_not_auto_narrate_twice(self):
        intro = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_g2_intro.js').read_text(encoding='utf-8')
        reading = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertIn('activity.instruction', intro)
        self.assertIn("a.activity_key!=='aral-l24-g2-v-word-reading'", reading)
        self.assertIn('canonicalInstruction=instructionText', reading)
        self.assertIn('${esc(canonicalInstruction)}', reading)
