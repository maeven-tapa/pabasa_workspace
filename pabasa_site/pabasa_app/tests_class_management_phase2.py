from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .models import School, Section, User


class ClassManagementPhase2Tests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Phase 2 School", code="PH2")
        self.teacher_a = self._user("teacher-a", "teacher-a@example.com")
        self.teacher_b = self._user("teacher-b", "teacher-b@example.com")
        self.section_a = self._section("PH2-A", "Section A", self.teacher_a)
        self.section_b = self._section("PH2-B", "Section B", self.teacher_b)

    def _user(self, custom_id, email):
        return User.objects.create(
            custom_id=custom_id,
            role="teacher",
            first_name=custom_id,
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="N/A",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email=email,
            password_hash=make_password("password"),
            school_record=self.school,
        )

    def _section(self, code, name, teacher, is_active=True):
        return Section.objects.create(
            school=self.school,
            class_code=code,
            class_name=name,
            subject="Reading",
            teacher=teacher,
            is_active=is_active,
        )

    def _login(self, teacher):
        session = self.client.session
        session.update({"user_id": teacher.id, "user_role": "teacher", "email": teacher.email})
        session.save()

    def test_teacher_opens_own_section_by_section_id(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("class_management"), {"section_id": self.section_a.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.section_a.class_name)

    def test_teacher_cannot_open_another_teachers_section_by_section_id(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("class_management"), {"section_id": self.section_b.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Section Assigned")
        self.assertNotContains(response, self.section_b.class_name)

    def test_inactive_section_cannot_open(self):
        inactive = self._section("PH2-I", "Inactive Section", self.teacher_a, is_active=False)
        self._login(self.teacher_a)

        response = self.client.get(reverse("class_management"), {"section_id": inactive.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Section Assigned")

    def test_legacy_code_opens_own_section(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("class_management"), {"code": self.section_a.class_code})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.section_a.class_name)

    def test_legacy_code_cannot_open_another_teachers_section(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("class_management"), {"code": self.section_b.class_code})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Section Assigned")
        self.assertNotContains(response, self.section_b.class_name)

    def test_no_section_assigned_state_remains_safe(self):
        teacher_without_section = self._user("teacher-empty", "teacher-empty@example.com")
        self._login(teacher_without_section)

        response = self.client.get(reverse("class_management"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Section Assigned")

