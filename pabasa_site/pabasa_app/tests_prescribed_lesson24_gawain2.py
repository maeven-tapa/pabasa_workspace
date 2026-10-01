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

    def test_startup_waits_for_simulan_and_uses_the_canonical_instruction_path(self):
        startup = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_startup.js').read_text(encoding='utf-8')
        reading = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_g2_reading.js').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_l24_g2_reading_page.html').read_text(encoding='utf-8')
        workbook_template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn("data-l24-start-button", startup)
        self.assertIn("pabasa:l24-started", startup)
        self.assertIn("pabasa:l24-started", reading)
        self.assertIn('async function playInstruction()', reading)
        self.assertNotIn('prescribed_l24_g2_intro.js', template)
        self.assertIn("prescribed_l24_g2_reading.js' %}?v=20261001-l24-g2-audio-2", workbook_template)

    def test_instruction_and_feedback_use_mapped_audio_before_tts_fallback(self):
        reading = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_g2_reading.js').read_text(encoding='utf-8')
        views = (Path(__file__).parent / 'views.py').read_text(encoding='utf-8')
        self.assertIn("text === (activity.instruction || '')", reading)
        self.assertIn('localAudio.instruction || null', reading)
        self.assertIn('const url = localAudioUrl(text);', reading)
        self.assertIn('if (url) return playLocalAudio(url);', reading)
        self.assertNotIn('fall through to the existing TTS path', reading)
        self.assertIn('return speakWithGoogle(text);', reading)
        self.assertIn('await speakWithBrowserTts(text);', reading)
        self.assertIn("utterance.lang = 'fil-PH'", reading)
        self.assertIn('await playFeedback(feedback);', reading)
        self.assertIn("const message = 'Pakinggan ang tamang pagbigkas, pagkatapos ay subukan mong basahin.'; render(message); await playFeedback(message)", reading)
        self.assertIn("const message = 'Handa ka na?'; render(message); await playFeedback(message)", reading)
        self.assertIn("prescribed_activity_key', activity.activity_key", reading)
        self.assertIn("'instruction': static(audio_root + 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv._TTS.mp3')", views)
        for word in L24_G2_V_WORDS:
            self.assertIn(f"'{word}': '{word}_TTS.mp3'", views)
