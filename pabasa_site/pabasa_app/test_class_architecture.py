import json
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Assessment, Enrollment, Section, User


def make_user(custom_id, role, email):
    return User.objects.create(
        custom_id=custom_id,
        role=role,
        first_name=role.title(),
        last_name="Account",
        middle_initial="",
        suffix="",
        sex="female",
        birth_month=1,
        birth_day=1,
        birth_year=1990,
        email=email,
        password_hash="hashed-password",
    )


class CanonicalSectionArchitectureTests(TestCase):
    def setUp(self):
        self.teacher = make_user("TCH-CANONICAL", "teacher", "canonical-teacher@example.com")
        self.student = make_user("STU-CANONICAL", "student", "canonical-student@example.com")
        self.section = Section.objects.create(
            class_code="G2-A",
            class_name="Grade 2 - A",
            grade_level="Grade 2",
            section="A",
            teacher=self.teacher,
            subject="Reading",
        )

    def test_grade_and_section_identity_is_case_insensitively_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Section.objects.create(
                class_code="G2-A-DUP",
                class_name="Duplicate",
                grade_level="grade 2",
                section="a",
                teacher=self.teacher,
                subject="Reading",
            )

    def test_legacy_unclassified_sections_remain_supported(self):
        Section.objects.create(
            class_code="LEGACY-1", class_name="Legacy One", teacher=self.teacher, subject="Reading"
        )
        Section.objects.create(
            class_code="LEGACY-2", class_name="Legacy Two", teacher=self.teacher, subject="Reading"
        )

    def test_teacher_assignment_is_replaceable_and_optional(self):
        self.assertEqual(self.section.teacher, self.teacher)
        self.section.teacher = None
        self.section.save(update_fields=["teacher"])
        self.section.refresh_from_db()
        self.assertIsNone(self.section.teacher)

    def test_enrollment_is_unique_and_json_compatible(self):
        self.assertTrue(self.section.add_student(self.student))
        self.assertFalse(self.section.add_student(self.student))
        self.assertEqual(Enrollment.objects.filter(student=self.student, section=self.section).count(), 1)
        self.section.refresh_from_db()
        self.assertEqual(self.section.students[0]["student_id"], self.student.id)
        self.assertTrue(self.section.has_student(self.student))
        self.assertEqual(self.section.get_student_count(), 1)

        self.assertTrue(self.section.deactivate_student(self.student))
        self.assertFalse(Enrollment.objects.get(student=self.student, section=self.section).is_active)
        self.assertFalse(self.section.has_student(self.student))
        self.assertTrue(self.section.add_student(self.student))
        self.assertTrue(Enrollment.objects.get(student=self.student, section=self.section).is_active)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.student, section=self.section)

    def test_relational_enrollment_is_visible_to_legacy_readers(self):
        Enrollment.objects.create(student=self.student, section=self.section)
        self.assertTrue(self.section.has_student(self.student))
        self.assertEqual(self.section.get_enrolled_students(active_only=True)[0]["student_id"], self.student.id)

    def test_assessment_relationship_survives_teacher_reassignment(self):
        assessment = Assessment.objects.create(
            title="History",
            code="ASM-HISTORY",
            assessment_type="word",
            status="published",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
            attempt_no=1,
        )
        self.section.teacher = None
        self.section.save(update_fields=["teacher"])
        assessment.refresh_from_db()
        self.assertEqual(assessment.section, self.section)

    def test_create_endpoint_rejects_existing_canonical_section(self):
        session = self.client.session
        session.update({"user_id": self.teacher.id, "user_role": "teacher", "email": self.teacher.email})
        session.save()
        response = self.client.post(
            reverse("create_reading_class"),
            json.dumps({"grade": "grade 2", "section": "a"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Section.objects.filter(grade_level__iexact="grade 2", section__iexact="a").count(), 1)


class StudentSignupAutomaticEnrollmentTests(TestCase):
    """OTP signup resolves the configured canonical class, whether or not a teacher is assigned yet."""

    def setUp(self):
        self.teacher = make_user("TCH-AUTO", "teacher", "auto-teacher@example.com")
        self.student_number = 0

    def _create_teacher_class(self, grade_level="Grade 2", section_name="BONIFACIO"):
        return Section.objects.create(
            class_code=f"AUTO-{Section.objects.count() + 1}",
            class_name=f"{grade_level} - {section_name}",
            grade_level=grade_level,
            section=section_name,
            teacher=self.teacher,
            subject="Reading",
            is_active=True,
        )

    def _signup_and_verify(self, grade_level="Grade 2", section_name="BONIFACIO"):
        self.student_number += 1
        suffix = self.student_number
        payload = {
            "first_name": "Student",
            "last_name": f"{suffix}",
            "email": f"student-{suffix}@example.com",
            "password": "Student123",
            "confirm_password": "Student123",
            "lrn": f"1234567890{suffix:02d}",
            "grade_level": grade_level,
            "section": section_name,
            "sex": "female",
            "birth_month": "1",
            "birth_day": "5",
            "birth_year": "2014",
        }
        with patch("pabasa_app.views.send_student_signup_otp_email"), patch(
            "pabasa_app.views.send_student_confirmation_email"
        ), patch("pabasa_app.views._notify_admins"):
            response = self.client.post(reverse("register_student"), payload)
            self.assertEqual(response.status_code, 200)
            otp = self.client.session["pending_student_signup_otp"]
            response = self.client.post(reverse("verify_student_otp"), {"otp": otp})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        return User.objects.get(email=payload["email"])

    def test_matching_grade_and_section_enrolls_student_after_otp(self):
        teacher_class = self._create_teacher_class()

        student = self._signup_and_verify()

        self.assertTrue(teacher_class.has_student(student))
        self.assertEqual(Enrollment.objects.filter(student=student, section=teacher_class).count(), 1)

    def test_unconfigured_section_is_rejected_before_otp(self):
        self._create_teacher_class()
        payload = {
            "first_name": "Student", "last_name": "Rejected", "email": "rejected@example.com",
            "password": "Student123", "confirm_password": "Student123", "lrn": "123456789099",
            "grade_level": "Grade 2", "section": "RIZAL", "sex": "female",
            "birth_month": "1", "birth_day": "5", "birth_year": "2014",
        }
        response = self.client.post(reverse("register_student"), payload)
        self.assertEqual(response.status_code, 400)

    def test_same_section_name_on_a_different_grade_is_a_different_class(self):
        grade_two = self._create_teacher_class()
        grade_three = self._create_teacher_class("Grade 3", "BONIFACIO")
        student = self._signup_and_verify(grade_level="Grade 3")
        self.assertTrue(grade_three.has_student(student))
        self.assertFalse(grade_two.has_student(student))

    def test_section_without_teacher_still_enrolls_student(self):
        section = self._create_teacher_class()
        section.teacher = None
        section.save(update_fields=["teacher"])
        student = self._signup_and_verify()
        self.assertTrue(section.has_student(student))

    def test_existing_membership_is_not_duplicated(self):
        teacher_class = self._create_teacher_class()
        student = self._signup_and_verify()

        self.assertFalse(teacher_class.add_student(student))
        self.assertEqual(Enrollment.objects.filter(student=student, section=teacher_class).count(), 1)


class TeacherSignupCanonicalAssignmentTests(TestCase):
    def test_teacher_otp_assigns_the_existing_canonical_section(self):
        section = Section.objects.create(
            class_code="G2-BONI", class_name="Grade 2 - BONIFACIO",
            grade_level="Grade 2", section="BONIFACIO", subject="Reading",
        )
        payload = {
            "first_name": "Teacher", "last_name": "Bonifacio", "email": "teacher-signup@example.com",
            "password": "Teacher123", "confirm_password": "Teacher123", "sex": "female",
            "birth_month": "1", "birth_day": "1", "birth_year": "1990",
            "grade_level": "Grade 2", "section": "BONIFACIO",
        }
        with patch("pabasa_app.views.send_teacher_signup_otp_email"), patch(
            "pabasa_app.views.send_teacher_confirmation_email"
        ), patch("pabasa_app.views._notify_admins"), patch("pabasa_app.views._notify_principals"):
            self.assertEqual(self.client.post(reverse("register_teacher"), payload).status_code, 200)
            response = self.client.post(reverse("verify_teacher_otp"), {"otp": self.client.session["pending_teacher_signup_otp"]})
        self.assertTrue(response.json()["success"])
        section.refresh_from_db()
        self.assertEqual(section.teacher.email, payload["email"])

    def test_assigned_section_rejects_a_second_teacher_before_otp(self):
        teacher = make_user("TCH-EXISTING", "teacher", "existing@example.com")
        Section.objects.create(class_code="G2-RIZAL", class_name="Grade 2 - RIZAL", grade_level="Grade 2", section="RIZAL", teacher=teacher, subject="Reading")
        payload = {"first_name": "Teacher", "last_name": "Second", "email": "second@example.com", "password": "Teacher123", "confirm_password": "Teacher123", "sex": "female", "birth_month": "1", "birth_day": "1", "birth_year": "1990", "grade_level": "Grade 2", "section": "RIZAL"}
        response = self.client.post(reverse("register_teacher"), payload)
        self.assertEqual(response.status_code, 409)
