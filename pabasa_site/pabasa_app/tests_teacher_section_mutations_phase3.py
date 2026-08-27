import json

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .models import Enrollment, School, Section, User


class TeacherSectionMutationsPhase3Tests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Phase 3 School", code="PH3")
        self.teacher_a = self._user("teacher-a", "teacher-a@phase3.example", "teacher")
        self.teacher_b = self._user("teacher-b", "teacher-b@phase3.example", "teacher")
        self.student = self._user("student-a", "student-a@phase3.example", "student")
        self.section_a = self._section("PH3-A", "Section A", self.teacher_a)
        self.section_b = self._section("PH3-B", "Section B", self.teacher_b)

    def _user(self, custom_id, email, role):
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

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_teacher_can_update_own_section_by_section_id(self):
        self._login(self.teacher_a)

        response = self._post("update_class_info", {
            "section_id": self.section_a.id,
            "class_code": self.section_a.class_code,
            "class_name": "Updated Section A",
            "description": "Updated description",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.section_a.refresh_from_db()
        self.assertEqual(self.section_a.class_name, "Updated Section A")

    def test_teacher_cannot_update_another_teachers_section(self):
        self._login(self.teacher_a)

        response = self._post("update_class_info", {
            "section_id": self.section_b.id,
            "class_name": "Should Not Change",
            "description": "Should Not Change",
        })

        self.assertEqual(response.status_code, 404)
        self.section_b.refresh_from_db()
        self.assertEqual(self.section_b.class_name, "Section B")

    def test_teacher_can_add_student_to_own_section(self):
        self._login(self.teacher_a)

        response = self._post("teacher_add_student", {
            "section_id": self.section_a.id,
            "student_id": self.student.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(Enrollment.objects.filter(student=self.student, section=self.section_a, is_active=True).exists())

    def test_teacher_cannot_add_student_to_another_teachers_section(self):
        self._login(self.teacher_a)

        response = self._post("teacher_add_student", {
            "section_id": self.section_b.id,
            "student_id": self.student.id,
        })

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Enrollment.objects.filter(student=self.student, section=self.section_b).exists())

    def test_teacher_can_remove_student_from_own_section(self):
        self.section_a.add_student(self.student)
        self._login(self.teacher_a)

        response = self._post("teacher_remove_student", {
            "section_id": self.section_a.id,
            "student_id": self.student.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(Enrollment.objects.filter(student=self.student, section=self.section_a, is_active=True).exists())

    def test_teacher_cannot_remove_student_from_another_teachers_section(self):
        self.section_b.add_student(self.student)
        self._login(self.teacher_a)

        response = self._post("teacher_remove_student", {
            "section_id": self.section_b.id,
            "student_id": self.student.id,
        })

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Enrollment.objects.filter(student=self.student, section=self.section_b, is_active=True).exists())

    def test_inactive_section_mutation_is_rejected(self):
        inactive = self._section("PH3-I", "Inactive Section", self.teacher_a, is_active=False)
        self._login(self.teacher_a)

        response = self._post("update_class_info", {
            "section_id": inactive.id,
            "class_name": "Should Not Change",
        })

        self.assertEqual(response.status_code, 404)
        inactive.refresh_from_db()
        self.assertEqual(inactive.class_name, "Inactive Section")

    def test_class_code_only_mutations_are_rejected(self):
        self._login(self.teacher_a)

        own_response = self._post("update_class_info", {
            "class_code": self.section_a.class_code,
            "class_name": "Updated Through Compatibility",
        })
        other_response = self._post("teacher_add_student", {
            "class_code": self.section_b.class_code,
            "student_id": self.student.id,
        })

        self.assertEqual(own_response.status_code, 404)
        self.assertFalse(own_response.json()["success"])
        self.assertEqual(other_response.status_code, 404)
        self.assertFalse(Enrollment.objects.filter(student=self.student, section=self.section_b).exists())
