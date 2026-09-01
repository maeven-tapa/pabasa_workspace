from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Enrollment, School, SchoolCalendar, Section, User


class RemainingEnrollmentLifecycleIntegrationTests(TestCase):
    def setUp(self):
        SchoolCalendar.objects.update(is_active=False)
        self.school = School.objects.create(name="Lifecycle School", code="LIFE")
        self.year_one = SchoolCalendar.objects.create(school_year="2026-2027", current_term=3, is_active=False)
        self.year_two = SchoolCalendar.objects.create(school_year="2027-2028", current_term=1, is_active=True)
        self.teacher_old = self.user("TCH-OLD", "old-teacher@example.com", "teacher")
        self.teacher_new = self.user("TCH-NEW", "new-teacher@example.com", "teacher")
        self.student = self.user("STU-LIFE", "student@example.com", "student")
        self.old_section = self.section("RIZAL", self.year_one, self.teacher_old)
        self.new_section = self.section("AGUINALDO", self.year_two, None)
        self.old_enrollment = Enrollment.objects.create(
            student=self.student, section=self.old_section, school=self.school,
            school_calendar=self.year_one, grade_level="Grade 2", status="active",
        )

    def user(self, custom_id, email, role):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name=custom_id,
            last_name="User", middle_initial="", suffix="", sex="N/A",
            birth_month=1, birth_day=1, birth_year=2014,
            email=email, password_hash=make_password("password"),
            school_record=self.school,
        )

    def section(self, name, calendar, teacher):
        return Section.objects.create(
            school=self.school, school_calendar=calendar,
            class_code=f"G2-{name}", class_name=f"Grade 2 - {name}",
            grade_level="Grade 2", section=name, subject="Reading",
            teacher=teacher, is_active=True,
        )

    def login_admin(self):
        admin = self.user("ADM-LIFE", "admin@example.com", "admin")
        session = self.client.session
        session.update({"user_id": admin.id, "user_role": "admin", "email": admin.email})
        session.save()

    def test_retained_return_isolated_and_assignable(self):
        self.old_enrollment.finalize_outcome("retained", finalized_by=self.teacher_old)
        self.login_admin()
        response = self.client.post(reverse("admin_student_returning_enrollment", args=[self.student.id]))
        self.assertEqual(response.status_code, 302)
        returning = Enrollment.objects.get(student=self.student, school_calendar=self.year_two)
        self.assertEqual(returning.status, "awaiting_assignment")
        self.assertFalse(returning.is_active)
        self.assertIsNone(returning.section_id)
        self.assertEqual(Enrollment.objects.filter(student=self.student, school_calendar=self.year_two, status__in=("active", "awaiting_assignment")).count(), 1)

        self.new_section.assign_teacher(self.teacher_new)
        response = self.client.post(reverse("admin_student_move_enrollment", args=[self.student.id]), {"section_id": self.new_section.id})
        self.assertEqual(response.status_code, 302)
        returning.refresh_from_db()
        self.assertEqual(returning.section_id, self.new_section.id)
        self.assertEqual(returning.status, "active")
        self.assertTrue(returning.is_active)
        self.old_enrollment.refresh_from_db()
        self.assertEqual((self.old_enrollment.status, self.old_enrollment.outcome), ("completed", "retained"))

        self.assertEqual(returning.assigned_teacher_id, self.teacher_new.id)
        self.assertEqual(returning.status, "active")
        self.assertTrue(returning.is_active)
        self.assertEqual(Enrollment.objects.filter(student=self.student, school_calendar=self.year_two).count(), 1)

    def test_promoted_archive_and_pre_archive_recovery(self):
        self.old_enrollment.finalize_outcome("promoted", finalized_by=self.teacher_old)
        self.assertEqual((self.old_enrollment.status, self.old_enrollment.outcome), ("completed", "promoted"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.account_status, "pending_archive")
        self.assertFalse(self.student.is_archived)

        self.login_admin()
        self.client.post(reverse("admin_student_archive_action", args=[self.student.id]), {"action": "revert_retained"})
        self.student.refresh_from_db()
        self.old_enrollment.refresh_from_db()
        self.assertEqual(self.student.account_status, "active")
        self.assertFalse(self.student.is_archived)
        self.assertEqual((self.old_enrollment.status, self.old_enrollment.outcome), ("completed", "retained"))

    def test_post_archive_restore_then_return_keeps_history(self):
        self.old_enrollment.finalize_outcome("promoted", finalized_by=self.teacher_old)
        self.login_admin()
        self.client.post(reverse("admin_student_archive_action", args=[self.student.id]), {"action": "approve_archive"})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_archived)
        self.client.post(reverse("admin_student_restore", args=[self.student.id]))
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_archived)
        self.client.post(reverse("admin_student_archive_action", args=[self.student.id]), {"action": "correct_retained"})
        self.client.post(reverse("admin_student_returning_enrollment", args=[self.student.id]))
        returning = Enrollment.objects.get(student=self.student, school_calendar=self.year_two)
        self.assertEqual(returning.status, "awaiting_assignment")
        self.assertEqual(Enrollment.objects.filter(student=self.student, school_calendar=self.year_two).count(), 1)
        self.old_enrollment.refresh_from_db()
        self.assertEqual((self.old_enrollment.status, self.old_enrollment.outcome), ("completed", "retained"))

    def test_teacher_cannot_own_two_sections_in_same_year_but_can_in_history(self):
        historical = self.section("BONIFACIO-2026", self.year_one, self.teacher_new)
        self.assertEqual(historical.teacher_id, self.teacher_new.id)
        self.new_section.assign_teacher(self.teacher_new)
        other = self.section("BONIFACIO", self.year_two, None)
        with self.assertRaises(ValidationError):
            other.assign_teacher(self.teacher_new)
