"""Rendered activity regressions; browser progress and speech stay in memory."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Run directly from the repository root, or through Django's test runner.
ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'pabasa_site'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.test import RequestFactory, SimpleTestCase

from pabasa_app.prescribed_activity_catalog import prescribed_activity
from pabasa_app.views import reading_transcribe_api


class Session67RequestedAudioTests(SimpleTestCase):
    def test_rendered_controls_and_audio_transitions_in_chrome(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node and Playwright are required for these browser regressions.')
        fixtures = []
        templates = {
            'lesson-17-18-gawain-5': 'prescribed_picture_syllable_matching_page',
            'lesson-17-18-gawain-6': 'prescribed_oral_missing_syllable_page',
            'lesson-17-18-gawain-9': 'prescribed_oral_picture_word_write_page',
            'session-7-lesson-19-gawain-2': 'session7_missing_syllable_page',
        }
        for key, template in templates.items():
            activity = prescribed_activity(key)
            data = {
                **activity,
                'items': [{**item, 'image_url': static(item['image_path'])} for item in activity['items']],
                'progress': {'state': {}, 'answers': []},
                'progress_url': '/progress/', 'completion_url': '/complete/',
                'read_aloud_url': '/narrate/', 'transcribe_url': '/transcribe/',
                'intro_enabled': key == 'lesson-17-18-gawain-5',
            }
            verdicts = {}
            if key == 'lesson-17-18-gawain-6':
                # Browser requests receive real backend verdicts for these synthetic transcripts.
                for item in activity['items']:
                    target = item['word']
                    verdicts[target] = {}
                    for heard in ('USA', target, 'paco', 'RoSeS', 'CARTON'):
                        request = RequestFactory().post('/api/reading/transcribe/', {
                            'audio': SimpleUploadedFile('test.webm', b'test', content_type='audio/webm'),
                            'target_text': target, 'language': 'Filipino', 'mode': 'reading',
                            'prescribed_activity_key': key,
                        })
                        request._dont_enforce_csrf_checks = True
                        with (
                            patch('pabasa_app.views._check_auth', return_value=True),
                            patch('pabasa_app.views._enforce_student_access_for_request', return_value=None),
                            patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(heard, 'chirp_3', '')),
                        ):
                            response = reading_transcribe_api(request)
                        self.assertEqual(response.status_code, 200)
                        verdicts[target][heard] = json.loads(response.content)
            fixtures.append({'key': key, 'data': data, 'speech_verdicts': verdicts, 'html': render_to_string(
                f'pabasa_app/{template}.html', {'prescribed_activity_data': data})})
        # The later-session include must retain its own layout and behavior.
        fixtures.append({'key': 'later-controls', 'data': {}, 'html': '<html><body>' + render_to_string(
            'pabasa_app/session8_11_prescribed_controls.html', {'prefix': 'prescribed-s8-test'}) + '</body></html>'})
        root = ROOT
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / 'fixtures.json'
            fixture_path.write_text(json.dumps(fixtures), encoding='utf-8')
            environment = {**os.environ, 'PABASA_SESSION67_FIXTURES': str(fixture_path)}
            result = subprocess.run([node, str(root / 'tools' / 'test_session67_requested_audio.cjs')],
                                    cwd=root, env=environment, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    from django.conf import settings
    from django.test.utils import get_runner
    runner = get_runner(settings)(verbosity=1, interactive=False)
    raise SystemExit(bool(runner.run_tests(['tools.tests_session67_requested_audio'])))
