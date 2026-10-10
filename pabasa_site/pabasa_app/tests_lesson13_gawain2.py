"""Lesson 13 word aliases and completion, without access to student records."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from .tests_session4_gawain4_controls import PageParser
from .models import SchoolCalendar, StudentActivityProgress, User
from .views import prescribed_activity_complete, prescribed_activity_progress


class Lesson13Gawain2Tests(SimpleTestCase):
    def test_aliases_and_real_controller_completion_lifecycle(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js required for activity controller tests.')
        html = render_to_string('pabasa_app/lesson_13_gawain_2_page.html', {
            'lesson13_gawain2_data': {'columns': [['lola']], 'progress': {}},
        })
        page = PageParser()
        page.feed(html)
        source = next(s for s in page.scripts if 'targetAliases=' in s)
        harness = Path(settings.BASE_DIR).parent / 'tools' / 'test_lesson13_gawain2.cjs'
        script = 'require(' + json.dumps(str(harness)) + ').run(' + json.dumps(source) + ').catch(e=>{console.error(e);process.exitCode=1});'
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS:', result.stdout)
        self.assertIn('href="' + reverse('assessment') + '"', source)

    def test_completion_button_is_responsive_and_non_wrapping(self):
        html = render_to_string('pabasa_app/lesson_13_gawain_2_page.html', {
            'lesson13_gawain2_data': {'columns': [], 'progress': {'activity_completed': True}},
        })
        self.assertIn('Tapos na ang gawain! 🎉', html)
        self.assertIn('white-space:nowrap', html)
        self.assertIn('prefers-reduced-motion:reduce', html)

    def test_completion_typography_uses_reference_font_and_weights(self):
        html = render_to_string('pabasa_app/lesson_13_gawain_2_page.html', {
            'lesson13_gawain2_data': {'columns': [], 'progress': {'activity_completed': True}},
        })
        reference = render_to_string('pabasa_app/session_4_gawain_5_page.html', {
            'session4_gawain5_data': {'progress': {'activity_completed': True}},
        })
        family = 'font-family:Fredoka,Nunito,"Segoe UI",sans-serif'
        self.assertIn(family, reference)
        for tag, weight in (('h1', '900'), ('p', '700'), ('a', '900')):
            rules = re.findall(re.escape('.lesson-13-gawain-2-page .lesson-13-completion ' + tag + '{') + r'([^}]+)', html)
            self.assertTrue(any(family in rule and 'font-weight:' + weight in rule for rule in rules), tag)
        self.assertIn("fredoka-one.one-regular.ttf", html)
        self.assertIn('font-size:clamp(1.5rem,4.5vw,1.75rem)', html)

    def test_help_variant_is_scoped_and_modal_ids_are_unique(self):
        html = render_to_string('pabasa_app/lesson_13_gawain_2_page.html', {
            'lesson13_gawain2_data': {'columns': [['lola']], 'progress': {}},
        })
        page = PageParser()
        page.feed(html)
        self.assertEqual(len(page.ids), len(set(page.ids)))
        for text in ('1. Basahin ang salita', '2. Magsalita nang malinaw',
                     '3. Magpatuloy sa gawain', 'NAINTINDIHAN KO!'):
            self.assertIn(text, html)
        other = render_to_string('pabasa_app/session5_prescribed_controls.html',
                                 {'prefix': 'other', 'help_text': 'Original instructions'})
        self.assertIn('Original instructions', other)
        self.assertNotIn('NAINTINDIHAN KO!', other)

    def test_modal_handlers_save_before_navigation_and_allow_retry(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js required for isolated modal tests.')
        html = render_to_string('pabasa_app/lesson_13_gawain_2_page.html', {
            'lesson13_gawain2_data': {'columns': [['lola']], 'progress': {}},
        })
        page = PageParser()
        page.feed(html)
        controller = next(s for s in page.scripts if 'targetAliases=' in s)
        modal = next(s for s in page.scripts if 'pauseReturnBound' in s)
        harness = Path(settings.BASE_DIR).parent / 'tools' / 'test_lesson13_gawain2_modals.cjs'
        source = 'require(' + json.dumps(str(harness)) + ').run(' + json.dumps(controller) + ',' + json.dumps(modal) + ').catch(e=>{console.error(e);process.exitCode=1});'
        result = subprocess.run([node], input=source, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class Lesson13Gawain2PersistenceTests(TestCase):
    """Only Django's disposable test database is used by these tests."""
    def setUp(self):
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        self.student = User.objects.create(
            custom_id='L13G2-TEST', role='student', first_name='Disposable', last_name='Reader',
            sex='X', birth_month=1, birth_day=1, birth_year=2018,
            email='l13g2@example.test', password_hash='test', school_calendar=self.calendar,
        )
        self.lifecycle = {'state': 'ARAL_ACTIVE', 'school_calendar': self.calendar, 'term': 1}
        self.key = 'lesson-13-gawain-2'

    def post(self, view, payload=None):
        request = RequestFactory().post('/test/', data=json.dumps(payload or {}), content_type='application/json')
        request.session = {'user_id': self.student.id, 'user_role': 'student'}
        request._dont_enforce_csrf_checks = True
        with patch('pabasa_app.views._active_prescribed_student', return_value=self.student), \
             patch('pabasa_app.views._current_learning_context', return_value=self.lifecycle), \
             patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True):
            return view(request, self.key)

    def test_backend_rejects_incomplete_items(self):
        for count in (0, 8):
            self.post(prescribed_activity_progress, {'state': {'current_index': count, 'completed_items': count}})
            response = self.post(prescribed_activity_complete)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(StudentActivityProgress.objects.get(student=self.student).activity_completed)

    def test_completion_is_persisted_and_late_save_cannot_clear_it(self):
        self.post(prescribed_activity_progress, {'state': {'current_index': 8, 'completed_items': 9, 'phase': 'complete'}})
        response = self.post(prescribed_activity_complete)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['success'])
        self.post(prescribed_activity_progress, {'state': {'current_index': 0, 'completed_items': 0, 'phase': 'active'}})
        progress = StudentActivityProgress.objects.get(student=self.student)
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 9)
        self.assertEqual(progress.correct_items, 9)
        self.assertEqual(progress.state['phase'], 'complete')
