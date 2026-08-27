from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .models import Enrollment, Material, School, Section, User


class ClassMaterialsAuthorizationTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="School A", code="CMA")
        self.school_b = School.objects.create(name="School B", code="CMB")
        self.teacher_a = self._user("teacher-a", "teacher", self.school_a)
        self.teacher_b = self._user("teacher-b", "teacher", self.school_b)
        self.student_a = self._user("student-a", "student")
        self.section_a = Section.objects.create(
            school=self.school_a,
            class_code="CMA-001",
            class_name="School A Section",
            subject="Reading",
            teacher=self.teacher_a,
            is_active=True,
        )
        self.section_b = Section.objects.create(
            school=self.school_b,
            class_code="CMB-001",
            class_name="School B Section",
            subject="Reading",
            teacher=self.teacher_b,
            is_active=True,
        )
        self.material = Material.objects.create(
            title="Section A Material",
            item_type="word",
            content_text="basa",
            type="assessment",
            status="published",
            section=self.section_a,
            teacher=self.teacher_a,
            is_active=True,
        )

    def _user(self, custom_id, role, school=None):
        return User.objects.create(
            custom_id=custom_id,
            role=role,
            first_name=custom_id,
            last_name="User",
            middle_initial="",
            suffix="",
            sex="N/A",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email=f"{custom_id}@example.com",
            password_hash=make_password("password"),
            school_record=school,
        )

    def _login(self, user):
        session = self.client.session
        session.update({"user_id": user.id, "user_role": user.role, "email": user.email})
        session.save()

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(
            reverse("get_class_materials"),
            {"section_id": self.section_a.id},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_student_can_fetch_own_section_by_id_and_metadata_remains(self):
        Enrollment.objects.create(student=self.student_a, section=self.section_a, is_active=True)
        self._login(self.student_a)

        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_a.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["class_code"], self.section_a.class_code)
        self.assertEqual(payload["class_name"], self.section_a.class_name)
        self.assertEqual(payload["subject"], self.section_a.subject)
        self.assertEqual(payload["materials"]["word"][0]["raw_id"], self.material.id)

    def test_student_cannot_fetch_other_school_section_by_id(self):
        Enrollment.objects.create(student=self.student_a, section=self.section_a, is_active=True)
        self._login(self.student_a)

        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_b.id})

        self.assertEqual(response.status_code, 403)

    def test_teacher_can_fetch_own_section_by_id(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_a.id})

        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_fetch_other_teacher_section_by_id(self):
        self._login(self.teacher_a)

        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_b.id})

        self.assertEqual(response.status_code, 403)

    def test_class_code_only_request_is_rejected(self):
        Enrollment.objects.create(student=self.student_a, section=self.section_a, is_active=True)
        self._login(self.student_a)

        own_response = self.client.get(reverse("get_class_materials"), {"class_code": self.section_a.class_code})
        foreign_response = self.client.get(reverse("get_class_materials"), {"class_code": self.section_b.class_code})

        self.assertEqual(own_response.status_code, 400)
        self.assertEqual(foreign_response.status_code, 400)
