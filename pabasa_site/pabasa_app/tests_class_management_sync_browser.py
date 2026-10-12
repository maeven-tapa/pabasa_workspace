"""Real section API and Drop Student exercised in Chrome against disposable data."""
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, Enrollment
from .tests_class_management_sync import ManagementSyncFixtures


class ClassManagementSyncBrowserTests(ManagementSyncFixtures, StaticLiveServerTestCase):
    def test_calendar_and_enrollment_live_updates_and_directory_controls(self):
        for number in range(11):
            Enrollment.objects.create(student=self.user(f'learner{number:02d}'), section=self.section)
        term_one = Assessment.objects.create(title='Disposable browser CRLA', code='SYNC-BROWSER-T1',
            teacher=self.teacher, student=self.student, enrollment=self.enrollment, official_term=1,
            system_assessment_key='bosy_crla_pretest', attempt_status='completed',
            completed_at=timezone.now(), crla_classification='Low Emerging Reader')
        original_result = Assessment.objects.filter(pk=term_one.pk).values().get()
        original_enrollment = Enrollment.objects.filter(pk=self.enrollment.pk).values().get()
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_class_management_sync.cjs'
        env = dict(os.environ, PABASA_SYNC_SERVER=self.live_server_url,
            PABASA_SYNC_COOKIE=self.client.cookies['sessionid'].value,
            PABASA_SYNC_URL=reverse('class_management') + f'?section_id={self.section.pk}',
            PABASA_SYNC_SECTION=str(self.section.pk), PABASA_SYNC_STUDENT=str(self.student.pk))
        def context(request, role, extra):
            return dict(extra, nav_role='teacher', user_id=self.teacher.pk)
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
                if action == 'term2':
                    self.set_term(2)
                elif action == 'term2_started':
                    term_two = Assessment.objects.create(title='Disposable started CRLA', code='SYNC-BROWSER-T2',
                        teacher=self.teacher, student=self.student, enrollment=self.enrollment, official_term=2,
                        system_assessment_key='bosy_crla_pretest', attempt_status='started',
                        crla_classification='Developing Reader')
                elif action == 'term2_finalized':
                    term_two.attempt_status = 'completed'
                    term_two.completed_at = timezone.now()
                    term_two.save()
                elif action == 'term3_finalized':
                    Assessment.objects.create(title='Disposable Term 3 CRLA', code='SYNC-BROWSER-T3',
                        teacher=self.teacher, student=self.student, enrollment=self.enrollment, official_term=3,
                        system_assessment_key='bosy_crla_pretest', attempt_status='completed',
                        completed_at=timezone.now(), crla_classification='Transitioning Reader')
                elif action == 'aral_exit':
                    self.student.preference = {'reading_assessment_state': {'aral_exit_override': True,
                        'aral_exit_scope': {'term': 1, 'phase': 'pretest'}, 'aral_manual_status': 'ineligible'}}
                    self.student.save()
                elif action == 'term3':
                    self.set_term(3)
                elif action == 'enroll':
                    newcomer = self.user('newcomer')
                    self.section.add_student(newcomer)
                elif action == 'metadata':
                    newcomer.email = 'updated@sync.example.invalid'
                    newcomer.save()
                elif action == 'transfer':
                    self.other_section.add_student(newcomer)
                elif action == 'reactivate':
                    self.section.add_student(newcomer)
                elif action == 'no_term':
                    self.calendar.events.all().delete()
                process.stdin.write('ok\n')
                process.stdin.flush()
            process.wait(timeout=120)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        self.assertEqual(Assessment.objects.filter(pk=term_one.pk).values().get(), original_result)
        self.assertEqual(Enrollment.objects.filter(pk=self.enrollment.pk).values().get(), original_enrollment)
        self.assertEqual(messages[-1]['result'], 'passed')
        self.assertEqual(Enrollment.objects.filter(section=self.section, status='active', is_active=True).count(), 12)
        self.assertEqual(Enrollment.objects.filter(section=self.other_section, status='active', is_active=True).count(), 0)
        print(json.dumps(messages[-1]))
