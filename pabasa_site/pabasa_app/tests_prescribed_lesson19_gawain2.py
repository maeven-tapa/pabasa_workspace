import json
import shutil
import subprocess
import tempfile
import uuid
from html.parser import HTMLParser
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import School, StudentActivityProgress, User
from .prescribed_test_fixtures import prescribed_term_fixture


class _InlineJavaScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'script':
            return
        attributes = dict(attrs)
        if attributes.get('type', '').lower() == 'application/json':
            self._script = None
        else:
            self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self._script is not None:
            self.scripts.append(''.join(self._script))
            self._script = None


class PrescribedLesson19Gawain2TemplateSyntaxTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.node = shutil.which('node')

    def test_rendered_inline_javascript_passes_node_syntax_check(self):
        if not self.node:
            self.skipTest('Node.js is required to syntax-check rendered activity JavaScript.')
        context = {
            'prescribed_activity_data': {
                'activity_key': 'session-7-lesson-19-gawain-2',
                'session_key': 'session-7', 'session_number': 7,
                'lesson_number': 19, 'gawain_number': 2,
                'display_title': 'Lesson 19: Gawain 2',
                'title': 'Isulat ang Nawawalang Pantig',
                'instruction': 'Basahin ang ngalan ng larawan. Pagkatapos, isulat ang nawawalang pantig.',
                'items': [{'id': 'daan', 'word': 'daan', 'stem': '__an', 'answer': 'da',
                           'alt_text': 'Larawan ng daan', 'image_url': '/static/daan.png',
                           'blank_length': 2}],
                'progress_url': reverse('prescribed_activity_progress', kwargs={'activity_key': 'session-7-lesson-19-gawain-2'}),
                'completion_url': reverse('prescribed_activity_complete', kwargs={'activity_key': 'session-7-lesson-19-gawain-2'}),
                'read_aloud_url': reverse('reading_read_aloud_api'),
                'transcribe_url': reverse('reading_transcribe_api'),
                'progress': {'activity_completed': False, 'state': {'phase': 'intro'}},
            },
            'prefix': 'prescribed-s7-l19-g2',
            'help_text': 'Basahin ang salita, pagkatapos isulat ang nawawalang pantig.',
        }
        rendered = render_to_string('pabasa_app/session7_missing_syllable_page.html', context)
        parser = _InlineJavaScriptParser()
        parser.feed(rendered)
        self.assertTrue(parser.scripts, 'Expected an inline activity script in the rendered page.')
        activity_scripts = [script for script in parser.scripts if 'async function listen(n)' in script]
        self.assertEqual(len(activity_scripts), 1, 'Expected one oral-audio handler in the rendered activity.')
        self.assertNotIn('listen=async function', activity_scripts[0])
        scripts_to_check = parser.scripts + [
            (Path(__file__).parent / 'static' / 'pabasa_app' / 'js' / 'session7_intro_modal.js').read_text(encoding='utf-8'),
        ]

        with tempfile.TemporaryDirectory() as directory:
            for index, script in enumerate(scripts_to_check):
                script_path = Path(directory) / f'inline-{index}.js'
                script_path.write_text(script, encoding='utf-8')
                result = subprocess.run([self.node, '--check', str(script_path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


class PrescribedLesson19Gawain2RestartTests(TestCase):
    key = 'session-7-lesson-19-gawain-2'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Lesson 19 {token}', code=f'L19-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Lesson 19', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2018, email=f'lesson19-g2-{token}@example.com', password_hash='hashed',
            school_record=school,
        )
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.save(update_fields=['active_session_key', 'updated_at'])
        prescribed_term_fixture(self.student)
        self.url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})

    def post(self, body):
        return self.client.post(self.url, data=json.dumps(body), content_type='application/json')

    def test_restart_returns_activity_to_intro_even_after_saved_progress(self):
        progressed = self.post({
            'state': {'phase': 'oral_reading', 'completed_oral_reads': [0], 'state_version': 1},
        })
        self.assertEqual(progressed.status_code, 200)
        self.assertEqual(progressed.json()['progress']['state']['phase'], 'written_answer')

        restarted = self.post({'reset': True})

        self.assertEqual(restarted.status_code, 200)
        payload = restarted.json()['progress']
        self.assertFalse(payload['activity_completed'])
        self.assertEqual(payload['completed_items'], 0)
        self.assertEqual(payload['state']['phase'], 'intro')
        self.assertEqual(payload['state']['current_item_index'], 0)
        self.assertEqual(payload['state']['completed_oral_reads'], [])
        self.assertEqual(payload['state']['written_answers'], [])
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertFalse(saved.activity_completed)
        self.assertEqual(saved.current_index, 0)
        self.assertEqual(saved.completed_items, 0)
