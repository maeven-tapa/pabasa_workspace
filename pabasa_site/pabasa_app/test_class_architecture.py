import json
import socket
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Assessment, Enrollment, School, Section, User


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
        self.school = School.objects.create(name="Canonical School", code="CANONICAL-SCHOOL")
        self.section = Section.objects.create(
            class_code="G2-A",
            class_name="Grade 2 - A",
            grade_level="Grade 2",
            section="A",
            school=self.school,
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
                school=self.school,
                teacher=self.teacher,
                subject="Reading",
            )

    def test_section_creation_requires_an_explicit_school(self):
        with self.assertRaises(ValidationError):
            Section.objects.create(
                class_code="NO-SCHOOL",
                class_name="Unowned Section",
                subject="Reading",
            )

    def test_legacy_unclassified_sections_remain_supported(self):
        Section.objects.create(
            class_code="LEGACY-1", class_name="Legacy One", school=self.school, teacher=self.teacher, subject="Reading"
        )
        Section.objects.create(
            class_code="LEGACY-2", class_name="Legacy Two", school=self.school, teacher=self.teacher, subject="Reading"
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

    def test_legacy_class_code_join_route_is_removed(self):
        response = self.client.post(
            "/api/join-class/",
            json.dumps({"class_code": self.section.class_code}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Enrollment.objects.filter(student=self.student).exists())

    def test_existing_enrollment_survives_without_join_route(self):
        enrollment = Enrollment.objects.create(student=self.student, section=self.section)
        self.client.post(
            "/api/join-class/",
            json.dumps({"class_code": self.section.class_code}),
            content_type="application/json",
        )
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.is_active)

    def test_student_dashboard_has_no_class_code_join_ui(self):
        self.section.add_student(self.student)
        session = self.client.session
        session.update({"user_id": self.student.id, "user_role": "student", "email": self.student.email})
        session.save()

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/api/join-class/")
        self.assertNotContains(response, "data-class-code-form")
        self.assertContains(response, "My Classes")


class SchoolScopedSectionIsolationTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADM-SCHOOL-SCOPE", "admin", "school-scope-admin@example.com")
        self.student = make_user("STU-SCHOOL-SCOPE", "student", "school-scope-student@example.com")
        self.school_a = School.objects.create(
            name="School A",
            code="SCHOOL-A",
            address="123 School A Road",
            logo="schools/existing-a.png",
        )
        self.school_b = School.objects.create(name="School B", code="SCHOOL-B", address="")
        session = self.client.session
        session.update({
            "user_id": self.admin.id,
            "user_role": "admin",
            "email": self.admin.email,
        })
        session.save()

    def _create_rizal(self, school):
        return self.client.post(
            reverse("admin_school_detail", args=[school.id]),
            {"grade_level": "Grade 2", "section": "Rizal"},
        )

    def test_same_grade_and_section_can_exist_in_two_schools(self):
        response_a = self._create_rizal(self.school_a)
        response_b = self._create_rizal(self.school_b)

        self.assertEqual(response_a.status_code, 302)
        self.assertEqual(response_b.status_code, 302)
        sections = Section.objects.filter(grade_level="Grade 2", section="RIZAL")
        self.assertEqual(sections.count(), 2)
        self.assertSetEqual(set(sections.values_list("school_id", flat=True)), {self.school_a.id, self.school_b.id})

        section_a = sections.get(school=self.school_a)
        section_b = sections.get(school=self.school_b)
        page_a = self.client.get(reverse("admin_school_detail", args=[self.school_a.id]))
        page_b = self.client.get(reverse("admin_school_detail", args=[self.school_b.id]))
        self.assertEqual(
            [section.id for section in page_a.context["sections_by_grade"]["Grade 2"]],
            [section_a.id],
        )
        self.assertEqual(
            [section.id for section in page_b.context["sections_by_grade"]["Grade 2"]],
            [section_b.id],
        )

        duplicate_a = self._create_rizal(self.school_a)
        duplicate_b = self._create_rizal(self.school_b)
        self.assertEqual(duplicate_a.status_code, 200)
        self.assertEqual(duplicate_b.status_code, 200)
        self.assertContains(duplicate_a, "already exists in School A")
        self.assertContains(duplicate_b, "already exists in School B")
        self.assertEqual(Section.objects.filter(grade_level="Grade 2", section="RIZAL").count(), 2)

        section_b.add_student(self.student)
        self.assertEqual(section_a.get_student_count(), 0)
        self.assertEqual(section_b.get_student_count(), 1)

        self.client.post(
            reverse("admin_school_section_update", args=[section_a.id]),
            {"action": "deactivate"},
        )
        section_a.refresh_from_db()
        section_b.refresh_from_db()
        self.assertFalse(section_a.is_active)
        self.assertTrue(section_b.is_active)
        self.assertEqual(section_b.get_student_count(), 1)

    def test_admin_school_list_hides_default_and_shows_school_card_details(self):
        principal = make_user("PRN-SCHOOL-SCOPE", "principal", "school-scope-principal@example.com")
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.save(update_fields=["school_record", "school"])

        response = self.client.get(reverse("admin_school"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.school_a.name)
        self.assertContains(response, self.school_a.code)
        self.assertContains(response, "Principal Account")
        self.assertContains(response, "Active")
        self.assertContains(response, reverse("admin_school_detail", args=[self.school_a.id]))
        self.assertNotContains(response, "Default School")

    def test_school_workspace_creates_and_displays_relational_principal(self):
        with patch("pabasa_app.views._send_principal_credentials_email"):
            response = self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Juan",
                    "middle_initial": "D",
                    "last_name": "Dela Cruz",
                    "email": "juan.school-a@example.com",
                    "contact_no": "09170000001",
                    "school_id": str(self.school_b.id),
                },
            )
        self.assertEqual(response.status_code, 302)
        principal = User.objects.get(email="juan.school-a@example.com")
        self.assertEqual(principal.role, "principal")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertEqual(User.objects.filter(role="principal", school_record=self.school_b, is_archived=False).count(), 0)
        self.assertContains(self.client.get(reverse("admin_school_detail", args=[self.school_a.id])), "Juan")
        self.assertContains(self.client.get(reverse("admin_school")), "Juan")

        edit_response = self.client.post(
            reverse("admin_principal_edit", args=[principal.id]),
            {
                "first_name": "Juan Updated",
                "last_name": "Dela Cruz",
                "email": principal.email,
                "contact_no": principal.contact_no,
                "school_name": self.school_b.name,
                "school_address": "Updated address",
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        principal.refresh_from_db()
        self.assertEqual(principal.school_record_id, self.school_a.id)

    def test_principal_form_has_optional_suffix_contact_and_loading_guard(self):
        response = self.client.get(reverse("admin_school_detail", args=[self.school_a.id]))

        self.assertContains(response, "School Information")
        self.assertContains(response, self.school_a.name)
        self.assertContains(response, self.school_a.code)
        self.assertContains(response, self.school_a.address)
        self.assertContains(response, 'name="suffix"')
        self.assertContains(response, 'Suffix <span class="text-muted">(optional)</span>')
        self.assertContains(response, 'name="contact_no" type="tel" class="form-control"')
        self.assertNotContains(response, 'name="contact_no" type="tel" class="form-control" value="" required')
        self.assertContains(response, 'id="createPrincipalLoadingModal"')
        self.assertContains(response, 'Creating Principal Account')
        self.assertContains(response, 'form.dataset.submitting')
        self.assertContains(response, 'submitButton.disabled = true')
        self.assertContains(response, 'if (!form.checkValidity()) return')
        self.assertNotContains(response, 'name="school_logo"')

        global_create_page = self.client.get(reverse("admin_principals"))
        self.assertNotContains(global_create_page, 'name="school_logo"')

    def test_principal_creation_accepts_blank_suffix_and_contact(self):
        with patch("pabasa_app.views._send_principal_credentials_email") as send_email:
            response = self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Blank",
                    "last_name": "Optional",
                    "suffix": "",
                    "email": "blank-optionals@example.com",
                    "contact_no": "",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        principal = User.objects.get(email="blank-optionals@example.com")
        self.assertEqual(principal.suffix, "")
        self.assertEqual(principal.contact_no, "")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertTrue(principal.must_change_password)
        self.assertTrue(principal.check_password("OPTIONAL123"))
        self.assertNotEqual(principal.password_hash, "OPTIONAL123")
        self.assertContains(response, "Principal account created successfully")
        self.assertContains(response, "Login credentials were sent")
        self.assertContains(response, "Blank Optional")
        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.args[3], "OPTIONAL123")

    def test_global_principal_creation_needs_no_logo_and_does_not_copy_school_address(self):
        with patch("pabasa_app.views._send_principal_credentials_email"):
            response = self.client.post(
                reverse("admin_principals"),
                {
                    "first_name": "Global",
                    "middle_initial": "",
                    "last_name": "Dela Cruz",
                    "suffix": "",
                    "school_name": self.school_a.name,
                    "email": "global-principal@example.com",
                    "contact_no": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        principal = User.objects.get(email="global-principal@example.com")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertTrue(principal.must_change_password)
        self.assertTrue(principal.check_password("DELACRUZ123"))
        self.assertFalse(principal.profile_picture)
        self.assertNotIn("principal_school_info", principal.preference)
        self.assertNotIn(self.school_a.address, str(principal.tags))

    def test_smtp_failure_keeps_principal_and_shows_warning(self):
        with patch(
            "pabasa_app.views._send_principal_credentials_email",
            side_effect=socket.gaierror(11001, "getaddrinfo failed"),
        ):
            response = self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Mail",
                    "last_name": "Unavailable",
                    "suffix": "III",
                    "email": "smtp-unavailable@example.com",
                    "contact_no": "",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        principal = User.objects.get(email="smtp-unavailable@example.com")
        self.assertEqual(principal.suffix, "III")
        self.assertEqual(principal.contact_no, "")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertTrue(principal.must_change_password)
        self.assertContains(response, "Mail Unavailable III")
        self.assertContains(response, "credentials email could not be sent")

    def test_second_active_principal_is_rejected_by_school_workspace(self):
        first = make_user("PRN-SCHOOL-A-ENDPOINT", "principal", "endpoint-first@example.com")
        first.school_record = self.school_a
        first.school = self.school_a.name
        first.save(update_fields=["school_record", "school"])

        with patch("pabasa_app.views._send_principal_credentials_email") as send_email:
            response = self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Second",
                    "last_name": "Blocked",
                    "email": "endpoint-second@example.com",
                    "contact_no": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already has an active Principal")
        self.assertFalse(User.objects.filter(email="endpoint-second@example.com").exists())
        self.assertEqual(User.objects.filter(role="principal", school_record=self.school_a, is_archived=False).count(), 1)
        send_email.assert_not_called()

    def test_principal_edit_preserves_school_and_accepts_suffix_and_blank_contact(self):
        principal = make_user("PRN-EDIT-OPTIONALS", "principal", "edit-optionals@example.com")
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.contact_no = "09170000000"
        principal.profile_picture = "pabasa_app/uploads/school_logos/legacy.png"
        principal.preference = {
            "principal_school_info": {
                "name": "Legacy School Name",
                "address": "Legacy copied address",
                "logo": "pabasa_app/uploads/school_logos/legacy.png",
            }
        }
        principal.save(update_fields=["school_record", "school", "contact_no", "profile_picture", "preference"])

        edit_page = self.client.get(reverse("admin_principal_edit", args=[principal.id]))
        self.assertContains(edit_page, 'name="suffix"')
        self.assertContains(edit_page, self.school_a.code)
        self.assertContains(edit_page, self.school_a.address)
        self.assertContains(edit_page, 'id="schoolName" type="text"')
        self.assertNotContains(edit_page, 'name="school_logo"')

        response = self.client.post(
            reverse("admin_principal_edit", args=[principal.id]),
            {
                "first_name": "Edited",
                "last_name": "Principal",
                "suffix": "III",
                "email": principal.email,
                "contact_no": "",
                "school_name": self.school_b.name,
                "school_address": "Updated address",
            },
        )

        self.assertEqual(response.status_code, 302)
        principal.refresh_from_db()
        self.assertEqual(principal.suffix, "III")
        self.assertEqual(principal.contact_no, "")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertEqual(principal.profile_picture, "pabasa_app/uploads/school_logos/legacy.png")
        self.assertEqual(principal.preference["principal_school_info"]["logo"], "pabasa_app/uploads/school_logos/legacy.png")
        self.school_a.refresh_from_db()
        self.assertEqual(self.school_a.logo, "schools/existing-a.png")

    def test_principal_detail_uses_relational_school_information(self):
        principal = make_user("PRN-DETAIL-SCHOOL", "principal", "detail-school@example.com")
        principal.first_name = "Detail"
        principal.last_name = "Principal"
        principal.suffix = "III"
        principal.contact_no = ""
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.preference = {
            "principal_school_info": {
                "address": "Wrong legacy address",
                "contact": "09179999999",
            }
        }
        principal.save()

        response = self.client.get(reverse("admin_principal_detail", args=[principal.id]))
        content = response.content.decode()
        principal_section = content.split("Principal Details", 1)[1].split("School Information", 1)[0]
        school_section = content.split("School Information", 1)[1].split('</div>', 1)[0]

        self.assertContains(response, self.school_a.code)
        self.assertContains(response, self.school_a.address)
        self.assertNotContains(response, "Wrong legacy address")
        self.assertIn("Contact Number", principal_section)
        self.assertNotIn("Contact Number", school_section)
        self.assertIn("Suffix", principal_section)
        self.assertIn("III", principal_section)

    def test_principal_password_reset_preserves_identity_and_sends_new_temporary_password(self):
        principal = make_user("PRN-RESET-SUCCESS", "principal", "reset-success@example.com")
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.password_hash = make_password("OldPrincipalPassword!1")
        principal.save(update_fields=["school_record", "school", "password_hash"])
        original_hash = principal.password_hash
        original_count = User.objects.filter(role="principal").count()

        with patch("pabasa_app.views._send_principal_credentials_email") as send_email:
            response = self.client.post(
                reverse("admin_principal_reset_password", args=[principal.id]),
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Principal password reset successfully")
        self.assertContains(response, 'id="resetPrincipalPasswordForm"')
        self.assertContains(response, "form.dataset.submitting")
        self.assertContains(response, "button.disabled = true")
        principal.refresh_from_db()
        self.assertNotEqual(principal.password_hash, original_hash)
        self.assertTrue(principal.must_change_password)
        self.assertFalse(check_password("OldPrincipalPassword!1", principal.password_hash))
        self.assertEqual(principal.custom_id, "PRN-RESET-SUCCESS")
        self.assertEqual(principal.email, "reset-success@example.com")
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertEqual(User.objects.filter(role="principal").count(), original_count)
        send_email.assert_called_once()
        temporary_password = send_email.call_args.args[3]
        self.assertEqual(temporary_password, "ACCOUNT123")
        self.assertTrue(check_password(temporary_password, principal.password_hash))
        self.assertNotEqual(principal.password_hash, temporary_password)
        self.assertTrue(send_email.call_args.kwargs["is_reset"])
        self.assertNotContains(response, temporary_password)
        self.assertNotIn(temporary_password, str(response.redirect_chain))
        self.assertNotIn(temporary_password, str(principal.tags))
        self.assertNotIn(temporary_password, str(principal.preference))

    def test_principal_temporary_password_normalizes_surname_and_ignores_suffix(self):
        from pabasa_app.views import _principal_temporary_password

        self.assertEqual(_principal_temporary_password("Santos"), "SANTOS123")
        self.assertEqual(_principal_temporary_password("Dela Cruz"), "DELACRUZ123")
        self.assertEqual(_principal_temporary_password("De Leon"), "DELEON123")
        self.assertEqual(_principal_temporary_password("Dela-Cruz, Jr."), "DELACRUZJR123")

        with patch("pabasa_app.views.send_mail") as send_email:
            self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Suffix",
                    "last_name": "Santos",
                    "suffix": "III",
                    "email": "suffix-password@example.com",
                    "contact_no": "",
                },
            )

        principal = User.objects.get(email="suffix-password@example.com")
        self.assertEqual(principal.suffix, "III")
        self.assertTrue(principal.check_password("SANTOS123"))
        self.assertFalse(principal.check_password("SANTOSIII123"))
        email_message = send_email.call_args.args[1]
        self.assertIn("Temporary Password: SANTOS123", email_message)
        self.assertNotIn("SANTOSIII123", email_message)

    def test_principal_must_change_temporary_password_before_dashboard_access(self):
        principal = make_user("PRN-TEMP-LOGIN", "principal", "temp-login@example.com")
        principal.first_name = "Temporary"
        principal.last_name = "Dela Cruz"
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.must_change_password = True
        principal.set_password("DELACRUZ123")
        principal.save()

        login_response = self.client.post(
            reverse("login_user"),
            {"custom_id": principal.custom_id, "password": "DELACRUZ123"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.json()["success"])
        self.assertEqual(
            login_response.json()["redirect_url"],
            reverse("principal_change_temporary_password"),
        )

        change_page = self.client.get(reverse("principal_change_temporary_password"))
        self.assertContains(change_page, "New Password")
        self.assertContains(change_page, "Confirm New Password")
        self.assertRedirects(
            self.client.get(reverse("dashboard_principal")),
            reverse("principal_change_temporary_password"),
        )
        self.assertRedirects(
            self.client.get(reverse("principal_settings")),
            reverse("principal_change_temporary_password"),
        )

        mismatch = self.client.post(
            reverse("principal_change_temporary_password"),
            {"new_password": "NewPrivatePassword!908", "confirm_password": "DifferentPassword!908"},
        )
        self.assertContains(mismatch, "do not match")
        principal.refresh_from_db()
        self.assertTrue(principal.must_change_password)

        same_temporary = self.client.post(
            reverse("principal_change_temporary_password"),
            {"new_password": "DELACRUZ123", "confirm_password": "DELACRUZ123"},
        )
        self.assertContains(same_temporary, "instead of the temporary password")

        weak = self.client.post(
            reverse("principal_change_temporary_password"),
            {"new_password": "short", "confirm_password": "short"},
        )
        self.assertContains(weak, "too short")

        old_session_key = self.client.session.session_key
        new_private_password = "NewPrivatePassword!908"
        changed = self.client.post(
            reverse("principal_change_temporary_password"),
            {"new_password": new_private_password, "confirm_password": new_private_password},
        )
        self.assertRedirects(changed, reverse("dashboard_principal"))
        principal.refresh_from_db()
        self.assertFalse(principal.must_change_password)
        self.assertTrue(principal.check_password(new_private_password))
        self.assertFalse(principal.check_password("DELACRUZ123"))
        self.assertNotEqual(self.client.session.session_key, old_session_key)
        self.assertEqual(self.client.get(reverse("dashboard_principal")).status_code, 200)

        self.client.get(reverse("logout"))
        old_login = self.client.post(
            reverse("login_user"),
            {"custom_id": principal.custom_id, "password": "DELACRUZ123"},
        )
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post(
            reverse("login_user"),
            {"custom_id": principal.custom_id, "password": new_private_password},
        )
        self.assertEqual(new_login.json()["redirect_url"], reverse("dashboard_principal"))

    def test_teacher_and_student_login_redirects_are_unchanged(self):
        for role, custom_id, expected_url in [
            ("teacher", "TCH-4321", "/dashboard/teacher/"),
            ("student", "G2-4321", "/dashboard/"),
        ]:
            user = make_user(custom_id, role, f"{role}-login@example.com")
            user.set_password("ExistingPassword!908")
            user.save(update_fields=["password_hash", "updated_at"])
            response = self.client.post(
                reverse("login_user"),
                {"custom_id": custom_id, "password": "ExistingPassword!908"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["redirect_url"], expected_url)
            self.client.get(reverse("logout"))

    def test_smtp_failure_after_password_reset_is_nonfatal_and_not_logged_with_password(self):
        principal = make_user("PRN-RESET-SMTP", "principal", "reset-smtp@example.com")
        principal.school_record = self.school_a
        principal.school = self.school_a.name
        principal.save(update_fields=["school_record", "school"])
        original_hash = principal.password_hash

        with patch(
            "pabasa_app.views._send_principal_credentials_email",
            side_effect=socket.gaierror(11001, "getaddrinfo failed"),
        ) as send_email, patch("pabasa_app.views.logger.warning") as warning_log:
            response = self.client.post(
                reverse("admin_principal_reset_password", args=[principal.id]),
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporary credentials email could not be sent")
        self.assertContains(response, "SMTP configuration is required")
        principal.refresh_from_db()
        self.assertNotEqual(principal.password_hash, original_hash)
        self.assertTrue(principal.must_change_password)
        self.assertEqual(principal.school_record_id, self.school_a.id)
        self.assertEqual(User.objects.filter(email=principal.email).count(), 1)
        warning_log.assert_called_once()
        temporary_password = send_email.call_args.args[3]
        logged_values = " ".join(str(value) for value in warning_log.call_args.args)
        self.assertNotIn(temporary_password, logged_values)
        self.assertNotContains(response, temporary_password)
        self.assertNotIn(temporary_password, str(response.redirect_chain))
        self.assertNotIn(temporary_password, str(principal.tags))
        self.assertNotIn(temporary_password, str(principal.preference))

    def test_one_active_principal_per_school_and_independent_other_school(self):
        first = make_user("PRN-SCHOOL-A-1", "principal", "principal-a-1@example.com")
        first.school_record = self.school_a
        first.save(update_fields=["school_record"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(
                custom_id="PRN-SCHOOL-A-2", role="principal", first_name="Second", last_name="Principal",
                middle_initial="", suffix="", sex="N/A", birth_month=1, birth_day=1, birth_year=1990,
                email="principal-a-2@example.com", password_hash="hashed", school_record=self.school_a,
            )
        second = make_user("PRN-SCHOOL-B-1", "principal", "principal-b-1@example.com")
        second.school_record = self.school_b
        second.save(update_fields=["school_record"])
        self.assertEqual(second.school_record_id, self.school_b.id)

    def test_archived_principal_can_be_replaced_without_deleting_history(self):
        principal = make_user("PRN-ARCHIVE-A", "principal", "principal-archive@example.com")
        principal.school_record = self.school_a
        principal.save(update_fields=["school_record"])
        response = self.client.post(reverse("admin_principal_deactivate", args=[principal.id]))
        self.assertEqual(response.status_code, 302)
        principal.refresh_from_db()
        self.assertTrue(principal.is_archived)
        self.assertEqual(principal.school_record_id, self.school_a.id)
        with patch("pabasa_app.views._send_principal_credentials_email"):
            replacement = self.client.post(
                reverse("admin_school_detail", args=[self.school_a.id]),
                {
                    "action": "create_principal",
                    "first_name": "Replacement",
                    "last_name": "Principal",
                    "email": "replacement-principal@example.com",
                    "contact_no": "09170000002",
                },
            )
        self.assertEqual(replacement.status_code, 302)
        self.assertEqual(
            User.objects.get(email="replacement-principal@example.com").school_record_id,
            self.school_a.id,
        )

    def test_archived_school_rejects_principal_creation(self):
        self.school_a.archive()
        response = self.client.post(
            reverse("admin_school_detail", args=[self.school_a.id]),
            {
                "action": "create_principal",
                "first_name": "Blocked",
                "last_name": "Principal",
                "email": "blocked-principal@example.com",
                "contact_no": "09170000003",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="blocked-principal@example.com").exists())


class SchoolAwareSignupTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Signup School A", code="SIGNUP-A")
        self.school_b = School.objects.create(name="Signup School B", code="SIGNUP-B")
        self.teacher = make_user("TCH-SIGNUP-SCOPE", "teacher", "signup-existing-teacher@example.com")
        self.teacher_b = make_user("TCH-SIGNUP-SCOPE-B", "teacher", "signup-existing-teacher-b@example.com")
        self.teacher_section = Section.objects.create(
            class_code="SIGNUP-A-1",
            class_name="Grade 2 - Rizal",
            grade_level="Grade 2",
            section="Rizal",
            school=self.school_a,
            teacher=self.teacher,
            subject="Reading",
        )
        self.student_section = Section.objects.create(
            class_code="SIGNUP-B-1",
            class_name="Grade 2 - Rizal",
            grade_level="Grade 2",
            section="Rizal",
            school=self.school_b,
            subject="Reading",
        )

    def _registration_payload(self, section, email, **extra):
        payload = {
            "first_name": "Signup",
            "last_name": "User",
            "email": email,
            "password": "Signup123",
            "confirm_password": "Signup123",
            "sex": "female",
            "birth_month": "1",
            "birth_day": "5",
            "birth_year": "1990",
            "school_id": str(section.school_id),
            "grade_level": section.grade_level,
            "section": str(section.id),
            "department": "Mathematics",
        }
        payload.update(extra)
        return payload

    def test_signup_sections_are_school_scoped_and_default_is_hidden(self):
        response = self.client.get(
            reverse("signup_sections"),
            {"role": "student", "school_id": self.school_b.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["grades"], ["Grade 2"])
        self.assertEqual([item["id"] for item in response.json()["sections"]], [self.student_section.id])

        teacher_response = self.client.get(
            reverse("signup_sections"),
            {"role": "teacher", "school_id": self.school_a.id, "grade_level": "Grade 2"},
        )
        self.assertEqual(teacher_response.json()["sections"], [])
        page = self.client.get(reverse("teacher_signup"))
        self.assertContains(page, self.school_a.name)
        self.assertContains(page, self.school_b.name)
        self.assertNotContains(page, "Default School")

    def test_teacher_signup_rejects_cross_school_section_and_assigns_correct_school(self):
        payload = self._registration_payload(self.student_section, "signup-teacher@example.com")
        payload["school_id"] = str(self.school_a.id)
        response = self.client.post(reverse("register_teacher"), payload)
        self.assertEqual(response.status_code, 400)

        available = Section.objects.create(
            class_code="SIGNUP-A-2",
            class_name="Grade 2 - Aquino",
            grade_level="Grade 2",
            section="Aquino",
            school=self.school_a,
            subject="Reading",
        )
        payload = self._registration_payload(available, "signup-teacher-valid@example.com")
        with patch("pabasa_app.views.send_teacher_signup_otp_email"):
            response = self.client.post(reverse("register_teacher"), payload)
        self.assertEqual(response.status_code, 200)
        otp = self.client.session["pending_teacher_signup_otp"]
        with patch("pabasa_app.views.send_teacher_confirmation_email"), patch("pabasa_app.views._notify_admins"), patch("pabasa_app.views._notify_principals"):
            response = self.client.post(reverse("verify_teacher_otp"), {"otp": otp})
        self.assertEqual(response.status_code, 200)

        created = User.objects.get(email="signup-teacher-valid@example.com")
        self.assertEqual(created.school_record_id, self.school_a.id)
        self.assertEqual(created.section, available.section)
        available.refresh_from_db()
        self.assertEqual(available.teacher_id, created.id)

    def test_student_signup_accepts_occupied_section_and_rejects_cross_school_section(self):
        occupied = Section.objects.create(
            class_code="SIGNUP-B-2",
            class_name="Grade 2 - Aquino",
            grade_level="Grade 2",
            section="Aquino",
            school=self.school_b,
            teacher=self.teacher_b,
            subject="Reading",
        )
        payload = self._registration_payload(occupied, "signup-student-cross@example.com", lrn="123456789012")
        payload["school_id"] = str(self.school_a.id)
        response = self.client.post(reverse("register_student"), payload)
        self.assertEqual(response.status_code, 400)

        payload = self._registration_payload(self.student_section, "signup-student-valid@example.com", lrn="123456789013")
        with patch("pabasa_app.views.send_student_signup_otp_email"):
            response = self.client.post(reverse("register_student"), payload)
        self.assertEqual(response.status_code, 200)
        otp = self.client.session["pending_student_signup_otp"]
        with patch("pabasa_app.views.send_student_confirmation_email"), patch("pabasa_app.views._notify_admins"):
            response = self.client.post(reverse("verify_student_otp"), {"otp": otp})
        self.assertEqual(response.status_code, 200)
        created = User.objects.get(email="signup-student-valid@example.com")
        self.assertEqual(created.school_record_id, self.school_b.id)
        self.assertEqual(created.section, self.student_section.section)
        self.assertTrue(Enrollment.objects.filter(student=created, section=self.student_section, is_active=True).exists())



class StudentSignupAutomaticEnrollmentTests(TestCase):
    """OTP signup resolves the configured canonical class, whether or not a teacher is assigned yet."""

    def setUp(self):
        self.teacher = make_user("TCH-AUTO", "teacher", "auto-teacher@example.com")
        self.school = School.objects.create(name="Automatic Signup School", code="AUTO-SIGNUP-SCHOOL")
        self.student_number = 0

    def _create_teacher_class(self, grade_level="Grade 2", section_name="BONIFACIO"):
        return Section.objects.create(
            school=self.school,
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
        section_count = Section.objects.count()

        student = self._signup_and_verify()

        self.assertTrue(teacher_class.has_student(student))
        self.assertEqual(Enrollment.objects.filter(student=student, section=teacher_class).count(), 1)
        self.assertEqual(Section.objects.count(), section_count)

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
    def setUp(self):
        self.school = School.objects.create(name="Teacher Signup School", code="TEACHER-SIGNUP-SCHOOL")

    def test_teacher_otp_assigns_the_existing_canonical_section(self):
        section = Section.objects.create(
            school=self.school,
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
            section_count = Section.objects.count()
            self.assertEqual(self.client.post(reverse("register_teacher"), payload).status_code, 200)
            response = self.client.post(reverse("verify_teacher_otp"), {"otp": self.client.session["pending_teacher_signup_otp"]})
        self.assertTrue(response.json()["success"])
        section.refresh_from_db()
        self.assertEqual(section.teacher.email, payload["email"])
        self.assertEqual(Section.objects.count(), section_count)

    def test_unconfigured_section_is_rejected_without_creating_one(self):
        payload = {
            "first_name": "Teacher", "last_name": "Missing", "email": "missing@example.com",
            "password": "Teacher123", "confirm_password": "Teacher123", "sex": "female",
            "birth_month": "1", "birth_day": "1", "birth_year": "1990",
            "grade_level": "Grade 2", "section": "NOT-CONFIGURED",
        }
        section_count = Section.objects.count()
        response = self.client.post(reverse("register_teacher"), payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Section.objects.count(), section_count)

    def test_assigned_section_rejects_a_second_teacher_before_otp(self):
        teacher = make_user("TCH-EXISTING", "teacher", "existing@example.com")
        Section.objects.create(school=self.school, class_code="G2-RIZAL", class_name="Grade 2 - RIZAL", grade_level="Grade 2", section="RIZAL", teacher=teacher, subject="Reading")
        payload = {"first_name": "Teacher", "last_name": "Second", "email": "second@example.com", "password": "Teacher123", "confirm_password": "Teacher123", "sex": "female", "birth_month": "1", "birth_day": "1", "birth_year": "1990", "grade_level": "Grade 2", "section": "RIZAL"}
        response = self.client.post(reverse("register_teacher"), payload)
        self.assertEqual(response.status_code, 409)
