from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .models import Enrollment, Material, School, Section, User


class Phase6SectionIdentityRegressionTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Regression School A", code="RGA")
        self.school_b = School.objects.create(name="Regression School B", code="RGB")
        self.teacher_a = self._user("reg-teacher-a", "teacher", self.school_a)
        self.teacher_b = self._user("reg-teacher-b", "teacher", self.school_b)
        self.student_a = self._user("reg-student-a", "student", self.school_a)
        self.student_b = self._user("reg-student-b", "student", self.school_b)
        self.section_a = Section.objects.create(
            school=self.school_a, class_code="RGA-001", class_name="Regression A",
            subject="Reading", teacher=self.teacher_a, is_active=True,
        )
        self.section_b = Section.objects.create(
            school=self.school_b, class_code="RGB-001", class_name="Regression B",
            subject="Reading", teacher=self.teacher_b, is_active=True,
        )
        self.inactive_section = Section.objects.create(
            school=self.school_a, class_code="RGA-002", class_name="Inactive A",
            subject="Reading", teacher=self.teacher_a, is_active=False,
        )
        Enrollment.objects.create(student=self.student_a, section=self.section_a, is_active=True)
        self.material = Material.objects.create(
            title="Regression Material", item_type="word", content_text="basa",
            type="assessment", status="published", section=self.section_a,
            teacher=self.teacher_a, is_active=True,
        )

    def _user(self, custom_id, role, school):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name=custom_id,
            last_name="User", middle_initial="", suffix="", sex="N/A",
            birth_month=1, birth_day=1, birth_year=2010,
            email=f"{custom_id}@example.com", password_hash=make_password("password"),
            school_record=school,
        )

    def _login(self, user):
        session = self.client.session
        session.update({"user_id": user.id, "user_role": user.role, "email": user.email})
        session.save()

    def test_student_joined_classes_returns_section_id(self):
        self._login(self.student_a)
        response = self.client.get(reverse("get_student_joined_classes"))
        self.assertEqual(response.status_code, 200)
        classes = response.json()["classes"]
        self.assertEqual([item["section_id"] for item in classes], [self.section_a.id])
        self.assertEqual(classes[0]["id"], self.section_a.id)

    def test_student_material_access_is_enrollment_bound(self):
        self._login(self.student_a)
        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_a.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["materials"]["word"][0]["raw_id"], self.material.id)

        foreign_response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_b.id})
        self.assertEqual(foreign_response.status_code, 403)

    def test_teacher_classes_returns_only_active_owned_sections_with_section_id(self):
        self._login(self.teacher_a)
        response = self.client.get(reverse("get_teacher_classes"))
        self.assertEqual(response.status_code, 200)
        classes = response.json()["classes"]
        self.assertEqual([item["section_id"] for item in classes], [self.section_a.id])
        self.assertNotIn(self.section_b.id, [item["section_id"] for item in classes])
        self.assertNotIn(self.inactive_section.id, [item["section_id"] for item in classes])

    def test_teacher_can_open_only_owned_active_section_by_id(self):
        self._login(self.teacher_a)
        own = self.client.get(reverse("class_management"), {"section_id": self.section_a.id})
        self.assertEqual(own.status_code, 200)
        self.assertNotContains(own, "No Section Assigned")

        foreign = self.client.get(reverse("class_management"), {"section_id": self.section_b.id})
        self.assertContains(foreign, "No Section Assigned")

        inactive = self.client.get(reverse("class_management"), {"section_id": self.inactive_section.id})
        self.assertContains(inactive, "No Section Assigned")
