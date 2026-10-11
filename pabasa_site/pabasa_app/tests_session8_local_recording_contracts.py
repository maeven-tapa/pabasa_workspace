import json
from pathlib import Path
import unittest
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from . import views
from .prescribed_workbook import (
    apply_event,
    get_activity,
    initial_l24_g3_repeat_state,
)


APP_ROOT = Path(__file__).resolve().parent


class Session8LocalRecordingContractTests(unittest.TestCase):
    """Local MediaRecorder flows submit clips and must not require Basahin."""

    RECORDING_SCRIPTS = (
        'static/pabasa_app/js/prescribed_l22_g2_reading.js',
        'static/pabasa_app/js/prescribed_l22_g4_f_builder.js',
        'static/pabasa_app/js/prescribed_l23_g2_reading.js',
        'static/pabasa_app/js/prescribed_l24_g3_repeat.js',
    )

    def test_local_recorders_submit_audio_without_shared_basahin_dependency(self):
        for relative_path in self.RECORDING_SCRIPTS:
            with self.subTest(script=relative_path):
                source = (APP_ROOT / relative_path).read_text(encoding='utf-8')
                self.assertIn('getUserMedia', source)
                self.assertIn("append('audio'", source)
                self.assertNotIn('window.Basahin.attachStreamResult', source)

    def test_only_legacy_session8_reading_controls_use_shared_basahin_presentation(self):
        targets = {
            'prescribed_l22_g2_reading.js': ('aral-l22-g2-c-word-reading', 'aral-l22-g6-f-word-reading'),
            'prescribed_l22_g4_f_builder.js': ('aral-l22-g4-f-syllable-builder',),
            'prescribed_l23_g2_reading.js': ('aral-l23-g2-n-word-reading',),
            'prescribed_l24_g2_reading.js': ('aral-l24-g2-v-word-reading',),
            'prescribed_l24_g3_repeat.js': ('aral-l24-g3-x-repeat',),
        }
        self.assertEqual(sum(map(len, targets.values())), 6)
        for source_name in targets:
            with self.subTest(script=source_name):
                source = (APP_ROOT / 'static/pabasa_app/js' / source_name).read_text(encoding='utf-8')
                self.assertIn('window.BasahinButton?.decorate', source)
                self.assertIn('getUserMedia', source)

        workbook = (APP_ROOT / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn('window.Basahin?.bindActivity', workbook)
        self.assertIn("window.BasahinButton?.LABEL||'Basahin'", workbook)

    def test_specialized_microphone_pages_load_shared_basahin_before_their_renderer(self):
        """The specialized pages must make the renderer's real decoration hook available."""
        targets = {
            'prescribed_l22_g2_reading.js': ('aral-l22-g2-c-word-reading', 'aral-l22-g6-f-word-reading'),
            'prescribed_l22_g4_f_builder.js': ('aral-l22-g4-f-syllable-builder',),
            'prescribed_l23_g2_reading.js': ('aral-l23-g2-n-word-reading',),
            'prescribed_l24_g2_reading.js': ('aral-l24-g2-v-word-reading',),
            'prescribed_l24_g3_repeat.js': ('aral-l24-g3-x-repeat',),
        }
        self.assertEqual(sum(map(len, targets.values())), 6)
        controls = (APP_ROOT / 'templates/pabasa_app/session8_11_prescribed_controls.html').read_text(encoding='utf-8')
        self.assertIn("{% include 'pabasa_app/basahin_script.html' %}", controls)
        for renderer_name, activity_keys in targets.items():
            with self.subTest(renderer=renderer_name):
                renderer = (APP_ROOT / 'static/pabasa_app/js' / renderer_name).read_text(encoding='utf-8')
                self.assertIn('window.BasahinButton?.decorate', renderer)
                for activity_key in activity_keys:
                    self.assertIn(activity_key, controls)

    def test_shared_basahin_ready_state_has_the_reference_icon_and_label_contract(self):
        source = (APP_ROOT / 'static/pabasa_app/js/basahin_button.js').read_text(encoding='utf-8')
        self.assertIn("const LABEL = 'Basahin'", source)
        self.assertIn("icon.setAttribute('data-basahin-icon', '')", source)
        self.assertIn("label.setAttribute('data-basahin-label', '')", source)
        self.assertIn("if (button.dataset.basahinState !== state) button.dataset.basahinState = state", source)


class Session8ClipSubmissionBehaviorTests(SimpleTestCase):
    """Exercise uploaded-clip submission through STT and activity evaluation."""

    ACTIVITIES = (
        ('aral-l22-g2-c-word-reading', 'reading_attempt'),
        ('aral-l22-g6-f-word-reading', 'reading_attempt'),
        ('aral-l22-g4-f-syllable-builder', 'reading_attempt'),
        ('aral-l23-g2-n-word-reading', 'reading_attempt'),
        ('aral-l24-g3-x-repeat', 'reading'),
    )

    @staticmethod
    def _preview_state(activity_key):
        if activity_key != 'aral-l24-g3-x-repeat':
            return {}
        activity = get_activity(activity_key)
        state = initial_l24_g3_repeat_state()
        return apply_event(activity, state, {'action': 'model_listened'})

    def test_clip_without_stream_token_reaches_stt_and_correct_or_incorrect_evaluation(self):
        for activity_key, action in self.ACTIVITIES:
            activity = get_activity(activity_key)
            target = activity['items'][0]['text']
            for is_correct, transcript in ((True, target), (False, '__not_the_target__')):
                with self.subTest(activity=activity_key, correct=is_correct):
                    audio = SimpleUploadedFile(
                        'session8.webm', b'mocked-webm-audio', content_type='audio/webm'
                    )
                    data = {
                        'action': action,
                        'revision': '0',
                        'audio': audio,
                    }
                    preview_state = self._preview_state(activity_key)
                    if preview_state:
                        data['_preview_state'] = json.dumps(preview_state)
                    request = RequestFactory().post('/progress/', data=data)
                    request._admin_prescribed_preview = True
                    real_reading_api = views.reading_transcribe_api
                    while hasattr(real_reading_api, '__wrapped__'):
                        real_reading_api = real_reading_api.__wrapped__

                    with (
                        patch.object(views, '_check_auth', return_value=True),
                        patch.object(views, '_enforce_student_access_for_request', return_value=None),
                        patch.object(
                            views,
                            'transcribe_audio_bytes_with_model',
                            return_value=(transcript, 'mocked-chirp-3', ''),
                        ) as mocked_stt,
                        patch.object(views, 'reading_transcribe_api', side_effect=real_reading_api),
                    ):
                        response = views._prescribed_workbook_activity_progress(
                            request, activity_key, activity, student=None
                        )

                    self.assertEqual(response.status_code, 200, response.content)
                    result = json.loads(response.content)
                    self.assertTrue(result['success'], result)
                    self.assertEqual(result.get('stt_model'), 'mocked-chirp-3')
                    mocked_stt.assert_called_once()
                    self.assertEqual(mocked_stt.call_args.args[0], b'mocked-webm-audio')
                    self.assertNotIn('prescribed_stream_token', request.POST)
                    self.assertEqual(result['progress']['current_index'], 1 if is_correct else 0)
                    self.assertEqual(result['state']['revision'], 1)


class Session8MicrophoneTemplateTests(SimpleTestCase):
    """Render the specialized pages to guard the real shared-button load order."""

    PAGES = (
        ('aral-l22-g2-c-word-reading', 'prescribed_l22_g2_reading_page.html', 'prescribed_l22_g2_reading.js'),
        ('aral-l22-g6-f-word-reading', 'prescribed_l22_g2_reading_page.html', 'prescribed_l22_g2_reading.js'),
        ('aral-l22-g4-f-syllable-builder', 'prescribed_l22_g4_f_builder_page.html', 'prescribed_l22_g4_f_builder.js'),
        ('aral-l23-g2-n-word-reading', 'prescribed_l23_g2_reading_page.html', 'prescribed_l23_g2_reading.js'),
        ('aral-l24-g2-v-word-reading', 'prescribed_l24_g2_reading_page.html', 'prescribed_l24_g2_reading.js'),
        ('aral-l24-g3-x-repeat', 'prescribed_l24_g3_repeat_page.html', 'prescribed_l24_g3_repeat.js'),
    )

    def test_specialized_pages_render_shared_button_before_activity_renderer(self):
        for activity_key, template_name, renderer_name in self.PAGES:
            with self.subTest(activity=activity_key):
                rendered = render_to_string(
                    f'pabasa_app/{template_name}',
                    {'workbook_payload': {'activity': get_activity(activity_key), 'state': {}, 'preview': True}},
                )
                self.assertIn('basahin_button.js', rendered)
                self.assertIn(renderer_name, rendered)
                self.assertEqual(rendered.count('basahin_button.js'), 1)
                self.assertEqual(rendered.count(renderer_name), 1)
                self.assertLess(rendered.index('basahin_button.js'), rendered.index(renderer_name))


if __name__ == '__main__':
    unittest.main()
