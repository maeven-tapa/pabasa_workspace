"""ARAL directory status follows scoped Live CRLA progress, not invented grades."""
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, LiveAssessmentSession, Material
from .tests_class_management_sync import ManagementSyncFixtures


class LiveProgressFixtures(ManagementSyncFixtures):
    def setUp(self):
        super().setUp()
        login = self.client.session
        login.set_expiry(settings.SESSION_COOKIE_AGE)
        login.save()
        self.material = Material.objects.get(system_assessment_key='bosy_crla_pretest')
        self.live = LiveAssessmentSession.objects.create(
            id='directory-live-progress', teacher=self.teacher, section=self.section,
            material=self.material, student_ids=[self.student.pk], student_count=1,
            status='started', start_at=timezone.make_aware(datetime(2026, 10, 12)),
            batch_assignments={str(self.student.pk): 1},
            student_states={str(self.student.pk): {'status': 'reading', 'recovery_state': {'stage': 'words'}}},
        )

    def directory(self, **params):
        return self.client.get(reverse('get_teacher_students_api'), {
            'sync': 'directory', 'section_id': self.section.pk, 'term': '1',
            'term_mode': 'manual', **params,
        })

    def set_state(self, **state):
        self.live.student_states = {str(self.student.pk): state}
        self.live.save(update_fields=['student_states', 'updated_at'])

    def official_result(self):
        return Assessment.objects.create(
            teacher=self.teacher, student=self.student, enrollment=self.enrollment,
            section=self.section, material=self.material, official_term=1,
            system_assessment_key='bosy_crla_pretest', system_assessment_phase='pretest',
            attempt_status='completed', completed_at=timezone.now(),
            crla_classification='Low Emerging Reader', classification='Low Emerging Reader',
            title='Disposable directory result', code='DIRECTORY-LIVE-RESULT', total_score=4,
        )


class StudentsLiveProgressTests(LiveProgressFixtures, TestCase):
    def test_saved_resumed_and_completed_states_do_not_invent_an_official_result(self):
        for state, expected in [
            ({'status': 'reading', 'recovery_state': {'stage': 'words'}}, 'in_progress'),
            ({'status': 'reading', 'participation_status': 'save_requested'}, 'saving'),
            ({'status': 'reading', 'participation_status': 'saved', 'recovery_state': {'stage': 'words'}}, 'saved'),
            ({'status': 'paused', 'recovery_state': {'stage': 'words'}}, 'paused'),
            ({'status': 'completed', 'recovery_state': {'temporary_completed': True, 'stage': 'completed'}}, 'completed'),
            # Completed students remain completed when another participant is saved.
            ({'status': 'completed', 'participation_status': 'saved', 'recovery_state': {'temporary_completed': True}}, 'completed'),
        ]:
            with self.subTest(expected=expected):
                self.set_state(**state)
                before = list(LiveAssessmentSession.objects.values())
                payload = self.directory().json()
                student = payload['students'][0]
                self.assertEqual(student['crla_progress']['status'], expected)
                self.assertEqual(student['crla_progress']['session_url'], reverse('live_assessment_session', args=[self.live.pk]))
                self.assertEqual(student['reading_level'], 'Pending')
                self.assertIsNone(student['crla_result'])
                self.assertFalse(student['has_completed_assessment'])
                self.assertFalse(payload['crla']['finalize_ready'])
                self.assertFalse(Assessment.objects.filter(student=self.student).exists())
                self.assertEqual(list(LiveAssessmentSession.objects.values()), before)

    def test_official_result_replaces_temporary_display(self):
        self.set_state(status='completed', recovery_state={'temporary_completed': True})
        result = self.official_result()
        before = Assessment.objects.filter(pk=result.pk).values().get()
        student = self.directory().json()['students'][0]
        self.assertIsNone(student['crla_progress'])
        self.assertEqual(student['reading_level'], 'Low Emerging Reader')
        self.assertTrue(student['has_completed_assessment'])
        self.assertIsNotNone(student['crla_result'])
        self.assertEqual(Assessment.objects.filter(pk=result.pk).values().get(), before)

    def test_foreign_teacher_section_term_phase_and_ended_sessions_do_not_supply_status(self):
        for fields in [
            {'teacher': self.other_teacher}, {'section': self.other_section},
            {'status': 'ended'}, {'status': 'cancelled'},
            {'start_at': timezone.make_aware(datetime(2025, 10, 12))},
            {'material': Material.objects.get(system_assessment_key='eosy_crla_posttest')},
            {'student_ids': []},
        ]:
            with self.subTest(fields=list(fields)):
                originals = {key: getattr(self.live, key) for key in fields}
                for key, value in fields.items():
                    setattr(self.live, key, value)
                self.live.save()
                self.assertIsNone(self.directory().json()['students'][0]['crla_progress'])
                for key, value in originals.items():
                    setattr(self.live, key, value)
                self.live.save()
        self.assertIsNone(self.directory(term='2').json()['students'][0]['crla_progress'])
        self.assertEqual(self.directory(section_id=self.other_section.pk).status_code, 403)

    def test_waiting_and_skipped_students_are_not_reported_as_completed(self):
        for state in [
            {'status': 'waiting'}, {'status': 'skipped'}, {'status': 'missed'},
            {'status': 'completed'},
        ]:
            self.set_state(**state)
            self.assertIsNone(self.directory().json()['students'][0]['crla_progress'])


class StudentsLiveProgressBrowserTests(LiveProgressFixtures, StaticLiveServerTestCase):
    def test_status_changes_and_official_result_in_real_browser(self):
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_students_live_progress.cjs'
        env = dict(os.environ, PABASA_SYNC_SERVER=self.live_server_url,
            PABASA_SYNC_COOKIE=self.client.cookies['sessionid'].value)
        with patch('pabasa_app.views._dashboard_context', side_effect=lambda request, role, extra: dict(extra, nav_role=role)):
            process = subprocess.Popen(['node', str(script)], env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: process.poll() is None and process.kill())
            messages = []
            for line in process.stdout:
                item = json.loads(line)
                action = item.get('command')
                if not action:
                    messages.append(item)
                    continue
                if action == 'saved':
                    self.set_state(status='reading', participation_status='saved', recovery_state={'stage': 'words'})
                elif action == 'resumed':
                    self.set_state(status='reading', recovery_state={'stage': 'words'})
                elif action == 'completed':
                    self.set_state(status='completed', recovery_state={'temporary_completed': True, 'stage': 'completed'})
                elif action == 'official':
                    self.official_result()
                    self.live.status = 'ended'
                    self.live.save(update_fields=['status'])
                else:
                    self.fail(f'Unknown command: {action}')
                process.stdin.write('ok\n')
                process.stdin.flush()
            process.wait(timeout=120)
            if process.returncode:
                auth = Session.objects.filter(session_key=self.client.cookies['sessionid'].value).first()
                print(json.dumps({'fixture_session_exists': bool(auth),
                    'fixture_user_matches': bool(auth and auth.get_decoded().get('user_id') == self.teacher.pk),
                    'fixture_teacher_exists': type(self.teacher).objects.filter(pk=self.teacher.pk, is_archived=False, account_status='active').exists()}))
            self.assertEqual(process.returncode, 0, process.stderr.read())
        self.assertEqual(messages[-1]['result'], 'passed')
        print(json.dumps(messages[-1]))
