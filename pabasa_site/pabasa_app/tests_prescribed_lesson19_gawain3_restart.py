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


class _ActivityScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.current = None if dict(attrs).get('type') == 'application/json' else []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            self.scripts.append(''.join(self.current))
            self.current = None


class Lesson19Gawain3ScriptTests(SimpleTestCase):
    def test_rendered_activity_script_is_valid_javascript(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for the JavaScript syntax check.')
        rendered = render_to_string('pabasa_app/session7_circle_word_page.html', {
            'prescribed_activity_data': {'activity_key': 'session-7-lesson-19-gawain-3',
                                         'items': [], 'progress': {'state': {'phase': 'intro'}}},
            'prefix': 'prescribed-s7-l19-g3',
        })
        parser = _ActivityScripts()
        parser.feed(rendered)
        activity = [script for script in parser.scripts if 'async function read(index' in script]
        self.assertEqual(len(activity), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'activity.js'
            path.write_text(activity[0], encoding='utf-8')
            result = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class Lesson19Gawain3RestartTests(TestCase):
    key = 'session-7-lesson-19-gawain-3'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Gawain 3 {token}', code=f'G3-{token}')
        student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Reader', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2018, email=f'g3-{token}@example.com', password_hash='hashed',
            school_record=school,
        )
        session = self.client.session
        session.update({'user_id': student.id, 'user_role': 'student', 'email': student.email})
        session.save()
        prescribed_term_fixture(student)
        self.student = student
        self.url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})

    def post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload), content_type='application/json')

    def test_restart_clears_oral_progress_and_attempts(self):
        progress = self.post({'state': {
            'phase': 'oral_reading', 'orally_completed_words': {'0': [0]},
            'stt_attempt_counts': {'0:1': 2}, 'state_version': 1,
        }})
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.json()['progress']['state']['orally_completed_words']['0'], [0])

        restarted = self.post({'reset': True})
        self.assertEqual(restarted.status_code, 200)
        state = restarted.json()['progress']['state']
        self.assertEqual(state['phase'], 'intro')
        self.assertEqual(state['current_item_index'], 0)
        self.assertEqual(state['orally_completed_words']['0'], [])
        self.assertEqual(state['stt_attempt_counts']['0:1'], 0)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual(saved.current_index, 0)
        self.assertEqual(saved.completed_items, 0)
        self.assertFalse(saved.activity_completed)
