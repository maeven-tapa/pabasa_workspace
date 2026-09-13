from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import Material, PracticeDebugSettings
from .views import (
    _practice_difficulty_is_accessible,
    _practice_game_progression,
    admin_practice_assessment,
)


class PracticeDebugTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        for language in ('English', 'Filipino'):
            for mode in ('free', 'color', 'hunt'):
                Material.objects.create(
                    title='Hard practice', type='practice', source_type='shared',
                    is_system_owned=True, status='published', is_active=True,
                    difficulty_level='hard', language=language,
                    content_json={'mode': mode, 'difficulty': 'hard', 'level': 'level_5', 'items': ['cat']},
                )

    def test_toggle_unlocks_all_modes_and_languages_without_granting_progress(self):
        for enabled in (False, True, False):
            PracticeDebugSettings.objects.update_or_create(pk=1, defaults={'unlock_all': enabled})
            for language in ('English', 'Filipino'):
                for mode in ('free', 'color', 'hunt'):
                    with self.subTest(enabled=enabled, language=language, mode=mode):
                        progression = _practice_game_progression(mode, language=language)
                        hard = progression['sections'][-1]
                        self.assertEqual(hard['unlocked'], enabled)
                        self.assertEqual(hard['levels'][-1]['state'], 'unlocked' if enabled else 'locked')
                        self.assertEqual(hard['levels'][0]['state'], 'content_unavailable')
                        self.assertEqual(progression['summary']['stars_earned'], 0)
                        self.assertEqual(progression['summary']['completed_levels'], 0)
                        self.assertEqual(_practice_difficulty_is_accessible(mode, 'hard'), enabled)

    def request_toggle(self, role, value='on'):
        request = self.factory.post(reverse('admin_practice_assessment'), {'unlock_all': value, 'language': 'Filipino'})
        request.session = {'user_id': 1, 'user_role': role}
        request._dont_enforce_csrf_checks = True
        return admin_practice_assessment(request)

    def test_only_admin_can_change_global_setting(self):
        for role in ('student', 'teacher', 'principal'):
            self.assertEqual(self.request_toggle(role).status_code, 302)
            self.assertFalse(PracticeDebugSettings.objects.exists())
        self.assertEqual(self.request_toggle('admin').status_code, 302)
        self.assertTrue(PracticeDebugSettings.objects.get(pk=1).unlock_all)
        self.request_toggle('admin', 'off')
        self.assertFalse(PracticeDebugSettings.objects.get(pk=1).unlock_all)

    def test_csrf_and_invalid_values_are_rejected(self):
        request = self.factory.post(reverse('admin_practice_assessment'), {'unlock_all': 'on'})
        request.session = {'user_id': 1, 'user_role': 'admin'}
        self.assertEqual(admin_practice_assessment(request).status_code, 403)
        self.assertEqual(self.request_toggle('admin', 'invalid').status_code, 400)
        self.assertFalse(PracticeDebugSettings.objects.exists())
