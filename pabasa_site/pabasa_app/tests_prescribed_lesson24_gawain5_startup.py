import json
import hashlib
from pathlib import Path
from unittest.mock import ANY, patch

from django.test import RequestFactory, SimpleTestCase

from .prescribed_workbook import get_activity
from .views import reading_read_aloud_api


class Lesson24Gawain5StartupTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(__file__).parent
        self.factory = RequestFactory()
        self.js = (self.root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.template = (self.root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')

    def test_target_identity_and_instruction_are_authoritative(self):
        activity = get_activity('aral-l24-g5-z-syllabication')
        self.assertEqual((activity['section_label'], activity['display_gawain_number']), ('Bahagi 2', '5'))
        self.assertEqual(activity['instruction'], 'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo.')

    def test_instruction_is_silent_until_target_starts(self):
        self.assertIn('if(g5Syllables&&!activityStarted&&text===instructionText)return;', self.js)
        self.assertIn("document.addEventListener('pabasa:l24-started'", self.js)
        self.assertIn('activityStarted=true;render();\n      if(!instructionSpoken){', self.js)
        self.assertIn('instructionSpoken=true;\n        playPrescribedAudio(instructionText,true)', self.js)
        self.assertIn('playPrescribedAudio(instructionText,true)', self.js)

    def test_target_receives_cache_busted_shared_workbook_script(self):
        self.assertIn("aral-l24-g5-z-syllabication' %}<script", self.template)
        self.assertIn('20261002-l24-g5-mapped-instruction-1', self.template)

    def test_exact_instruction_mapping_is_present_and_takes_priority(self):
        instruction = get_activity('aral-l24-g5-z-syllabication')['instruction']
        audio = self.root / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_24/BAHAGI_2/GAWAIN_5'
        mapped = audio / 'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo._TTS.mp3'
        self.assertTrue(mapped.exists())
        self.assertGreater(mapped.stat().st_size, 0)
        self.assertIn(repr(instruction), self.js)
        self.assertIn("'instruction': 'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo._TTS.mp3'", (self.root / 'views.py').read_text(encoding='utf-8'))
        self.assertIn('const mapped =', self.js)
        self.assertLess(self.js.index('const mapped ='), self.js.index('fetch(data.read_aloud_url'))

    def test_source_and_destination_instruction_audio_match(self):
        source = Path(r'C:\Users\caroline\Downloads\session 8_Lesson 24_bahagi= 02_Gawain 05') / 'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo._TTS.mp3'
        destination = self.root / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_24/BAHAGI_2/GAWAIN_5' / source.name
        self.assertTrue(source.exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(destination.read_bytes()).digest())

    def test_unmapped_text_keeps_existing_tts_fallback(self):
        self.assertIn("fetch(data.read_aloud_url", self.js)

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='encoded-audio')
    def test_unmapped_text_reaches_filipino_tts(self, synthesize, _access, _auth):
        text = 'Unmapped Gawain 5 diagnostic text.'
        request = self.factory.post('/reading/read-aloud/', {
            'target_text': text,
            'language': 'Filipino',
            'mode': 'reading',
            'prescribed_activity_key': 'aral-l24-g5-z-syllabication',
            'prescribed_session_key': 'session-8',
        })
        request._dont_enforce_csrf_checks = True
        response = reading_read_aloud_api(request)
        self.assertEqual(response.status_code, 200, response.content)
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['audio_content'], 'encoded-audio')
        self.assertEqual(payload['tts_language'], 'fil-PH')
        synthesize.assert_called_once_with(
            text,
            ANY,
            'fil-PH',
            credentials_file=ANY,
            voice_gender='FEMALE',
        )
