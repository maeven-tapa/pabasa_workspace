from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.hashers import check_password, make_password

from .models import Material, User


class ProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="TCH-0001",
            role="teacher",
            first_name="Old",
            last_name="Name",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="old@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_profile_page_includes_hidden_save_flag(self):
        response = self.client.get(reverse("profile"))

        self.assertContains(response, 'name="save_account_details" value="true"', html=False)

    def test_profile_post_updates_user_record(self):
        response = self.client.post(
            reverse("profile"),
            {
                "save_account_details": "true",
                "first_name": "New",
                "last_name": "Name",
                "middle_initial": "Q",
                "suffix": "Jr.",
                "email": "new@example.com",
                "bio": "Updated bio",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.middle_initial, "Q")
        self.assertEqual(self.user.suffix, "Jr.")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertIn({"profile_info": {"bio": "Updated bio"}}, self.user.tags)


class PracticeReaderMaterialTests(TestCase):
    def test_word_reader_receives_active_published_practice_items(self):
        Material.objects.create(
            title="Easy syllables",
            item_type="word",
            content_text="HA\nhe\nhi\nho\nhu",
            content_json={"source": "admin_practice", "difficulty": "easy", "items": ["HA", "he", "hi", "ho", "hu"]},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )
        Material.objects.create(
            title="Draft syllables",
            item_type="word",
            content_text="draft",
            content_json={"items": ["draft"]},
            status="draft",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="practiceMaterialsData"', html=False)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)
        self.assertNotContains(response, "Draft syllables")

    def test_word_reader_parses_comma_separated_content_text_when_json_items_missing(self):
        Material.objects.create(
            title="Comma syllables",
            item_type="word",
            content_text="HA, he, hi, ho, hu",
            content_json={},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)


class SettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="STD-0001",
            role="student",
            first_name="Settings",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="settings@example.com",
            password_hash=make_password("old-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_settings_password_change_updates_user_hash(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(check_password("new-password", self.user.password_hash))

    def test_settings_saves_push_notification_preferences(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "save_notifications",
                "push_enabled": "on",
                "new_materials": "on",
                "progress_updates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Push notification preferences saved.")

        self.user.refresh_from_db()
        self.assertIn({
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": False,
                "new_materials": True,
                "reading_reminders": False,
                "progress_updates": True,
            }
        }, self.user.tags)


class AdminSettingsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="ADM-9999",
            role="admin",
            first_name="Admin",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="admin-settings@example.com",
            password_hash=make_password("admin-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_admin_settings_renders_new_settings_ui(self):
        response = self.client.get(reverse("admin_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pabasa_app/admin_settings.html")
        self.assertContains(response, "Push Notifications")
        self.assertContains(response, "Enable Notifications")
        self.assertContains(response, "Email Notifications")
        self.assertContains(response, "Save Preferences")
        self.assertContains(response, "Change Password")
        self.assertContains(response, "Current Password")
        self.assertContains(response, "New Password")
        self.assertContains(response, "Confirm Password")
        self.assertContains(response, "Update Password")
        self.assertNotContains(response, "Settings placeholder. CRUD is not implemented yet.")
