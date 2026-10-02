import hashlib
from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import get_activity


class Lesson24Gawain6AudioTests(SimpleTestCase):
    key = 'aral-l24-g6-z-word-search'

    def setUp(self):
        root = Path(__file__).parent
        self.js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.views = (root / 'views.py').read_text(encoding='utf-8')
        self.template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')

    def test_exact_runtime_instruction_maps_to_confirmed_supplied_recording(self):
        activity = get_activity(self.key)
        self.assertEqual(
            activity['instruction'],
            'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.',
        )
        self.assertIn("'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.',", self.js)
        self.assertIn("'instruction': 'Panuto Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita._TTS.mp3'", self.views)

    def test_existing_instruction_recording_is_identified_as_non_exact(self):
        folder = Path(r'C:\Users\caroline\Downloads\session 8_Lesson 24_bahagi= 02_Gawain 06')
        supplied = folder / 'Panuto Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita._TTS.mp3'
        destination = Path(__file__).parent / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_24/BAHAGI_2/GAWAIN_6' / supplied.name
        self.assertTrue(supplied.exists())
        self.assertTrue(destination.exists())
        self.assertEqual(hashlib.sha256(supplied.read_bytes()).digest(), hashlib.sha256(destination.read_bytes()).digest())
        self.assertNotEqual(supplied.stem.removesuffix('_TTS'), get_activity(self.key)['instruction'])

    def test_startup_and_mapped_playback_path_remain_wired(self):
        self.assertIn('if(g6Search)window.PabasaL24G6Start=startLesson24;', self.js)
        self.assertIn('playPrescribedAudio(instructionText,true)', self.js)
        self.assertEqual(
            self.js.count("playPrescribedAudio(instructionText,true).catch(error=>{if(error?.name!=='AbortError')console.error('Lesson 24 instruction audio failed'"),
            1,
        )
        self.assertIn('const mapped =', self.js)
        self.assertIn('new Audio(localUrl)', self.js)
        self.assertIn('fetch(data.read_aloud_url', self.js)
        self.assertIn("aral-l24-g6-z-word-search' %}<script", self.template)
        self.assertIn('20261002-l24-g6-direct-start-audio-1', self.template)

    def test_real_simulan_path_is_the_only_gawain6_startup_owner(self):
        startup = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l24_startup.js').read_text(encoding='utf-8')
        self.assertIn("if (key === 'aral-l24-g6-z-word-search')", startup)
        self.assertIn('window.PabasaL24G6Start?.();', startup)
        self.assertIn("document.dispatchEvent(new CustomEvent('pabasa:l24-started'", startup)
        self.assertEqual(self.js.count('window.PabasaL24G6Start=startLesson24;'), 1)
        self.assertEqual(self.js.count("playPrescribedAudio(instructionText,true).catch(error=>{if(error?.name!=='AbortError')console.error('Lesson 24 instruction audio failed'"), 1)
        renderer = self.js.split('function renderL24G6WordSearch', 1)[1].split('function renderFill', 1)[0]
        self.assertNotIn('playPrescribedAudio(instructionText', renderer)

    def test_gawain6_renderer_does_not_own_startup_playback(self):
        renderer = self.js.split('function renderL24G6WordSearch', 1)[1].split('function renderFill', 1)[0]
        self.assertNotIn('speakInstruction()', renderer)
        self.assertNotIn('__PABASA_G6_AUDIO_DEBUG__', self.js)

    def test_gawain5_mapping_remains_separate(self):
        self.assertIn('L24_G5_SYLLABLE_MAPPED_TEXT', self.js)
        self.assertIn('20261002-l24-g5-mapped-instruction-1', self.template)
