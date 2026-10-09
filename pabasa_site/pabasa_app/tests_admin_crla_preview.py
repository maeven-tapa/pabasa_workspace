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
        self.material = SimpleNamespace(id=12, is_active=True, status='published')

    def admin_request(self, request):
        request.session = {'user_id': 1, 'user_role': 'admin'}
        request._dont_enforce_csrf_checks = True
        return request

    def test_resolver_returns_original_published_record(self):
        with patch.object(views, '_get_official_reading_material', return_value=self.material) as resolver:
            self.assertIs(views._admin_published_crla(12), self.material)
        resolver.assert_called_once_with(12)

    def test_resolver_rejects_missing_inactive_or_unpublished_records(self):
        for material in (None, SimpleNamespace(is_active=False, status='published'),
                         SimpleNamespace(is_active=True, status='draft')):
            with self.subTest(material=material), patch.object(views, '_get_official_reading_material', return_value=material):
                self.assertIsNone(views._admin_published_crla(12))

    def test_test_button_uses_original_record_without_student_selection(self):
        request = self.admin_request(self.factory.get('/test/'))
        with patch.object(views, '_admin_published_crla', return_value=self.material) as resolver:
            response = views.admin_official_reading_assessment_test(request, 12)
        resolver.assert_called_once_with(12)
        url = urlsplit(response.url)
        self.assertEqual(url.path, '/dashboard/assessment/reading_ui/word/')
        query = parse_qs(url.query)
        self.assertEqual(query['official_assessment_id'], ['12'])
        self.assertEqual(query['admin_preview'], ['1'])
        self.assertTrue(query['admin_preview_token'][0])
        self.assertNotIn('admin_student_id', query)

    def test_launch_rejects_unavailable_record(self):
        request = self.admin_request(self.factory.get('/test/'))
        with patch.object(views, '_admin_published_crla', return_value=None):
            with self.assertRaises(PermissionDenied):
                views.admin_official_reading_assessment_test(request, 12)

    def test_score_without_student_uses_existing_published_record(self):
        request = self.admin_request(self.factory.post(
            '/api/admin/crla-preview/score/',
            json.dumps({'material_id': 12, 'stage': 'completed', 'part1_total_score': 6}),
            content_type='application/json',
        ))
        with patch.object(views, '_admin_published_crla', return_value=self.material):
            response = views.admin_crla_preview_score(request)
        self.assertEqual(json.loads(response.content)['reader_classification'], 'Low Emerging Reader')

    def test_score_uses_student_rules_without_persisting(self):
        payload = {
            'material_id': '12', 'stage': 'completed', 'part1_total_score': 28,
            'story_number': 1, 'story_total_words': 100, 'words_read': 70,
            'miscues': 30, 'duration_seconds': 60, 'correct_answers': 4,
            'classification': 'Forged browser label', 'story_read_percent': 100,
        }
        request = self.admin_request(self.factory.post(
            '/api/admin/crla-preview/score/',
            json.dumps(payload), content_type='application/json',
        ))
        with patch.object(views, '_admin_published_crla', return_value=self.material):
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
                views._admin_crla_preview_context(request)

    def test_preview_context_uses_same_official_record_on_all_reader_surfaces(self):
        for surface in ('word', 'sentence', 'para'):
            request = self.factory.get(f'/reader/{surface}/', {'admin_preview': '1', 'official_assessment_id': '12'})
            with self.subTest(surface=surface), \
                    patch.object(views, '_current_user', return_value=SimpleNamespace(role='admin', is_archived=False)), \
                    patch.object(views, '_admin_published_crla', return_value=self.material) as resolver:
                context = views._admin_crla_preview_context(request)
            resolver.assert_called_once_with(12)
            self.assertTrue(context['is_admin_preview'])
            self.assertEqual(context['admin_preview_return_url'], '/dashboard/admin/official-reading-assessments/')

    def test_preview_context_rejects_regular_material_reader(self):
        request = self.factory.get('/reader/', {'admin_preview': '1', 'id': '12'})
        with patch.object(views, '_current_user', return_value=SimpleNamespace(role='admin', is_archived=False)):
            with self.assertRaises(PermissionDenied):
                views._admin_crla_preview_context(request)

    def test_score_rejects_unavailable_record(self):
        request = self.admin_request(self.factory.post('/api/admin/crla-preview/score/',
            json.dumps({'material_id': 12}), content_type='application/json'))
        with patch.object(views, '_admin_published_crla', return_value=None):
            self.assertEqual(views.admin_crla_preview_score(request).status_code, 403)
