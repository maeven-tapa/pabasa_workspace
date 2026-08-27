import uuid

from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse

from .models import Assessment, School, Section, User


def _user(role, label, school=None, grade_level=""):
    token = uuid.uuid4().hex[:10].upper()
    return User.objects.create(
        custom_id=f"{role[:3].upper()}-{token}",
        role=role,
        first_name=label,
        last_name=role.title(),
        middle_initial="",
        suffix="",
        sex="female",
        birth_month=1,
        birth_day=1,
        birth_year=1990,
        email=f"{role}-{token.lower()}@example.com",
        password_hash=make_password("test-password"),
        school_record=school,
        grade_level=grade_level,
    )


class PrincipalSchoolIsolationTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Isolation School A", code="ISO-A")
        self.school_b = School.objects.create(name="Isolation School B", code="ISO-B")
        self.principal_a = _user("principal", "Alice", self.school_a)
        self.principal_b = _user("principal", "Bea", self.school_b)
        self.teacher_a = _user("teacher", "Teacher A", self.school_a)
        self.teacher_b = _user("teacher", "Teacher B", self.school_b)
        self.student_a = _user("student", "Student A", self.school_a, "Grade 2")
        self.student_b = _user("student", "Student B", self.school_b, "Grade 5")

        self.section_a = Section.objects.create(
            school=self.school_a,
            class_code="ISO-A-G2",
            class_name="Grade 2 A",
            grade_level="Grade 2",
            section="A",
            subject="Reading",
            teacher=self.teacher_a,
        )
        self.section_b = Section.objects.create(
            school=self.school_b,
            class_code="ISO-B-G5",
            class_name="Grade 5 B",
            grade_level="Grade 5",
            section="B",
            subject="Reading",
            teacher=self.teacher_b,
        )
        self.section_a.add_student(self.student_a)
        self.section_b.add_student(self.student_b)

        self.assessment_a = Assessment.objects.create(
            title="School A Assessment",
            code="ISO-ASM-A",
            assessment_type="word",
            teacher=self.teacher_a,
            section=self.section_a,
        )
        self.assessment_b = Assessment.objects.create(
            title="School B Assessment",
            code="ISO-ASM-B",
            assessment_type="word",
            teacher=self.teacher_b,
            section=self.section_b,
        )
        self.assessment_a.record_attempt(self.student_a, status="completed", total_score=91)
        self.assessment_b.record_attempt(self.student_b, status="completed", total_score=72)

    def _client_for(self, user):
        client = Client()
        session = client.session
        session.update({
            "user_id": user.id,
            "user_role": user.role,
            "custom_id": user.custom_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        })
        session.save()
        return client

    def test_each_principal_dashboard_is_scoped_to_own_school(self):
        response_a = self._client_for(self.principal_a).get(reverse("dashboard_principal"))
        response_b = self._client_for(self.principal_b).get(reverse("dashboard_principal"))

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_a.context["school_name"], self.school_a.name)
        self.assertEqual(response_b.context["school_name"], self.school_b.name)
        self.assertEqual(response_a.context["total_students"], 1)
        self.assertEqual(response_a.context["total_teachers"], 1)
        self.assertEqual(response_a.context["total_sections"], 1)
        self.assertEqual(response_b.context["total_students"], 1)
        self.assertEqual(response_b.context["total_teachers"], 1)
        self.assertEqual(response_b.context["total_sections"], 1)
        self.assertEqual([row["title"] for row in response_a.context["assessment_rows"]], ["School A Assessment"])
        self.assertEqual([row["title"] for row in response_b.context["assessment_rows"]], ["School B Assessment"])

    def test_reports_and_assessments_do_not_accept_cross_school_query_data(self):
        client = self._client_for(self.principal_a)
        assessments = client.get(reverse("principal_assessments"))
        report = client.get(
            reverse("principal_reports"),
            {"report_type": "grade", "grade_level": "Grade 5"},
        )

        self.assertEqual(assessments.status_code, 200)
        self.assertContains(assessments, "School A Assessment")
        self.assertNotContains(assessments, "School B Assessment")
        self.assertEqual(report.context["report_preview_rows"], [])

    def test_cross_school_attempt_attached_to_owned_assessment_is_ignored(self):
        self.assessment_a.record_attempt(
            self.student_b,
            status="completed",
            total_score=99,
        )

        response = self._client_for(self.principal_a).get(reverse("principal_assessments"))
        assessment_row = response.context["assessment_rows"][0]

        self.assertEqual(assessment_row["participants"], 1)
        self.assertEqual(assessment_row["completed_students"], 1)
        self.assertNotIn(
            self.student_b.id,
            [row["student_id"] for row in response.context["assessment_attempt_rows"]],
        )

    def test_principal_cannot_open_admin_school_url_for_another_school(self):
        response = self._client_for(self.principal_a).get(
            reverse("admin_school_detail", args=[self.school_b.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("auth"))

    def test_principal_without_school_record_gets_empty_analytics(self):
        principal = _user("principal", "Unassigned")
        response = self._client_for(principal).get(reverse("dashboard_principal"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["school_name"], "School not assigned")
        self.assertEqual(response.context["total_students"], 0)
        self.assertEqual(response.context["total_teachers"], 0)
        self.assertEqual(response.context["total_sections"], 0)
        self.assertEqual(response.context["total_assessments"], 0)
        self.assertEqual(response.context["assessment_rows"], [])

    def test_admin_principal_dashboard_remains_global(self):
        admin = _user("admin", "Global")
        response = self._client_for(admin).get(reverse("dashboard_principal"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_students"], 2)
        self.assertEqual(response.context["total_teachers"], 2)
        self.assertEqual(response.context["total_sections"], 2)
        self.assertEqual(response.context["total_assessments"], 2)

    def test_persisted_role_blocks_forged_principal_session(self):
        forged_client = self._client_for(self.student_a)
        session = forged_client.session
        session["user_role"] = "principal"
        session.save()

        response = forged_client.get(reverse("dashboard_principal"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("auth"))
