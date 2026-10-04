import hashlib
from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import get_activity


class Lesson22Gawain1AudioTests(SimpleTestCase):
    key = 'aral-l22-g1-c-syllable-builder'
    audio_dir = Path(__file__).parent / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_22/GAWAIN_1'

    def setUp(self):
        root = Path(__file__).parent
        self.js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.views = (root / 'views.py').read_text(encoding='utf-8')
        self.template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')

    def test_gawain1_content_and_audio_manifest_cover_all_runtime_syllables(self):
        activity = get_activity(self.key)
        syllables = [item['text'] for item in activity['items']]
        self.assertEqual(syllables, ['cac', 'ce', 'ca', 'bu', 'com', 'pu', 'ga', 'tus', 'ter', 'yan', 'Car', 'do', 'bi', 'ca', 'net', 'te', 'Ce', 'les'])
        self.assertIn("'syllables': {", self.views)
        self.assertIn("'feedback': {", self.views)
        self.assertIn("'completion': {", self.views)
        for text in set(syllables):
            self.assertIn(f"'{text}'", self.views)
            self.assertTrue((self.audio_dir / f'{text.lower()}_TTS.mp3').is_file(), text)

    def test_all_gawain1_recordings_are_nonempty_mp3_files(self):
        expected = {
            'Basahin_ang_mga_pantig_mula_sa_Bid_box_TTS.mp3',
            'Letrang C. Handa kana_TTS.mp3',
            *(f'{name}_TTS.mp3' for name in ('bi', 'bu', 'ca', 'cac', 'car', 'ce', 'com', 'do', 'ga', 'les', 'net', 'pu', 'te', 'ter', 'tus', 'yan')),
            'Handa ka na_TTS.mp3',
            'Magaling! Nabasa mo nang tama ang lahat ng pantig._TTS.mp3',
            'Subukan muli._TTS.mp3',
            'Tama!_TTS.mp3',
        }
        self.assertEqual({path.name for path in self.audio_dir.glob('*.mp3')}, expected)
        for name in expected:
            path = self.audio_dir / name
            self.assertGreater(path.stat().st_size, 0, name)
            self.assertEqual(path.read_bytes()[:3], b'ID3', name)

    def test_gawain1_audio_precedes_google_tts_and_cache_token_is_scoped(self):
        self.assertIn('const localUrl=', self.js)
        self.assertIn('(l22G1 && L22_G1_MAPPED_TEXT.has(text))', self.js)
        self.assertIn("(localAudio.syllables || {})[text]", self.js)
        self.assertIn("(localAudio.feedback || {})[text]", self.js)
        self.assertIn("(localAudio.completion || {})[text]", self.js)
        self.assertIn("new Audio(localUrl)", self.js)
        self.assertIn("'Letrang C. Handa kana?': 'Letrang C. Handa kana_TTS.mp3'", self.views)
        self.assertIn("aral-l22-g1-c-syllable-builder' %}<script", self.template)
        self.assertIn('20261005-l22-g1-startup-audio-2', self.template)

    def test_instruction_recording_hash_is_stable(self):
        digest = hashlib.sha256((self.audio_dir / 'Basahin_ang_mga_pantig_mula_sa_Bid_box_TTS.mp3').read_bytes()).hexdigest()
        self.assertEqual(digest, 'dcd6d619b12abd1505e2fc508632f8dcb7269d9aa662d4e0c841b9bff3b26599')
