import json
from django.test import TestCase
from django.urls import reverse
from .models import Course, Enrollment, School, Section, User


class CourseSchoolScopingTests(TestCase):
    def make_user(self, custom_id, email, school, role="teacher"):
        return User.objects.create(custom_id=custom_id, role=role, first_name=custom_id,
            last_name="User", middle_initial="", suffix="", sex="female",
            birth_month=1, birth_day=1, birth_year=1990, email=email,
            password_hash="hashed", school_record=school if role == "teacher" else None)

    def setUp(self):
        self.school_a = School.objects.create(name="School A", code="S-A")
        self.school_b = School.objects.create(name="School B", code="S-B")
        self.teacher_a = self.make_user("TA-001", "ta@example.com", self.school_a)
        self.teacher_b = self.make_user("TB-001", "tb@example.com", self.school_b)
        self.section_a = Section.objects.create(school=self.school_a, class_code="A-001", class_name="A", teacher=self.teacher_a, subject="Reading")
        self.section_b = Section.objects.create(school=self.school_b, class_code="B-001", class_name="B", teacher=self.teacher_b, subject="Reading")
        self.course_a = Course.objects.create(code="CA-001", title="Course A", teacher=self.teacher_a, school=self.school_a)
        self.course_a.sections.add(self.section_a)
        self.course_b = Course.objects.create(code="CB-001", title="Course B", teacher=self.teacher_b, school=self.school_b)
        self.course_b.sections.add(self.section_b)

    def login(self, user):
        session = self.client.session
        session.update({"user_id": user.id, "user_role": user.role, "email": user.email, "custom_id": user.custom_id})
        session.save()

    def test_teacher_shared_listing_is_school_scoped(self):
        self.login(self.teacher_a)
        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["courses"]}
        self.assertIn(self.course_a.id, ids)
        self.assertNotIn(self.course_b.id, ids)

    def test_teacher_cannot_mutate_other_school_course_by_id(self):
        self.login(self.teacher_a)
        response = self.client.post(reverse("delete_course"), json.dumps({"course_id": self.course_b.id, "confirmation": "DELETE"}), content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.course_b.refresh_from_db()
        self.assertTrue(self.course_b.is_active)

    def test_new_course_gets_school_server_side_and_rejects_foreign_section(self):
        self.login(self.teacher_a)
        response = self.client.post(reverse("create_course"), json.dumps({"title": "New", "sections": [self.section_b.id]}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        course = Course.objects.get(id=response.json()["course"]["id"])
        self.assertEqual(course.school_id, self.school_a.id)
        self.assertFalse(course.sections.exists())

    def test_null_school_course_is_not_shared(self):
        legacy = Course.objects.create(code="LEGACY-001", title="Legacy", teacher=self.teacher_a)
        self.login(self.teacher_a)
        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})
        self.assertNotIn(legacy.id, {item["id"] for item in response.json()["courses"]})

    def test_student_enrollment_remains_section_boundary(self):
        student = self.make_user("ST-001", "student@example.com", None, role="student")
        self.section_a.add_student(student)
        self.assertTrue(Enrollment.objects.filter(student=student, section=self.section_a, is_active=True).exists())
        self.assertFalse(self.section_b.has_student(student))
