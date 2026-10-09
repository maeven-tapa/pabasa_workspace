import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase

from . import views
from .scoring import crla_part2_profile, crla_reading_profile


class AdminCrlaPreviewTests(SimpleTestCase):
    """No database queries/writes are allowed in these preview boundary tests."""

    def setUp(self):
        self.factory = RequestFactory()
        self.student = SimpleNamespace(id=48, custom_id='G2-0005')
        self.material = SimpleNamespace(id=12, is_active=True, status='published')

    def admin_request(self, request):
        request.session = {'user_id': 1, 'user_role': 'admin'}
        request._dont_enforce_csrf_checks = True
        return request

    def test_resolver_returns_the_original_selected_record(self):
        with patch.object(views, '_get_official_reading_material', return_value=self.material), \
                patch.object(views, '_official_material_phase', return_value='pretest'), \
                patch.object(views, '_official_reading_assessments_for_student', return_value=[{'id': 12}]) as selector:
            self.assertIs(views._admin_crla_material_for_student(self.student, 12), self.material)
            selector.assert_called_once_with(self.student, {'available': True, 'assessment_type': 'pretest'})

    def test_resolver_rejects_another_version(self):
        with patch.object(views, '_get_official_reading_material', return_value=self.material), \
                patch.object(views, '_official_material_phase', return_value='pretest'), \
                patch.object(views, '_official_reading_assessments_for_student', return_value=[{'id': 99}]):
            self.assertIsNone(views._admin_crla_material_for_student(self.student, 12))

    def test_launch_uses_original_id_and_shared_student_reader(self):
        request = self.admin_request(self.factory.get('/test/launch/', {'student_id': 'G2-0005'}))
        with patch.object(views, '_admin_selected_student', return_value=self.student), \
                patch.object(views, '_admin_crla_material_for_student', return_value=self.material):
            response = views.admin_official_reading_assessment_test_launch(request, 12)
        url = urlsplit(response.url)
        self.assertEqual(url.path, '/dashboard/assessment/reading_ui/word/')
        query = parse_qs(url.query)
        self.assertEqual(query['official_assessment_id'], ['12'])
        self.assertEqual(query['admin_student_id'], ['48'])
        self.assertEqual(query['admin_preview'], ['1'])
        self.assertTrue(query['admin_preview_token'][0])

    def test_launch_rejects_a_selection_mismatch(self):
        request = self.admin_request(self.factory.get('/test/launch/'))
        with patch.object(views, '_admin_selected_student', return_value=self.student), \
                patch.object(views, '_admin_crla_material_for_student', return_value=None):
            with self.assertRaises(PermissionDenied):
                views.admin_official_reading_assessment_test_launch(request, 12)

    def test_score_uses_student_rules_without_persisting(self):
        payload = {
            'material_id': '12', 'stage': 'completed', 'part1_total_score': 28,
            'story_number': 1, 'story_total_words': 100, 'words_read': 70,
            'miscues': 30, 'duration_seconds': 60, 'correct_answers': 4,
            'classification': 'Forged browser label', 'story_read_percent': 100,
        }
        request = self.admin_request(self.factory.post(
            '/api/admin/crla-preview/score/?admin_student_id=48',
            json.dumps(payload), content_type='application/json',
        ))
        with patch.object(views, '_admin_selected_student', return_value=self.student), \
                patch.object(views, '_admin_crla_material_for_student', return_value=self.material):
            response = views.admin_crla_preview_score(request)
        result = json.loads(response.content)
        profile = crla_part2_profile(100, 70, 30, 60, 4)
        expected = crla_reading_profile(28, 1, profile['passage_accuracy_percent'], 4)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(result['preview_only'])
        self.assertEqual(result['reader_classification'], expected)
        self.assertEqual(result['student_end_assessment_state']['passage_accuracy_percent'], 70)
        self.assertIsNone(result['next_url'])

    def test_scoring_is_admin_only(self):
        request = self.factory.post('/api/admin/crla-preview/score/', '{}', content_type='application/json')
        request.session = {'user_id': 48, 'user_role': 'student'}
        self.assertEqual(views.admin_crla_preview_score(request).status_code, 302)

    def test_preview_context_rejects_non_admin(self):
        request = self.factory.get('/reader/', {'admin_preview': '1'})
        request.session = {'user_id': 48, 'user_role': 'student'}
        with patch.object(views, '_current_user', return_value=SimpleNamespace(role='student', is_archived=False)):
            with self.assertRaises(PermissionDenied):
                views._admin_material_preview_context(request)
