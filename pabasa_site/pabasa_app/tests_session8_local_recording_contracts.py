import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from . import views
from .prescribed_workbook import (
    apply_event,
    get_activity,
    initial_state,
    initial_l24_g3_repeat_state,
)


APP_ROOT = Path(__file__).resolve().parent


class Session8LocalRecordingContractTests(unittest.TestCase):
    """Session 8 recording flows retain their activity-specific submission rules."""

    RECORDING_SCRIPTS = (
        'static/pabasa_app/js/prescribed_l22_g2_reading.js',
        'static/pabasa_app/js/prescribed_l22_g4_f_builder.js',
        'static/pabasa_app/js/prescribed_l23_g2_reading.js',
        'static/pabasa_app/js/prescribed_l24_g3_repeat.js',
    )

    def run_node(self, source):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for the microphone-state harness.')
        result = subprocess.run([node], input=source, capture_output=True, text=True,
                                timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_recorders_preserve_their_activity_specific_clip_submission(self):
        for relative_path in self.RECORDING_SCRIPTS:
            with self.subTest(script=relative_path):
                source = (APP_ROOT / relative_path).read_text(encoding='utf-8')
                self.assertIn('getUserMedia', source)
                self.assertIn("append('audio'", source)

    def test_confirmed_state_defects_delegate_capture_to_the_shared_button_lifecycle(self):
        targets = (
            'static/pabasa_app/js/prescribed_l22_g2_reading.js',
            'static/pabasa_app/js/prescribed_l23_g2_reading.js',
        )
        for relative_path in targets:
            with self.subTest(script=relative_path):
                source = (APP_ROOT / relative_path).read_text(encoding='utf-8')
                self.assertIn('window.Basahin.openMicrophone', source)
                self.assertIn("window.Basahin.capture({button:document.getElementById('read'),stream})", source)
                self.assertIn('window.Basahin.attachStreamResult', source)

    def test_shared_button_executes_listening_processing_and_ready_dom_states(self):
        source = (APP_ROOT / 'static/pabasa_app/js/basahin_button.js').read_text(encoding='utf-8')
        self.run_node(r'''
const vm = require('node:vm'), assert = require('node:assert/strict');
class Node {
  constructor() { this.attrs = {}; this.children = []; this.textContent = ''; this._dataset = {}; this.history = [];
    this.dataset = new Proxy(this._dataset, {set: (target, key, value) => {
      target[key] = String(value); if (key === 'basahinState') this.history.push(String(value)); return true;
    }}); }
  matches(selector) { return selector === 'button[data-basahin-button]' && this.hasAttribute('data-basahin-button'); }
  closest(selector) { return this.matches(selector) ? this : null; }
  setAttribute(name, value = '') { this.attrs[name] = String(value); }
  getAttribute(name) { return this.attrs[name] ?? null; }
  hasAttribute(name) { return Object.hasOwn(this.attrs, name); }
  querySelector(selector) { const key = selector.slice(1, -1); return this.children.find(child => child.hasAttribute(key)) || null; }
  querySelectorAll() { return []; }
  replaceChildren(...children) { this.children = children; children.forEach(child => { child.parentElement = this; }); }
}
const document = {readyState: 'complete', body: new Node(), listeners: {},
  addEventListener(name, callback) { this.listeners[name] = callback; },
  querySelectorAll() { return []; },
  createElement() { return new Node(); }};
const window = {location: {pathname: '/dashboard/assessment/'}};
const context = {window, document, MutationObserver: class { observe() {} }, requestAnimationFrame(callback) { callback(); }};
vm.runInNewContext(SOURCE, context);
const button = new Node();
window.BasahinButton.bindActivity(button, async () => {
  window.BasahinButton.setState(button, 'listening');
  window.BasahinButton.setState(button, 'processing');
  window.BasahinButton.setState(button, 'idle');
});
document.listeners.click({target: button});
Promise.resolve().then(() => {
  assert.deepEqual(button.history, ['idle', 'listening', 'processing', 'idle']);
  assert.equal(button.dataset.basahinState, 'idle');
  assert.equal(button.querySelector('[data-basahin-label]').textContent, 'Basahin');
}).catch(error => { console.error(error); process.exitCode = 1; });
'''.replace('SOURCE', json.dumps(source)))

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

    def test_l22_g1_accented_ce_provider_results_advance_once_without_an_incorrect_attempt(self):
        activity_key = 'aral-l22-g1-c-syllable-builder'
        activity_key = 'aral-l22-g1-c-syllable-builder'
        activity = get_activity(activity_key)
        for transcript in ('sé', 'Sé', 'SÉ', 'sé.'):
            with self.subTest(transcript=transcript):
                state = initial_state()
                apply_event(activity, state, {'action': 'reading_started'})
                apply_event(activity, state, {
                    'action': 'reading_syllable_attempt', 'transcript': 'cac',
                }, True)
                request = RequestFactory().post('/progress/', data={
                    'action': 'reading_syllable_attempt', 'revision': str(state['revision']),
                    'audio': SimpleUploadedFile('session8.webm', b'mocked-webm-audio', 'audio/webm'),
                    '_preview_state': json.dumps(state),
                })
                request._admin_prescribed_preview = True
                real_reading_api = views.reading_transcribe_api
                while hasattr(real_reading_api, '__wrapped__'):
                    real_reading_api = real_reading_api.__wrapped__
                with (
                    patch.object(views, '_check_auth', return_value=True),
                    patch.object(views, '_enforce_student_access_for_request', return_value=None),
                    patch.object(
                        views, 'transcribe_audio_bytes_with_model',
                        return_value=(transcript, 'mocked-chirp-3', ''),
                    ),
                    patch.object(views, 'reading_transcribe_api', side_effect=real_reading_api),
                ):
                    response = views._prescribed_workbook_activity_progress(
                        request, activity_key, activity, student=None
                    )
                result = json.loads(response.content)
                self.assertEqual(response.status_code, 200, result)
                self.assertEqual(result['state']['index'], 2)
                self.assertEqual(result['state']['last_feedback'], 'Tama!')
                self.assertEqual(result['state']['reading_attempts'], 0)

    def test_session8_script_rejection_is_consistent_for_uploaded_and_streamed_results(self):
        activity_cases = (
            ('aral-l22-g1-c-syllable-builder', 'Cebu', {
                'l22_c_pronunciation': '1', 'l22_c_syllable': 'ce', 'l22_c_sound': 'soft',
            }),
            # These custom word-search pages do not offer a microphone, but
            # their progress route still invokes the shared evaluator for a
            # submitted reading action.  Keep that dormant server path guarded.
            ('aral-l22-g3-c-word-search', 'Cecilia', {}),
            ('aral-l22-g5-f-word-search', 'Felix', {}),
        )
        for activity_key, target_text, extra_fields in activity_cases:
            base_fields = {
                'target_text': target_text, 'language': 'English', 'mode': 'reading',
                'prescribed_activity_key': activity_key, **extra_fields,
            }
            for transcript in ('से', 'seसे'):
                for source in ('uploaded', 'streamed'):
                    with self.subTest(activity_key=activity_key, source=source, transcript=transcript):
                        request = RequestFactory().post('/api/reading/transcribe/', {
                            **base_fields,
                            **({'audio': SimpleUploadedFile('session8.webm', b'audio', 'audio/webm')}
                               if source == 'uploaded' else {}),
                        })
                        request._dont_enforce_csrf_checks = True
                        with (
                            patch.object(views, '_check_auth', return_value=True),
                            patch.object(views, '_enforce_student_access_for_request', return_value=None),
                            patch.object(views, 'transcribe_audio_bytes_with_model', return_value=(transcript, 'mocked-chirp-3', '')),
                        ):
                            response = (
                                views._reading_transcribe_response(request, stream_transcript=transcript)
                                if source == 'streamed' else views.reading_transcribe_api(request)
                            )
                        result = json.loads(response.content)
                        self.assertEqual(response.status_code, 200, result)
                        self.assertFalse(result['complete'])
                        self.assertTrue(result['transcript_script_rejected'])
                        self.assertEqual(result['raw_transcript'], transcript)

        activity_key = 'aral-l22-g1-c-syllable-builder'
        activity = get_activity(activity_key)
        state = initial_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {
            'action': 'reading_syllable_attempt', 'transcript': 'cac',
        }, True)
        request = RequestFactory().post('/progress/', data={
            'action': 'reading_syllable_attempt', 'revision': str(state['revision']),
            'audio': SimpleUploadedFile('session8.webm', b'mocked-webm-audio', 'audio/webm'),
            '_preview_state': json.dumps(state),
        })
        request._admin_prescribed_preview = True
        real_reading_api = views.reading_transcribe_api
        while hasattr(real_reading_api, '__wrapped__'):
            real_reading_api = real_reading_api.__wrapped__
        with (
            patch.object(views, '_check_auth', return_value=True),
            patch.object(views, '_enforce_student_access_for_request', return_value=None),
            patch.object(views, 'transcribe_audio_bytes_with_model', return_value=('से', 'mocked-chirp-3', '')),
            patch.object(views, 'reading_transcribe_api', side_effect=real_reading_api),
        ):
            response = views._prescribed_workbook_activity_progress(
                request, activity_key, activity, student=None
            )
        progress = json.loads(response.content)['state']
        self.assertEqual(progress['index'], 1)
        self.assertEqual(progress['reading_attempts'], 0)
        self.assertEqual(progress['last_feedback'], 'Hindi ko malinaw na narinig. Subukan muli.')

    def test_l22_search_reading_posts_bind_the_activity_key_before_evaluation(self):
        for activity_key in ('aral-l22-g3-c-word-search', 'aral-l22-g5-f-word-search'):
            with self.subTest(activity_key=activity_key):
                activity = get_activity(activity_key)
                request = RequestFactory().post('/progress/', data={
                    'action': 'reading', 'revision': '0', '_preview_state': '{}',
                    'audio': SimpleUploadedFile('session8.webm', b'mocked-webm-audio', 'audio/webm'),
                })
                request._admin_prescribed_preview = True

                def rejected_speech(reading_request):
                    self.assertEqual(reading_request.POST['prescribed_activity_key'], activity_key)
                    return JsonResponse({
                        'success': True, 'transcript': 'से', 'raw_transcript': 'से',
                        'complete': False, 'transcript_script_rejected': True,
                    })

                with patch.object(views, 'reading_transcribe_api', side_effect=rejected_speech):
                    response = views._prescribed_workbook_activity_progress(
                        request, activity_key, activity, student=None
                    )
                # The legacy action remains invalid for a word search, but
                # only after the request has reached guarded evaluation.
                self.assertEqual(response.status_code, 400, response.content)


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
