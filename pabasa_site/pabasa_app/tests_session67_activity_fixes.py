import shutil
import subprocess
import tempfile
from pathlib import Path

from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

from .prescribed_activity_catalog import prescribed_activity
from .tests_prescribed_lesson19_gawain2 import _InlineJavaScriptParser
from .views import _admin_prescribed_sessions, _normalized_odd_word_state


class Session67ActivityFixTests(SimpleTestCase):
    def test_natural_success_and_retry_assets_are_mapped_to_the_right_activities(self):
        asset = 'pabasa_app/prescribed/audio/SESSION_6/magaling_tama_ang_iyong_pagbasa_natural_20261014.mp3'
        self.assertIsNotNone(finders.find(asset))
        for name in ('prescribed_picture_word_write_page', 'prescribed_picture_syllable_matching_page'):
            source = (Path(__file__).parent / 'templates' / 'pabasa_app' / f'{name}.html').read_text(encoding='utf-8')
            self.assertIn(asset, source)
            self.assertNotIn('magaling_tama_ang_iyong_pagbasa.mp3', source)
        matching = (Path(__file__).parent / 'templates' / 'pabasa_app' / 'prescribed_picture_syllable_matching_page.html').read_text(encoding='utf-8')
        self.assertIn('GAWAIN_7/hindi_pa_tama_tts.mp3', matching)

    def test_gawain6_uses_shared_capture_and_button(self):
        source = (Path(__file__).parent / 'templates' / 'pabasa_app' / 'prescribed_oral_missing_syllable_page.html').read_text(encoding='utf-8')
        for required in ('data-basahin-button', 'window.Basahin.bindActivity', 'window.Basahin.capture',
                         'window.Basahin.openMicrophone', 'window.Basahin.attachStreamResult'):
            self.assertIn(required, source)
        self.assertNotIn('setTimeout(()=>recorder.state', source)

    def test_gawain1_guided_listening_is_limited_and_recovers_completed_legacy_cycle(self):
        source = (Path(__file__).parent / 'templates' / 'pabasa_app' /
                  'prescribed_picture_syllable_matching_page.html').read_text(encoding='utf-8')
        self.assertIn('GUIDED_LISTEN_LIMIT=3', source)
        self.assertIn('aloudAttempts>=GUIDED_LISTEN_LIMIT', source)
        self.assertIn('resetGuidedListening();await save();renderOral', source)

    def test_display_number_changes_without_changing_saved_key_or_neighbors(self):
        activity = prescribed_activity('lesson-17-18-gawain-5')
        self.assertEqual(activity['activity_key'], 'lesson-17-18-gawain-5')
        self.assertEqual(activity['gawain_number'], 1)
        self.assertEqual(activity['title'], 'Lesson 17 at 18: Gawain 1')
        for number in range(6, 10):
            self.assertEqual(prescribed_activity(f'lesson-17-18-gawain-{number}')['gawain_number'], number)
        html = render_to_string('pabasa_app/prescribed_picture_syllable_matching_page.html', {
            'prescribed_activity_data': activity,
        })
        self.assertNotIn('gawain 5', html.lower())
        self.assertIn('GAWAIN_5/', html)  # asset and progress identities remain stable
        teacher_activity = next(
            item for session in _admin_prescribed_sessions() for item in session['activities']
            if item['activity_key'] == 'lesson-17-18-gawain-5'
        )
        self.assertEqual(teacher_activity['gawain_number'], 1)
        self.assertNotIn('gawain 5', str(teacher_activity).lower().replace('gawain-5', ''))

    def test_gawain8_fresh_state_starts_at_intro_and_continuation_keeps_position(self):
        activity = prescribed_activity('lesson-17-18-gawain-8')
        state = _normalized_odd_word_state(activity, {})
        self.assertEqual((state['phase'], state['current_group_index']), ('intro', 0))
        state = _normalized_odd_word_state(activity, {
            'phase': 'oral_reading', 'completed_answers': {'0': 1},
            'oral_completed': {'1': [0]},
        })
        self.assertEqual((state['phase'], state['current_group_index'], state['current_oral_word_index']),
                         ('oral_reading', 1, 1))
        # The shared normalizer retains its previous default outside this key.
        other = {**activity, 'activity_key': 'other-session-activity'}
        self.assertEqual(_normalized_odd_word_state(other, {})['phase'], 'oral_reading')

    def test_all_modified_inline_and_external_javascript_parses(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for the JavaScript syntax check.')
        root = Path(__file__).parent
        names = [
            'includes/session6_prescribed_controls', 'session8_11_prescribed_controls',
            'prescribed_missing_syllable_page', 'prescribed_oral_missing_syllable_page',
            'prescribed_oral_odd_word_page', 'prescribed_oral_picture_word_write_page',
            'prescribed_picture_syllable_matching_page', 'prescribed_picture_word_write_page',
            'session7_letter_ordering_page', 'session7_missing_syllable_page',
            'session7_circle_word_page',
        ]
        scripts = []
        for name in names:
            html = render_to_string(f'pabasa_app/{name}.html', {
                'prescribed_activity_data': {'activity_key': 'lesson-17-18-gawain-5'},
                'prefix': 'prescribed-s7-l19-g2',
            })
            parser = _InlineJavaScriptParser()
            parser.feed(html)
            scripts.extend(parser.scripts)
        for name in ['session67_ui', 'session6_prescribed_controls', 'session6_intro_modal',
                     'prescribed_session8_11_controls', 'session7_l2021_gawain3']:
            scripts.append((root / 'static' / 'pabasa_app' / 'js' / f'{name}.js').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            for index, script in enumerate(scripts):
                path = Path(directory) / f'script-{index}.js'
                path.write_text(script, encoding='utf-8')
                result = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
