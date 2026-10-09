import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson19MatchingItemsTests(SimpleTestCase):
    def test_third_items_share_dila_word_and_image_with_activity_specific_answers(self):
        gawain1 = prescribed_activity('session-7-lesson-19-gawain-1')['items'][2]
        gawain3 = prescribed_activity('session-7-lesson-19-gawain-3')['items'][2]

        self.assertEqual(gawain1['id'], 'dila')
        self.assertEqual(gawain1['word'], 'dila')
        self.assertEqual(gawain3['id'], 'dila')
        self.assertEqual(gawain3['word'], 'dila')
        self.assertEqual(gawain1['image_path'], gawain3['image_path'])
        self.assertIn('di', gawain1['choices'])
        self.assertEqual(gawain1['answer'], 'di')
        self.assertIn('dila', gawain3['choices'])
        self.assertEqual(gawain3['answer'], 'dila')

    def test_gawain1_dila_audio_is_local_and_reuses_gawain3_word_clip(self):
        root = Path(__file__).parent / 'static/pabasa_app/prescribed/audio/SESSION_7/LESSON_19'
        gawain1 = root / 'GAWAIN_1'
        for filename in ('basahin_highlight_dila.mp3', 'dila_tts.mp3'):
            self.assertGreater((gawain1 / filename).stat().st_size, 0)
            self.assertEqual(
                hashlib.sha256((gawain1 / filename).read_bytes()).digest(),
                hashlib.sha256((root / 'GAWAIN_3' / filename).read_bytes()).digest(),
            )

        activity = prescribed_activity('session-7-lesson-19-gawain-1')
        rendered = render_to_string('pabasa_app/prescribed_starting_syllable_page.html', {
            'prescribed_activity_data': {**activity, 'progress': {'state': {}}},
        })
        self.assertIn("dila:'basahin_highlight_dila.mp3'", rendered)
        self.assertIn("dila:'dila_tts.mp3'", rendered)
        node = shutil.which('node')
        if node:
            script = rendered.split('<script>', 1)[1].split('</script>', 1)[0]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'gawain1.js'
                path.write_text(script, encoding='utf-8')
                result = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_gawain1_debug_expected_tracks_next_item_and_speech_target(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for the activity transition regression check.')
        activity = prescribed_activity('session-7-lesson-19-gawain-1')
        payload = {
            **activity,
            'progress_url': '/progress/',
            'transcribe_url': '/api/reading/transcribe/',
            'progress': {'activity_completed': False, 'state': {
                'phase': 'feedback', 'current_item_index': 3,
                'correct_answers': [0, 1, 2, 3],
            }},
        }
        rendered = render_to_string('pabasa_app/prescribed_starting_syllable_page.html', {
            'prescribed_activity_data': payload,
        })
        script = rendered.split('<script>', 1)[1].split('</script>', 1)[0]
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            script_path = Path(directory) / 'gawain1.js'
            payload_path = Path(directory) / 'payload.json'
            script_path.write_text(script, encoding='utf-8')
            payload_path.write_text(json.dumps(payload), encoding='utf-8')
            result = subprocess.run([
                node, str(root / 'tools/test_session7_l19_g1_expected.cjs'),
                str(script_path),
                str(Path(__file__).parent / 'static/pabasa_app/js/prescribed_session8_11_controls.js'),
                str(payload_path),
                str(Path(__file__).parent / 'static/pabasa_app/js/speech_debug.js'),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
