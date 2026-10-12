"""Real Chrome exercises the existing Students controls and API against disposable data."""
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from .models import Assessment, Enrollment, StudentActivityProgress, StoryReadingProgress
from .tests_students_terms import StudentsTermFixtures


class StudentsTermsBrowserTests(StudentsTermFixtures, StaticLiveServerTestCase):
    def test_independent_historical_selections_calendar_poll_and_recovery(self):
        models = [Assessment, Enrollment, StudentActivityProgress, StoryReadingProgress]
        before = [list(model.objects.order_by('pk').values()) for model in models]
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_students_terms.cjs'
        env = dict(os.environ, PABASA_SYNC_SERVER=self.live_server_url,
            PABASA_SYNC_COOKIE=self.client.cookies['sessionid'].value,
            PABASA_STUDENTS_URL=reverse('students'),
            PABASA_STUDENTS_MATERIALS=json.dumps({term: material.pk for term, material in self.materials.items()}))
        def context(request, role, extra):
            return dict(extra, nav_role=role, user_id=self.teacher.pk)
        with patch('pabasa_app.views._dashboard_context', side_effect=context):
            process = subprocess.Popen(['node', str(script)], env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: process.poll() is None and process.kill())
            messages = []
            for line in process.stdout:
                item = json.loads(line)
                if 'command' not in item:
                    messages.append(item)
                    continue
                action = item['command']
                if action.startswith('term'):
                    self.set_term(int(action[-1]))
                elif action == 'no_term':
                    self.calendar.events.all().delete()
                else:
                    self.fail(f'Unknown browser command: {action}')
                process.stdin.write('ok\n')
                process.stdin.flush()
            process.wait(timeout=120)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        self.assertEqual([list(model.objects.order_by('pk').values()) for model in models], before)
        self.assertEqual(messages[-1]['result'], 'passed')
        print(json.dumps(messages[-1]))
