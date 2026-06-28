from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.hashers import check_password, make_password
import json

from .models import Material, User, Section, Assessment, Notification


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


class PrincipalSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="PRN-SES",
            role="principal",
            first_name="Jobelyn",
            last_name="Valdez",
            middle_initial="A",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=3,
            birth_year=1980,
            email="principal@example.com",
            password_hash=make_password("old-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_principal_settings_saves_school_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_school_info",
                "school_name": "Example Elementary School",
                "school_code": "EX-001",
                "municipality": "Imus",
                "province": "Cavite",
                "district": "District 5",
                "region": "CALABARZON",
                "address": "Example Street",
                "contact": "0917-123-4567",
                "email": "principal@example.org",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.preference["principal_school_info"]["name"], "Example Elementary School")
        self.assertEqual(self.user.preference["principal_school_info"]["code"], "EX-001")

    def test_principal_settings_changes_password(self):
        response = self.client.post(
            reverse("principal_settings"),
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

    def test_principal_settings_updates_personal_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_personal_info",
                "first_name": "Maria",
                "last_name": "Cruz",
                "middle_initial": "L",
                "email": "maria.cruz@example.org",
                "contact_number": "09171234567",
                "position": "Principal II",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personal information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Maria")
        self.assertEqual(self.user.last_name, "Cruz")
        self.assertEqual(self.user.middle_initial, "L")
        self.assertEqual(self.user.email, "maria.cruz@example.org")
        self.assertEqual(self.user.contact_no, "09171234567")
        self.assertEqual(self.user.preference["principal_profile_info"]["position"], "Principal II")


class AssessmentCompletionNotificationTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-9001",
            role="teacher",
            first_name="Taylor",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher9001@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STU-9001",
            role="student",
            first_name="Jane",
            last_name="Doe",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2012,
            email="student9001@example.com",
            password_hash=make_password("student-password"),
        )
        self.admin = User.objects.create(
            custom_id="ADM-9001",
            role="admin",
            first_name="Alex",
            last_name="Admin",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=1985,
            email="admin9001@example.com",
            password_hash=make_password("admin-password"),
        )
        self.section = Section.objects.create(
            teacher=self.teacher,
            class_name="Class A",
            class_code="CLS-A9001",
            subject="Reading",
            is_active=True,
        )
        self.section.add_student(self.student)
        self.assessment = Assessment.objects.create(
            title="Reading Fluency Test",
            code="ASM-9001",
            assessment_type="word",
            content="cat\ndog",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
        )

    def _login_student(self):
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session.save()

    def _login_teacher(self):
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session.save()

    def test_assessment_completion_creates_teacher_notification(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "assessment_id": f"assessment-{self.assessment.id}",
                "material_id": f"assessment-{self.assessment.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Jane Doe completed the assessment 'Reading Fluency Test' in Class A.", notification.message)
        self.assertFalse(notification.is_read)

    def test_duplicate_assessment_completion_does_not_create_second_notification(self):
        self._login_student()
        payload = json.dumps({
            "assessment_id": f"assessment-{self.assessment.id}",
            "material_id": f"assessment-{self.assessment.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })
        first = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        second = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.teacher,
                created_by=self.student,
                notification_type="assessment",
            ).count(),
            1,
        )

    def test_teacher_can_fetch_unread_notification(self):
        Notification.objects.create(
            recipient=self.teacher,
            created_by=self.student,
            title="📝 Student Completed an Assessment",
            message="Jane Doe completed the assessment 'Reading Fluency Test' in Class A.",
            notification_type="assessment",
            action_url=f"/dashboard/teacher/students/detail/?student_id={self.student.custom_id}",
        )
        self._login_teacher()
        response = self.client.get(reverse("get_notifications"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["notifications"]), 1)
        self.assertFalse(data["notifications"][0]["is_read"])

    def test_practice_completion_notifies_admin_in_app_only(self):
        material = Material.objects.create(
            title="Practice Words",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            status="published",
            is_active=True,
        )
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "practice",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        teacher_notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNone(teacher_notification)

        admin_notification = Notification.objects.filter(
            recipient=self.admin,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(admin_notification)
        self.assertIn("Jane Doe read \"Practice Words\"", admin_notification.message)
        self.assertFalse(admin_notification.is_read)


class TeacherStudentsDirectoryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-DIR1",
            role="teacher",
            first_name="Directory",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="directory-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STD-DIR1",
            role="student",
            first_name="Single",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="single-student@example.com",
            password_hash=make_password("student-password"),
        )
        self.section_a = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading One",
            class_code="READ-ONE",
            subject="Reading",
            is_active=True,
        )
        self.section_b = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading Two",
            class_code="READ-TWO",
            subject="Reading",
            is_active=True,
        )
        self.section_a.add_student(self.student)
        self.section_b.add_student(self.student)

        entries = self.section_b.get_enrolled_students()
        entries[0]["student_id"] = str(entries[0]["student_id"])
        self.section_b.students = entries
        self.section_b.save(update_fields=["students", "updated_at"])

        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_teacher_students_api_returns_one_row_with_joined_classes(self):
        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["custom_id"], self.student.custom_id)
        self.assertCountEqual(data["students"][0]["classes"], ["Reading One", "Reading Two"])
        self.assertCountEqual(data["students"][0]["class_codes"], ["READ-ONE", "READ-TWO"])

    def test_students_template_uses_static_renderer_only(self):
        response = self.client.get(reverse("students"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pabasa_app/js/students.js", html=False)
        self.assertNotContains(response, "Students directory: prefer server")

    def test_course_report_recipients_do_not_use_local_storage_students(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        helper_start = content.index("async function fetchStudentsForCourse(course)")
        helper_end = content.index("// Course-scoped Reports loader", helper_start)
        helper_body = content[helper_start:helper_end]

        self.assertIn("/dashboard/teacher/students-api/", helper_body)
        self.assertNotIn("pabasa_added_students", helper_body)
