import json
import uuid

from django.test import TestCase
from django.urls import reverse

from .models import Assessment, Course, Enrollment, Material, School, Section, User


def test_section_create(**kwargs):
    school = kwargs.pop("school", None)
    if school is None:
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f"Fixture School {suffix}", code=f"FIXTURE-{suffix}")
    return Section.objects.create(school=school, **kwargs)


class SectionBackedCoursesRegressionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Section Course School", code="SCS-001")
        self.teacher = User.objects.create(
            custom_id="TCH-SECTION-COURSES", role="teacher",
            first_name="Section", last_name="Owner", middle_initial="", suffix="",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="section-courses@example.com", password_hash="hashed-password",
            teacher_role="Teacher",
            school_record=self.school,
        )
        self.section = test_section_create(
            class_code="SEC-COURSES", class_name="Grade 2", header="Reading Class",
            description="", teacher=self.teacher, subject="English", is_active=True,
        )
        session = self.client.session
        session.update({
            "user_id": self.teacher.id, "user_role": "teacher",
            "email": self.teacher.email, "custom_id": self.teacher.custom_id,
        })
        session.save()

    def test_personal_courses_returns_owned_section_without_course_row(self):
        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Course.objects.filter(teacher=self.teacher).count(), 0)
        self.assertEqual(response.json()["courses"][0]["id"], f"section-{self.section.id}")
        self.assertEqual(response.json()["courses"][0]["title"], "Grade 2")

    def test_courses_context_is_section_backed(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["teacher_courses"][0]["id"], f"section-{self.section.id}")

    def test_shared_mode_remains_legacy_course_backed(self):
        other_teacher = User.objects.create(
            custom_id="TCH-SHARED-COURSES", role="teacher",
            first_name="Shared", last_name="Owner", middle_initial="", suffix="",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="shared-courses@example.com", password_hash="hashed-password",
            teacher_role="Teacher",
            school_record=self.school,
        )
        shared_course = Course.objects.create(
            code="SHARED-COURSE", title="Shared Course", teacher=other_teacher,
        )
        self.assertIsNone(shared_course.school_id)
        self.assertEqual(shared_course.teacher.school_record_id, self.school.id)
        self.assertFalse(shared_course.sections.exists())

        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})

        self.assertEqual(response.status_code, 200)
        ids = {course["id"] for course in response.json()["courses"]}
        # NULL-school legacy Courses remain owner-compatible but are excluded
        # from school-wide/shared discovery.
        self.assertNotIn(shared_course.id, ids)
        self.assertNotIn(f"section-{self.section.id}", ids)

    def test_section_identifier_scopes_assessments(self):
        assessment = Assessment.objects.create(
            title="Section Assessment", code="ASM-SECTION", assessment_type="word",
            status="published", teacher=self.teacher, section=self.section,
            is_active=True, attempt_no=1,
        )

        response = self.client.get(
            reverse("get_teacher_assessments_api"),
            {"course_id": f"section-{self.section.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(assessment.id, {item["id"] for item in response.json()["assessments"]})

    def test_section_identifier_adds_and_removes_material_without_course(self):
        material = Material.objects.create(
            teacher=self.teacher, title="Section Material", item_type="word",
            content_text="read", content_json={"items": ["read"]},
            type="practice", source_type="personal", status="published", is_active=True,
        )
        identifier = f"section-{self.section.id}"

        added = self.client.post(
            reverse("add_material_to_course"),
            json.dumps({"course_id": identifier, "material_id": material.id}),
            content_type="application/json",
        )
        self.assertEqual(added.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.section_id, self.section.id)
        self.assertTrue(material.assigned_sections.filter(id=self.section.id).exists())

        removed = self.client.post(
            reverse("remove_material_from_course"),
            json.dumps({"course_id": identifier, "material_id": material.id}),
            content_type="application/json",
        )
        self.assertEqual(removed.status_code, 200)
        material.refresh_from_db()
        self.assertIsNone(material.section_id)
        self.assertFalse(material.assigned_sections.filter(id=self.section.id).exists())

    def test_section_backed_course_can_start_live_assessment(self):
        student = self._user("SCS-STUDENT", "scs-student@example.com", "student", self.school)
        Enrollment.objects.create(student=student, section=self.section, assigned_teacher=self.teacher)
        material = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Live Section Material",
            item_type="word", content_text="read", content_json={"items": ["read"]},
            type="assessment", source_type="personal", status="published", is_active=True,
        )
        response = self.client.post(
            reverse("start_live_assessment"),
            json.dumps({
                "course_id": None,
                "section_id": self.section.id,
                "material_id": material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["session"]["available_students"][0]["id"], student.id)
