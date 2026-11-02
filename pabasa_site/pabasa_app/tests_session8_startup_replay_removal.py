from pathlib import Path

from django.test import SimpleTestCase
from django.template.loader import render_to_string

from .prescribed_workbook import get_activity


SESSION_8_ACTIVITY_KEYS = {
    'aral-l22-g1-c-syllable-builder',
    'aral-l22-g2-c-word-reading',
    'aral-l22-g3-c-word-search',
    'aral-l22-g4-f-syllable-builder',
    'aral-l22-g5-f-word-search',
    'aral-l22-g6-f-word-reading',
    'aral-l23-g1-n-syllable-builder',
    'aral-l23-g2-n-word-reading',
    'aral-l23-g3-j-word-reading',
    'aral-l23-g4-j-syllabication',
    'aral-l23-g5-j-word-search',
    'aral-l23-g6-q-syllable-builder',
    'aral-l23-g7-q-word-reading',
    'aral-l24-g1-v-syllable-builder',
    'aral-l24-g2-v-word-reading',
    'aral-l24-g3-x-word-reading',
    'aral-l24-g3-x-repeat',
    'aral-l24-g4-x-syllable-builder',
    'aral-l24-g4-x-pictures',
    'aral-l24-g5-z-syllabication',
    'aral-l24-g6-z-word-search',
    'aral-l24-g7-z-word-reading',
}


class Session8StartupReplayRemovalTests(SimpleTestCase):
    def test_exact_22_activity_scope_uses_replay_suppression(self):
        self.assertEqual(len(SESSION_8_ACTIVITY_KEYS), 22)
        template = Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html'
        source = template.read_text(encoding='utf-8')
        self.assertIn("workbook_payload.activity.session == 8", source)
        self.assertIn("['#wb-instruction-replay','#instruction','#tts','.l24g3-repeat-replay']", source)
        for key in SESSION_8_ACTIVITY_KEYS:
            with self.subTest(activity_key=key):
                activity = get_activity(key)
                self.assertEqual(activity['session'], 8)
                html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
                    'workbook_payload': {'activity': activity},
                })
                self.assertIn("['#wb-instruction-replay','#instruction','#tts','.l24g3-repeat-replay']", html)

    def test_other_sessions_do_not_receive_session8_suppression(self):
        activity = get_activity('aral-s9-a1-family-drawing')
        self.assertNotEqual(activity['session'], 8)
        html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
            'workbook_payload': {'activity': activity},
        })
        self.assertNotIn("['#wb-instruction-replay','#instruction','#tts','.l24g3-repeat-replay']", html)
        self.assertIn('id="wb-instruction-replay"', html)

    def test_startup_audio_path_remains_independent_of_replay_control(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn('function speakInstruction()', source)
        self.assertIn('playPrescribedAudio(instructionText)', source)
        self.assertIn('initializeL22Entry()', source)
        self.assertIn('if(!startupNarrationStarted){startupNarrationStarted=true;playStartup();}', source)
        self.assertIn("const session8Activity = SESSION8_REPLAY_REMOVAL_KEYS.has(a.activity_key);", source)
        self.assertIn("session8Activity?'':'<button", source)

    def test_lesson22_gawain2_and_gawain6_activity_script_cannot_restore_replay(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertIn('suppressInstructionReplay=isL22G2||isL22G6', source)
        self.assertNotIn('ensureInstruction', source)
        self.assertIn('const removeStartupReplay=()=>document.getElementById(\'instruction\')?.remove();', source)

    def test_lesson22_gawain6_uses_the_same_scoped_replay_guard(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertIn("isL22G6=a.activity_key==='aral-l22-g6-f-word-reading'", source)
        self.assertIn('if(suppressInstructionReplay){', source)
