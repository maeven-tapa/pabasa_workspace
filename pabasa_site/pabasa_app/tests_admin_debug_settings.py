from django.test import TestCase
from django.urls import reverse

from .models import PracticeDebugSettings
from . import tests as existing_tests


class AdminDebugSettingsTests(TestCase):
    setUp = existing_tests.AdminSettingsRenderTests.setUp

    def test_debug_controls_are_grouped_with_matching_modals(self):
        response = self.client.get(reverse('admin_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debug Controls')
        for modal_id in ('systemTimeDebugModal', 'prescribedAccessModal',
                         'otpDebugModal', 'practiceDebugModal'):
            self.assertContains(response, f'data-bs-target="#{modal_id}"')
            self.assertContains(response, f'id="{modal_id}"')
        self.assertNotContains(response, 'id="systemTimeDebugPanel"')
        self.assertNotContains(response, 'id="prescribedAccessPanel"')

    def test_practice_debug_can_be_enabled_and_disabled_from_settings(self):
        for value, expected in [('on', True), ('off', False)]:
            response = self.client.post(reverse('admin_settings'), {
                'settings_action': 'set_practice_debug_access', 'unlock_all': value,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(PracticeDebugSettings.objects.get(pk=1).unlock_all, expected)
            self.assertEqual(response.context['practice_debug_unlock_all'], expected)

    def test_invalid_practice_debug_value_preserves_current_setting(self):
        PracticeDebugSettings.objects.create(pk=1, unlock_all=True)
        response = self.client.post(reverse('admin_settings'), {
            'settings_action': 'set_practice_debug_access', 'unlock_all': 'invalid',
        })
        self.assertContains(response, 'Choose on or off for practice debug access.')
        self.assertTrue(PracticeDebugSettings.objects.get(pk=1).unlock_all)

    def test_practice_page_no_longer_contains_debug_toggle(self):
        response = self.client.get(reverse('admin_practice_assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="unlock_all"')

    def test_non_admin_cannot_change_practice_debug_through_settings(self):
        self.user.role = 'student'
        self.user.save(update_fields=['role'])
        session = self.client.session
        session['user_role'] = 'student'
        session.save()
        response = self.client.post(reverse('admin_settings'), {
            'settings_action': 'set_practice_debug_access', 'unlock_all': 'on',
        })
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(PracticeDebugSettings.objects.filter(unlock_all=True).exists())

    def test_demoted_account_with_stale_admin_session_cannot_change_practice_debug(self):
        self.user.role = 'teacher'
        self.user.save(update_fields=['role'])
        response = self.client.post(reverse('admin_settings'), {
            'settings_action': 'set_practice_debug_access', 'unlock_all': 'on',
        })
        self.assertRedirects(response, reverse('auth'), fetch_redirect_response=False)
        self.assertFalse(PracticeDebugSettings.objects.exists())

    def test_archived_admin_with_stale_session_cannot_change_practice_debug(self):
        self.user.is_archived = True
        self.user.save(update_fields=['is_archived'])
        PracticeDebugSettings.objects.create(pk=1, unlock_all=True)
        response = self.client.post(reverse('admin_settings'), {
            'settings_action': 'set_practice_debug_access', 'unlock_all': 'off',
        })
        self.assertRedirects(response, reverse('auth'), fetch_redirect_response=False)
        self.assertTrue(PracticeDebugSettings.objects.get(pk=1).unlock_all)

    def test_legacy_practice_endpoint_also_rejects_stale_admin_sessions(self):
        PracticeDebugSettings.objects.create(pk=1, unlock_all=True)
        for role, archived in [('teacher', False), ('admin', True)]:
            with self.subTest(role=role, archived=archived):
                self.user.role = role
                self.user.is_archived = archived
                self.user.save(update_fields=['role', 'is_archived'])
                response = self.client.post(reverse('admin_practice_assessment'), {
                    'unlock_all': 'off',
                })
                self.assertRedirects(response, reverse('auth'), fetch_redirect_response=False)
                self.assertTrue(PracticeDebugSettings.objects.get(pk=1).unlock_all)
