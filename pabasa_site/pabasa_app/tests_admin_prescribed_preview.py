import json
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from . import views
from .prescribed_activity_catalog import active_prescribed_activities
from .prescribed_workbook import apply_event, get_activity, initial_s9_a1_state
from .models import User


class AdminPrescribedPreviewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def admin_request(self, request):
        request.session = {'user_id': 1, 'user_role': 'admin'}
        request._dont_enforce_csrf_checks = True
        return request

    def test_sessions_include_exact_student_catalog_and_legacy_activities(self):
        sessions = views._admin_prescribed_sessions()
        self.assertEqual([session['number'] for session in sessions], list(range(1, 16)))
        keys = [activity['activity_key'] for session in sessions for activity in session['activities']]
        expected = {activity['activity_key'] for activity in active_prescribed_activities()}
        expected.update(activity['activity_key'] for activity in views.LEGACY_SESSION_PROGRESS_ACTIVITIES)
        self.assertEqual(set(keys), expected)
        self.assertEqual(len(keys), len(expected))

    def test_legacy_preview_renders_the_existing_student_view(self):
        request = self.admin_request(self.factory.get('/screen/'))
        with patch.object(views, 'lesson_1_gawain_1_page', return_value=HttpResponse('<head></head><body>original student activity</body>')) as original:
            response = views.admin_prescribed_activity_screen(request, 'lesson-1-gawain-1')
        original.assert_called_once_with(request)
        self.assertTrue(request._admin_prescribed_preview)
        self.assertIn(b'original student activity', response.content)
        self.assertIn(b'admin_prescribed_preview.js', response.content)

    def test_workbook_event_uses_original_evaluator_without_database_queries(self):
        key = 'aral-s9-a1-family-drawing'
        state = initial_s9_a1_state()
        event = {'action': 'draft', 'draft': {'text': 'My family'}, 'revision': 0}
        request = self.admin_request(self.factory.post('/event/', json.dumps({**event, '_preview_state': state}),
            content_type='application/json'))
        expected = apply_event(get_activity(key), state, event)
        response = views.admin_prescribed_workbook_event(request, key)
        result = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(result['preview_only'])
        expected['revision'] = 1
        self.assertEqual(result['state'], expected)

    def test_students_cannot_access_admin_preview_event(self):
        request = self.factory.post('/event/', '{}', content_type='application/json')
        request.session = {'user_id': 48, 'user_role': 'student'}
        self.assertEqual(views.admin_prescribed_workbook_event(request, 'aral-s9-a1-family-drawing').status_code, 302)


class Session6Gawain6AdminPreviewTests(TestCase):
    def test_admin_screen_uses_the_same_shared_basahin_button_as_students(self):
        admin = User.objects.create(custom_id='G6-PREVIEW-ADMIN', role='admin', first_name='Preview',
                                    last_name='Admin', middle_initial='', suffix='', sex='female',
                                    birth_month=1, birth_day=1, birth_year=1990,
                                    email='g6-preview-admin@example.com', password_hash='hashed')
        request = RequestFactory().get('/admin/prescribed/lesson-17-18-gawain-6/screen/')
        request.session = {'user_id': admin.id, 'user_role': 'admin'}
        response = views.admin_prescribed_activity_screen(request, 'lesson-17-18-gawain-6')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-basahin-button', html)
        self.assertIn('window.Basahin.bindActivity', html)
        self.assertIn('admin_prescribed_preview.js', html)
