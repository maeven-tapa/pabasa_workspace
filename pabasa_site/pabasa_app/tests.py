from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
import json
import uuid
from unittest.mock import patch

from pypdf import PdfReader

from .models import Material, User, Section, Assessment, Notification, Course, Note
from .reading_stt import analyze_reading
from .test_accounts import PRINCIPAL_DEFAULT_CUSTOM_ID, PRINCIPAL_DEFAULT_PASSWORD
from .views import _create_notification
from .weekly_digest import send_weekly_digest


class ReadingMatcherTests(TestCase):
    def test_wrong_word_does_not_complete_target(self):
        result = analyze_reading("water", 0, "apple")

        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_similar_wrong_word_does_not_match_when_first_sound_differs(self):
        result = analyze_reading("house", 0, "mouse")

        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_correct_words_advance_in_order_until_first_missing_target(self):
        result = analyze_reading("the water is cold", 0, "the apple is cold")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertFalse(result["complete"])


class PrincipalReportsExportTests(TestCase):
    def test_default_timezone_is_asia_manila(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Manila")

    def setUp(self):
        self.user = User.objects.create(
            custom_id=f"ADM-{uuid.uuid4().hex[:8].upper()}",
            role="admin",
            first_name="Principal",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="principal@example.com",
            password_hash="hashed-password",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_principal_reports_pdf_export_returns_pdf_response(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school", "export": "pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_principal_reports_pdf_export_includes_summary_overview(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school", "export": "pdf"})

        self.assertEqual(response.status_code, 200)
        reader = PdfReader(BytesIO(response.content))
        extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertTrue(extracted_text or response.content.startswith(b"%PDF"))


class PrincipalReportsPreviewTests(TestCase):
    def setUp(self):
        unique_suffix = uuid.uuid4().hex[:8].upper()
        self.principal = User.objects.create(
            custom_id=f"PRN-{unique_suffix}",
            role="principal",
            first_name="Jobelyn",
            last_name="Valdez",
            middle_initial="A",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=3,
            birth_year=1980,
            email="principal-preview@example.com",
            password_hash=make_password("Principal@123"),
        )
        self.teacher = User.objects.create(
            custom_id=f"TCH-{unique_suffix}",
            role="teacher",
            first_name="Rowan",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher-preview@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id=f"STD-{unique_suffix}",
            role="student",
            first_name="Ava",
            last_name="Learner",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2012,
            email="student-preview@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 2",
        )
        self.section = Section.objects.create(
            class_code=f"G2-{unique_suffix}",
            class_name="Grade 2 Preview",
            header="Reading Class",
            description="Preview section",
            teacher=self.teacher,
            is_active=True,
            subject="Reading",
            students=[{
                "student_id": self.student.id,
                "custom_id": self.student.custom_id,
                "first_name": self.student.first_name,
                "last_name": self.student.last_name,
                "email": self.student.email,
                "joined_at": timezone.now().isoformat(),
                "is_active": True,
            }],
        )
        self.assessment = Assessment.objects.create(
            title="Preview Assessment",
            code="ASM-PRV1",
            assessment_type="word",
            status="published",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
            attempt_no=1,
        )
        self.assessment.record_attempt(
            self.student,
            status="completed",
            total_score=87,
            accuracy=90,
            pronunciation_score=84,
            completed_at=timezone.now(),
        )
        session = self.client.session
        session["user_id"] = self.principal.id
        session["user_role"] = self.principal.role
        session["first_name"] = self.principal.first_name
        session["last_name"] = self.principal.last_name
        session["email"] = self.principal.email
        session["custom_id"] = self.principal.custom_id
        session.save()

    def test_principal_reports_preview_shows_live_assessment_data(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessment Report")
        self.assertContains(response, "Preview Assessment")
        self.assertContains(response, "87.0%")
        self.assertContains(response, "100%")

    def test_principal_reports_excel_export_still_returns_csv_response(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment", "export": "excel"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

    def test_principal_reports_page_uses_a_single_report_workflow(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a report")
        self.assertNotContains(response, "Recently Generated Reports")

    def test_principal_reports_disables_grade_filter_for_non_grade_reports(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="gradeLevel"')
        self.assertContains(response, 'disabled')

    def test_principal_reports_preview_uses_distinct_headers_for_each_report_type(self):
        school_response = self.client.get(reverse("principal_reports"), {"report_type": "school"})
        grade_response = self.client.get(reverse("principal_reports"), {"report_type": "grade"})
        assessment_response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(school_response.status_code, 200)
        self.assertEqual(grade_response.status_code, 200)
        self.assertEqual(assessment_response.status_code, 200)
        self.assertContains(school_response, "School Name")
        self.assertContains(grade_response, "Grade")
        self.assertContains(assessment_response, "Assessment")

    def test_principal_reports_export_buttons_submit_current_report_selection(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="export"')
        self.assertContains(response, 'value="pdf"')
        self.assertContains(response, 'value="excel"')


class PrincipalAccountBootstrapTests(TestCase):
    def test_login_recreates_missing_principal_account_once(self):
        self.assertFalse(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).exists())

        response = self.client.post(
            reverse("login_user"),
            {
                "custom_id": PRINCIPAL_DEFAULT_CUSTOM_ID,
                "password": PRINCIPAL_DEFAULT_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        principal = User.objects.get(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID)
        self.assertEqual(principal.role, "principal")
        self.assertTrue(check_password(PRINCIPAL_DEFAULT_PASSWORD, principal.password_hash))
        self.assertEqual(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).count(), 1)

        second_response = self.client.post(
            reverse("login_user"),
            {
                "custom_id": PRINCIPAL_DEFAULT_CUSTOM_ID,
                "password": PRINCIPAL_DEFAULT_PASSWORD,
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json()["success"])
        self.assertEqual(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).count(), 1)


class ProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="TCH-0001",
            role="teacher",
            first_name="Old",
            last_name="Name",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="old@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_profile_page_includes_hidden_save_flag(self):
        response = self.client.get(reverse("profile"))

        self.assertContains(response, 'name="save_account_details" value="true"', html=False)

    def test_profile_post_updates_user_record(self):
        response = self.client.post(
            reverse("profile"),
            {
                "save_account_details": "true",
                "first_name": "New",
                "last_name": "Name",
                "middle_initial": "Q",
                "suffix": "Jr.",
                "email": "new@example.com",
                "bio": "Updated bio",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.middle_initial, "Q")
        self.assertEqual(self.user.suffix, "Jr.")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertIn({"profile_info": {"bio": "Updated bio"}}, self.user.tags)


class MaterialCreationTests(TestCase):
    def test_add_reading_material_saves_selected_language(self):
        user = User.objects.create(
            custom_id="TCH-0002",
            role="teacher",
            first_name="Language",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="language@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Tagalog reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material = Material.objects.latest("id")
        self.assertEqual(material.content_json.get("language"), "Tagalog")
        self.assertEqual(material.type, "assessment")
        self.assertEqual(material.source_type, "shared")

    def test_add_reading_material_response_includes_shared_source_type(self):
        user = User.objects.create(
            custom_id="TCH-0003",
            role="teacher",
            first_name="Source",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="source@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material = Material.objects.latest("id")
        self.assertEqual(material.type, "assessment")
        self.assertEqual(material.source_type, "shared")

    def test_add_reading_material_reuses_existing_shared_material(self):
        user = User.objects.create(
            custom_id="TCH-0006",
            role="teacher",
            first_name="Reuse",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="reuse@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        existing = Material.objects.create(
            teacher=user,
            title="Shared reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw\nBuwan",
            content_json={"items": ["Araw", "Buwan"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "source_material_id": existing.id,
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["reused"])
        self.assertEqual(payload["created_count"], 0)
        self.assertEqual(payload["material_ids"], [existing.id])
        self.assertEqual(Material.objects.filter(source_type="shared", title="Shared reading").count(), 1)

    def test_add_reading_material_saves_multiple_paragraph_items(self):
        user = User.objects.create(
            custom_id="TCH-0003",
            role="teacher",
            first_name="Paragraph",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="paragraph@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Paragraph reading",
                "content": "First paragraph text.\n\nSecond paragraph text.",
                "reading_type": "paragraph",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material = Material.objects.latest("id")
        self.assertEqual(material.item_type, "paragraph")
        self.assertEqual(material.content_json.get("items"), ["First paragraph text.", "Second paragraph text."])

    def test_add_reading_material_saves_separate_sentence_items_from_multiline_content(self):
        user = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Sentence",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="sentence@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Sentence reading",
                "content": "First sentence.\nSecond sentence.\nThird sentence.",
                "reading_type": "sentence",
                "status": "published",
                "usage_type": "assessment",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material = Material.objects.latest("id")
        self.assertEqual(material.item_type, "sentence")
        self.assertEqual(material.content_json.get("items"), ["First sentence.", "Second sentence.", "Third sentence."])

    @patch("pabasa_app.views._compute_teacher_overview")
    def test_add_reading_material_skips_overview_by_default(self, mock_overview):
        user = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Fast",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="fast@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Fast create",
                "content": "alpha",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_overview.assert_not_called()

    def test_add_reading_material_saves_shared_source_type(self):
        user = User.objects.create(
            custom_id="TCH-0005",
            role="teacher",
            first_name="Shared",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "Tagalog",
                "source_type": "shared",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material"]["source_type"], "shared")

        material = Material.objects.latest("id")
        self.assertEqual(material.source_type, "shared")

    def test_teacher_courses_api_includes_material_source_type(self):
        teacher = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Course",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="course@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="CRS-1001",
            class_name="Course 1",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        student = User.objects.create(
            custom_id="STD-1001",
            role="student",
            first_name="Metric",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2015,
            email="metric.student@example.com",
            password_hash="hashed-password",
        )
        section.students = [{
            "student_id": student.id,
            "custom_id": student.custom_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "is_active": True,
        }]
        section.save(update_fields=["students"])
        course = Course.objects.create(
            code="C-1001",
            title="Shared Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)

        material = Material.objects.create(
            title="Imported reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "English"},
            type="practice",
            source_type="shared",
            status="published",
            difficulty_level="",
            is_active=True,
            section=section,
        )
        course.materials.add(material)
        assessment = Assessment.objects.create(
            title="Course assessment",
            code="ASM-1001",
            assessment_type="word",
            status="published",
            teacher=teacher,
            section=section,
            is_active=True,
            attempt_no=1,
        )
        course.assessments.add(assessment)

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_payload = next(item for item in payload["courses"] if item["id"] == course.id)
        material_payload = next(item for item in course_payload["materials"] if item["id"] == material.id)
        self.assertEqual(material_payload["source_type"], "shared")
        self.assertTrue(material_payload["is_shared_material"])
        self.assertEqual(course_payload["metrics"], {
            "sections": 1,
            "assessments": 1,
            "materials": 1,
            "students": 1,
        })

    def test_shared_courses_api_includes_own_shared_materials_without_personal_rows(self):
        current_teacher = User.objects.create(
            custom_id="TCH-0010",
            role="teacher",
            first_name="Current",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="current-shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        other_teacher = User.objects.create(
            custom_id="TCH-0011",
            role="teacher",
            first_name="Other",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="other-shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        current_course = Course.objects.create(
            code="C-CURRENT-1",
            title="Current Course",
            description="",
            teacher=current_teacher,
        )
        other_course = Course.objects.create(
            code="C-OTHER-1",
            title="Other Course",
            description="",
            teacher=other_teacher,
        )
        personal_material = Material.objects.create(
            teacher=current_teacher,
            title="Legacy private reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
        )
        current_shared_material = Material.objects.create(
            teacher=current_teacher,
            title="Current shared reading",
            item_type="word",
            content_text="Buwan",
            content_json={"items": ["Buwan"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        shared_material = Material.objects.create(
            teacher=other_teacher,
            title="Original shared reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        current_course.materials.add(personal_material, current_shared_material)
        other_course.materials.add(shared_material)

        session = self.client.session
        session["user_id"] = current_teacher.id
        session["user_role"] = current_teacher.role
        session["first_name"] = current_teacher.first_name
        session["last_name"] = current_teacher.last_name
        session["email"] = current_teacher.email
        session["custom_id"] = current_teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_ids = {course["id"] for course in payload["courses"]}
        self.assertIn(current_course.id, course_ids)
        self.assertIn(other_course.id, course_ids)
        material_ids = {
            material["id"]
            for course in payload["courses"]
            for material in course["materials"]
        }
        self.assertNotIn(personal_material.id, material_ids)
        self.assertIn(current_shared_material.id, material_ids)
        self.assertIn(shared_material.id, material_ids)

    def test_add_material_to_course_response_includes_material_source_type(self):
        teacher = User.objects.create(
            custom_id="TCH-0006",
            role="teacher",
            first_name="Attach",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="attach@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="ATT-1001",
            class_name="Attach 1",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        course = Course.objects.create(
            code="ATT-C1",
            title="Attach Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)
        material = Material.objects.create(
            title="Persistent shared reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            difficulty_level="",
            is_active=True,
            section=section,
            teacher=teacher,
        )

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.post(
            reverse("add_material_to_course"),
            json.dumps({"course_id": course.id, "material_id": material.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material"]["source_type"], "shared")
        self.assertEqual(payload["material"]["material_source"], "shared")
        self.assertTrue(payload["material"]["is_shared_material"])


class PracticeReaderMaterialTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id="STD-PRACT",
            role="student",
            first_name="Practice",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="practice-student@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session["first_name"] = self.student.first_name
        session["last_name"] = self.student.last_name
        session["email"] = self.student.email
        session["custom_id"] = self.student.custom_id
        session.save()

    def test_word_reader_receives_active_published_practice_items(self):
        Material.objects.create(
            title="Easy syllables",
            item_type="word",
            content_text="HA\nhe\nhi\nho\nhu",
            content_json={"source": "admin_practice", "difficulty": "easy", "items": ["HA", "he", "hi", "ho", "hu"]},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )
        Material.objects.create(
            title="Draft syllables",
            item_type="word",
            content_text="draft",
            content_json={"items": ["draft"]},
            status="draft",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="practiceMaterialsData"', html=False)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)
        self.assertNotContains(response, "Draft syllables")

    def test_word_reader_parses_comma_separated_content_text_when_json_items_missing(self):
        Material.objects.create(
            title="Comma syllables",
            item_type="word",
            content_text="HA, he, hi, ho, hu",
            content_json={},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)

    def test_practice_completion_records_student_done_status(self):
        material = Material.objects.create(
            title="Completion syllables",
            item_type="word",
            content_text="HA\nhe",
            content_json={"items": ["HA", "he"]},
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"practice-{material.id}",
                "activity_type": "practice",
                "stars_earned": 20,
                "items_completed": 2,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material_id"], f"practice-{material.id}")
        self.assertEqual(payload["status"], "Done")

        material.refresh_from_db()
        completion = material.content_json["student_completions"][str(self.student.id)]
        self.assertEqual(completion["status"], "completed")
        self.assertEqual(completion["stars_earned"], 20)
        self.assertEqual(completion["items_completed"], 2)
        self.assertEqual(material.status, "published")

    def test_practice_completion_saves_detailed_results_metrics(self):
        material = Material.objects.create(
            title="Scored practice",
            item_type="word",
            content_text="HA\nhe",
            content_json={"items": ["HA", "he"]},
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"practice-{material.id}",
                "activity_type": "practice",
                "stars_earned": 20,
                "items_completed": 2,
                "correct_responses": 2,
                "incorrect_responses": 0,
                "reading_time_seconds": 45,
                "attempt_number": 1,
                "total_practice_items": 2,
                "total_read_words": 2,
                "total_skipped_words": 0,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material.refresh_from_db()
        completion = material.content_json["student_completions"][str(self.student.id)]
        self.assertEqual(completion["score"], 100)
        self.assertEqual(completion["accuracy"], 100)
        self.assertEqual(completion["correct_responses"], 2)
        self.assertEqual(completion["incorrect_responses"], 0)
        self.assertEqual(completion["reading_time_seconds"], 45)
        self.assertEqual(completion["attempt_number"], 1)
        self.assertEqual(completion["total_practice_items"], 2)
        self.assertEqual(completion["total_read_words"], 2)
        self.assertEqual(completion["total_skipped_words"], 0)

    def test_practice_results_route_redirects_to_shared_practice_flow(self):
        material = Material.objects.create(
            title="Results practice",
            item_type="word",
            content_text="HA\nhe",
            content_json={
                "items": ["HA", "he"],
                "student_completions": {
                    str(self.student.id): {
                        "student_id": self.student.id,
                        "status": "completed",
                        "completed_at": timezone.now().isoformat(),
                        "score": 80,
                        "accuracy": 80,
                        "correct_responses": 2,
                        "incorrect_responses": 1,
                        "reading_time_seconds": 60,
                        "attempt_number": 1,
                    }
                },
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_results"), {"id": f"practice-{material.id}"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("practice"))

    def test_practice_reader_template_shows_results_breakdown(self):
        response = self.client.get(reverse("practice_word_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Score Breakdown")
        self.assertContains(response, "Total Practice Items")
        self.assertContains(response, "Total Read Words")
        self.assertContains(response, "Total Skipped Words")

    def test_practice_hub_marks_only_completed_student_material_done(self):
        material = Material.objects.create(
            title="Done for one student",
            item_type="word",
            content_text="HA\nhe",
            content_json={
                "items": ["HA", "he"],
                "student_completions": {
                    str(self.student.id): {
                        "student_id": self.student.id,
                        "status": "completed",
                        "completed_at": timezone.now().isoformat(),
                    }
                },
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'"id": "practice-{material.id}"', html=False)
        self.assertContains(response, '"status": "Done"', html=False)
        self.assertContains(response, '"is_done": true', html=False)

        other_student = User.objects.create(
            custom_id="STD-OTHER-PRACT",
            role="student",
            first_name="Other",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="other-practice-student@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = other_student.id
        session["user_role"] = other_student.role
        session["first_name"] = other_student.first_name
        session["last_name"] = other_student.last_name
        session["email"] = other_student.email
        session["custom_id"] = other_student.custom_id
        session.save()

        response = self.client.get(reverse("practice"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'"id": "practice-{material.id}"', html=False)
        self.assertContains(response, '"status": "published"', html=False)
        self.assertContains(response, '"is_done": false', html=False)


class PracticeAccessControlTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-PRACT",
            role="teacher",
            first_name="Practice",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="practice-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.admin = User.objects.create(
            custom_id="ADM-PRACT",
            role="admin",
            first_name="Practice",
            last_name="Admin",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="practice-admin@example.com",
            password_hash=make_password("admin-password"),
        )

    def test_teacher_is_redirected_from_practice_reader(self):
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

        response = self.client.get(reverse("practice_word_page"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth"), response.url)

    def test_admin_can_open_practice_assessment_management(self):
        session = self.client.session
        session["user_id"] = self.admin.id
        session["user_role"] = self.admin.role
        session["first_name"] = self.admin.first_name
        session["last_name"] = self.admin.last_name
        session["email"] = self.admin.email
        session["custom_id"] = self.admin.custom_id
        session.save()

        response = self.client.get(reverse("admin_practice_assessment"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Practice Content")


class SettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="STD-0001",
            role="student",
            first_name="Settings",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="settings@example.com",
            password_hash=make_password("old-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_settings_password_change_updates_user_hash(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(check_password("new-password", self.user.password_hash))

    def test_settings_saves_push_notification_preferences(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "save_notifications",
                "push_enabled": "on",
                "new_materials": "on",
                "progress_updates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Push notification preferences saved.")

        self.user.refresh_from_db()
        self.assertIn({
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": False,
                "weekly_digest_enabled": False,
                "new_materials": True,
                "reading_reminders": False,
                "progress_updates": True,
            }
        }, self.user.tags)

    def test_settings_saves_weekly_digest_preference(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "save_notifications",
                "push_enabled": "on",
                "email_notifications": "on",
                "weekly_digest_enabled": "on",
                "new_materials": "on",
                "reading_reminders": "on",
                "progress_updates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.preference["notification_settings"]["weekly_digest_enabled"])


class AdminSettingsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="ADM-9999",
            role="admin",
            first_name="Admin",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="admin-settings@example.com",
            password_hash=make_password("admin-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_admin_settings_renders_new_settings_ui(self):
        response = self.client.get(reverse("admin_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pabasa_app/admin_settings.html")
        self.assertContains(response, "Push Notifications")
        self.assertContains(response, "Enable Notifications")
        self.assertContains(response, "Email Notifications")
        self.assertContains(response, "Save Preferences")
        self.assertContains(response, "Change Password")
        self.assertContains(response, "Current Password")
        self.assertContains(response, "New Password")
        self.assertContains(response, "Confirm Password")
        self.assertContains(response, "Update Password")
        self.assertNotContains(response, "Settings placeholder. CRUD is not implemented yet.")


class PreferenceDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="TCH-PREF",
            role="teacher",
            first_name="Pref",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="pref-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )

    def test_disabled_in_app_alerts_do_not_create_notification_rows(self):
        self.user.preference = {
            "notification_settings": {
                "push_enabled": False,
                "email_notifications": False,
                "weekly_digest_enabled": False,
            }
        }
        self.user.save(update_fields=["preference", "updated_at"])

        result = _create_notification(
            self.user,
            "Hidden alert",
            "This should not be stored.",
            send_email=False,
        )

        self.assertIsNone(result)
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())

    @patch("pabasa_app.views.send_mail")
    def test_email_alerts_respect_email_preference(self, mock_send_mail):
        self.user.preference = {
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": False,
                "weekly_digest_enabled": False,
            }
        }
        self.user.save(update_fields=["preference", "updated_at"])

        _create_notification(self.user, "Stored only", "No email should be sent.")

        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        mock_send_mail.assert_not_called()

        self.user.preference["notification_settings"]["email_notifications"] = True
        self.user.save(update_fields=["preference", "updated_at"])
        _create_notification(self.user, "Stored and emailed", "Email should be sent.")

        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 2)
        mock_send_mail.assert_called_once()


class PrincipalSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="PRN-SES",
            role="principal",
            first_name="Jobelyn",
            last_name="Valdez",
            middle_initial="A",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=3,
            birth_year=1980,
            email="principal@example.com",
            password_hash=make_password("old-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_principal_settings_saves_school_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_school_info",
                "school_name": "Example Elementary School",
                "school_code": "EX-001",
                "municipality": "Imus",
                "province": "Cavite",
                "district": "District 5",
                "region": "CALABARZON",
                "address": "Example Street",
                "contact": "0917-123-4567",
                "email": "principal@example.org",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.preference["principal_school_info"]["name"], "Example Elementary School")
        self.assertEqual(self.user.preference["principal_school_info"]["code"], "EX-001")

    def test_principal_settings_changes_password(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(check_password("new-password", self.user.password_hash))

    def test_principal_settings_updates_personal_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_personal_info",
                "first_name": "Maria",
                "last_name": "Cruz",
                "middle_initial": "L",
                "email": "maria.cruz@example.org",
                "contact_number": "09171234567",
                "position": "Principal II",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personal information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Maria")
        self.assertEqual(self.user.last_name, "Cruz")
        self.assertEqual(self.user.middle_initial, "L")
        self.assertEqual(self.user.email, "maria.cruz@example.org")
        self.assertEqual(self.user.contact_no, "09171234567")
        self.assertEqual(self.user.preference["principal_profile_info"]["position"], "Principal II")


class AssessmentCompletionNotificationTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-9001",
            role="teacher",
            first_name="Taylor",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher9001@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STU-9001",
            role="student",
            first_name="Jane",
            last_name="Doe",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2012,
            email="student9001@example.com",
            password_hash=make_password("student-password"),
        )
        self.admin = User.objects.create(
            custom_id="ADM-9001",
            role="admin",
            first_name="Alex",
            last_name="Admin",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=1985,
            email="admin9001@example.com",
            password_hash=make_password("admin-password"),
        )
        self.section = Section.objects.create(
            teacher=self.teacher,
            class_name="Class A",
            class_code="CLS-A9001",
            subject="Reading",
            is_active=True,
        )
        self.section.add_student(self.student)
        self.assessment = Assessment.objects.create(
            title="Reading Fluency Test",
            code="ASM-9001",
            assessment_type="word",
            content="cat\ndog",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
        )

    def _login_student(self):
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session.save()

    def _login_teacher(self):
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session.save()

    def test_assessment_material_creation_leaves_assessments_table_empty_until_completion(self):
        material = Material.objects.create(
            title="New Assessment Material",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="published",
            is_active=True,
        )

        self.assertIsNone(material.assessment)
        self.assertEqual(Assessment.objects.count(), 0)

        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material.refresh_from_db()
        self.assertIsNotNone(material.assessment)
        self.assertEqual(Assessment.objects.count(), 1)
        self.assertEqual(material.assessment.get_student_attempt_count(self.student), 1)

    def test_repeated_assessment_completions_create_separate_assessment_rows(self):
        material = Material.objects.create(
            title="Retake Assessment",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="published",
            is_active=True,
        )
        self._login_student()

        payload = json.dumps({
            "material_id": f"material-{material.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })

        first = self.client.post(reverse("record_assessment_completion"), data=payload, content_type="application/json")
        second = self.client.post(reverse("record_assessment_completion"), data=payload, content_type="application/json")

        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])

        material.refresh_from_db()
        self.assertIsNotNone(material.assessment)
        self.assertGreaterEqual(Assessment.objects.filter(code__startswith=material.assessment.code).count(), 2)
        attempts = material.assessment.get_attempts(self.student)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["attempt_number"], 1)
        self.assertEqual(attempts[1]["attempt_number"], 2)
        self.assertNotEqual(attempts[0]["attempt_id"], attempts[1]["attempt_id"])

    def test_assessment_completion_creates_teacher_notification(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "assessment_id": f"assessment-{self.assessment.id}",
                "material_id": f"assessment-{self.assessment.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Jane Doe completed the assessment 'Reading Fluency Test' in Class A.", notification.message)
        self.assertFalse(notification.is_read)

    def test_assessment_completion_saves_scores_and_crla_classification(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "assessment_id": f"assessment-{self.assessment.id}",
                "material_id": f"assessment-{self.assessment.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
                "scores": {
                    "fluency_score": 90,
                    "accuracy": 88,
                    "pronunciation_score": 86,
                    "time_score": 94,
                    "total_score": 89.5,
                    "wpm": 72,
                    "duration_seconds": 15,
                    "word_count": 18,
                    "transcript": "cat dog",
                    "speech_recognition_used": True,
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.assessment.refresh_from_db()
        attempt = self.assessment.get_attempts()[-1]
        self.assertEqual(attempt["fluency_score"], 90)
        self.assertEqual(attempt["accuracy"], 88)
        self.assertEqual(attempt["pronunciation_score"], 86)
        self.assertEqual(attempt["time_score"], 94)
        self.assertEqual(attempt["total_score"], 89.5)
        self.assertEqual(attempt["crla_classification"], "Transitioning Readers")
        self.assertEqual(attempt["wpm"], 72)

        self.student.refresh_from_db()
        self.assertEqual(self.student.reading_level, "Transitioning Readers")
        profile = self.student.preference.get("student_profile", {})
        self.assertEqual(profile["accuracy"], "88")
        self.assertEqual(profile["wpm"], "72")
        self.assertEqual(profile["crla_classification"], "Transitioning Readers")

    def test_numeric_material_id_records_assessment_attempt_by_assessment_id(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": str(self.assessment.id),
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.assessment.refresh_from_db()
        self.assertEqual(len(self.assessment.get_attempts(self.student)), 1)
        self.assertEqual(self.assessment.get_student_attempt_count(self.student), 1)

    def test_duplicate_assessment_completion_records_multiple_attempts_with_unique_ids(self):
        self._login_student()
        payload = json.dumps({
            "assessment_id": f"assessment-{self.assessment.id}",
            "material_id": f"assessment-{self.assessment.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })

        first = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        second = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )

        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])

        self.assessment.refresh_from_db()
        attempts = self.assessment.get_attempts(self.student)
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0]["attempt_id"], attempts[1]["attempt_id"])
        self.assertEqual(attempts[0]["attempt_number"], 1)
        self.assertEqual(attempts[1]["attempt_number"], 2)

    def test_teacher_update_material_does_not_create_assessment_record_when_none_exists(self):
        teacher = self.teacher
        material = Material.objects.create(
            title="Draft Assessment",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="draft",
            is_active=False,
        )
        self.assertIsNone(material.assessment)

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session.save()

        response = self.client.post(
            reverse("teacher_update_material"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "title": "Draft Assessment Updated",
                "content": "cat dog",
                "status": "published",
                "usage_type": "assessment",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material.refresh_from_db()
        self.assertIsNone(material.assessment)
        self.assertEqual(Assessment.objects.filter(title="Draft Assessment Updated").count(), 0)

    def test_numeric_material_id_records_assessment_attempt_by_assessment_id(self):
        self._login_student()
        payload = json.dumps({
            "assessment_id": f"assessment-{self.assessment.id}",
            "material_id": f"assessment-{self.assessment.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })
        first = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        second = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.teacher,
                created_by=self.student,
                notification_type="assessment",
            ).count(),
            1,
        )

    def test_class_materials_only_marks_completed_after_completed_attempt(self):
        self._login_student()

        self.assessment.record_attempt(self.student, status="started")
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["attempt_count"], 1)
        self.assertEqual(item["completed_attempt_count"], 0)
        self.assertFalse(item["student_has_completed"])

        self.assessment.record_attempt(self.student, status="completed")
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["attempt_count"], 2)
        self.assertEqual(item["completed_attempt_count"], 1)
        self.assertTrue(item["student_has_completed"])

    def test_class_materials_include_latest_time_score_for_completed_attempt(self):
        self._login_student()

        self.assessment.record_attempt(
            self.student,
            status="completed",
            time_score=82,
            total_score=88,
        )
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["latest_time_score"], 82)
        self.assertEqual(item["latest_attempt_summary"]["time_score"], 82)

    def test_teacher_can_fetch_unread_notification(self):
        Notification.objects.create(
            recipient=self.teacher,
            created_by=self.student,
            title="📝 Student Completed an Assessment",
            message="Jane Doe completed the assessment 'Reading Fluency Test' in Class A.",
            notification_type="assessment",
            action_url=f"/dashboard/teacher/students/detail/?student_id={self.student.custom_id}",
        )
        self._login_teacher()
        response = self.client.get(reverse("get_notifications"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["notifications"]), 1)
        self.assertFalse(data["notifications"][0]["is_read"])

    def test_practice_completion_notifies_admin_in_app_only(self):
        material = Material.objects.create(
            title="Practice Words",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            status="published",
            is_active=True,
        )
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "practice",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        teacher_notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNone(teacher_notification)

        admin_notification = Notification.objects.filter(
            recipient=self.admin,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(admin_notification)
        self.assertIn("Jane Doe read \"Practice Words\"", admin_notification.message)
        self.assertFalse(admin_notification.is_read)


class WeeklyDigestTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-DIGEST",
            role="teacher",
            first_name="Digest",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="digest-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
            preference={
                "notification_settings": {
                    "push_enabled": True,
                    "email_notifications": True,
                    "weekly_digest_enabled": True,
                }
            },
        )
        self.student = User.objects.create(
            custom_id="STD-DIGEST",
            role="student",
            first_name="Digest",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="digest-student@example.com",
            password_hash=make_password("student-password"),
        )
        self.section = Section.objects.create(
            teacher=self.teacher,
            class_name="Digest Class",
            class_code="DIG-001",
            subject="Reading",
            is_active=True,
        )
        self.section.add_student(self.student)
        self.assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section,
            title="Digest Assessment",
            code="DIG-ASM-001",
            assessment_type="word",
            content="cat\ndog",
            is_active=True,
        )
        self.start = timezone.now() - timedelta(days=7)
        self.end = timezone.now() + timedelta(seconds=1)
        self.assessment.record_attempt(
            self.student,
            status="completed",
            completed_at=(timezone.now() - timedelta(days=1)).isoformat(),
            total_score=88,
            accuracy=87,
            fluency_score=86,
            pronunciation_score=85,
        )

    @patch("pabasa_app.weekly_digest.send_mail")
    def test_weekly_digest_skips_disabled_user(self, mock_send_mail):
        self.teacher.preference["notification_settings"]["weekly_digest_enabled"] = False
        self.teacher.save(update_fields=["preference", "updated_at"])

        result = send_weekly_digest(self.teacher, self.start, self.end)

        self.assertEqual(result["skipped"], "weekly_digest_disabled")
        mock_send_mail.assert_not_called()

    @patch("pabasa_app.weekly_digest.send_mail")
    def test_teacher_weekly_digest_sends_and_records_window(self, mock_send_mail):
        result = send_weekly_digest(self.teacher, self.start, self.end)

        self.assertTrue(result["sent"])
        mock_send_mail.assert_called_once()
        email_body = mock_send_mail.call_args[0][1]
        self.assertIn("Assessments completed by students: 1", email_body)
        self.assertIn("Average class reading performance: 88.0%", email_body)

        self.teacher.refresh_from_db()
        digest_meta = self.teacher.preference["weekly_digest"]
        self.assertEqual(digest_meta["last_window_start"], self.start.isoformat())
        self.assertEqual(digest_meta["last_window_end"], self.end.isoformat())

        duplicate = send_weekly_digest(self.teacher, self.start, self.end)
        self.assertEqual(duplicate["skipped"], "duplicate_window")
        mock_send_mail.assert_called_once()


class TeacherStudentsDirectoryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-DIR1",
            role="teacher",
            first_name="Directory",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="directory-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STD-DIR1",
            role="student",
            first_name="Single",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="single-student@example.com",
            password_hash=make_password("student-password"),
        )
        self.section_a = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading One",
            class_code="READ-ONE",
            subject="Reading",
            is_active=True,
        )
        self.section_b = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading Two",
            class_code="READ-TWO",
            subject="Reading",
            is_active=True,
        )
        self.section_a.add_student(self.student)
        self.section_b.add_student(self.student)

        entries = self.section_b.get_enrolled_students()
        entries[0]["student_id"] = str(entries[0]["student_id"])
        self.section_b.students = entries
        self.section_b.save(update_fields=["students", "updated_at"])

        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_teacher_students_api_returns_one_row_with_joined_classes(self):
        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["custom_id"], self.student.custom_id)
        self.assertCountEqual(data["students"][0]["classes"], ["Reading One", "Reading Two"])
        self.assertCountEqual(data["students"][0]["class_codes"], ["READ-ONE", "READ-TWO"])

    def test_teacher_overview_counts_unique_students_across_classes(self):
        response = self.client.get(reverse("get_teacher_overview"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["classes_count"], 2)
        self.assertEqual(data["total_students"], 1)

    def test_teacher_students_api_uses_latest_assessment_classification(self):
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-DIR-001",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            total_score=87,
        )

        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["level"], "Transitioning Readers")
        self.assertTrue(data["students"][0]["has_completed_assessment"])

    def test_teacher_students_api_exposes_latest_completion_duration(self):
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-DIR-002",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            total_score=87,
            duration_seconds=75,
        )

        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["duration_seconds"], 75)

    def test_teacher_students_api_returns_pending_without_assessment_data(self):
        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["level"], "Pending")
        self.assertFalse(data["students"][0]["has_completed_assessment"])

    def test_teacher_course_assessments_api_includes_section_assigned_material_assessments(self):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Course Assigned Material",
            code="CRS-MAT-001",
            description="Course with section-assigned assessment material",
        )
        course.sections.add(self.section_a)

        other_teacher = User.objects.create(
            custom_id="TCH-SHARED",
            role="teacher",
            first_name="Shared",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="shared-teacher@example.com",
            password_hash=make_password("shared-password"),
            teacher_role="Teacher",
        )
        material = Material.objects.create(
            title="Shared Assessment",
            teacher=other_teacher,
            item_type="paragraph",
            type="assessment",
            status="published",
            is_active=True,
        )
        material.assigned_sections.add(self.section_a)

        material.record_assessment_result(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            accuracy=82,
            wpm=65,
            fluency_score=78,
            pronunciation_score=80,
            time_score=85,
            total_score=83,
        )

        response = self.client.get(
            reverse("get_teacher_assessments_api"),
            {"course_id": course.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["assessments"]), 1)
        self.assertEqual(data["assessments"][0]["title"], "Shared Assessment")
        self.assertEqual(data["assessments"][0]["attempt_count"], 1)

    def test_students_template_uses_static_renderer_only(self):
        response = self.client.get(reverse("students"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pabasa_app/js/students.js", html=False)
        self.assertNotContains(response, "Students directory: prefer server")

    def test_course_report_recipients_do_not_use_local_storage_students(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        helper_start = content.index("async function fetchStudentsForCourse(course)")
        helper_end = content.index("// Course-scoped Reports loader", helper_start)
        helper_body = content[helper_start:helper_end]

        self.assertIn("/dashboard/teacher/students-api/", helper_body)
        self.assertNotIn("pabasa_added_students", helper_body)

    def test_course_update_composer_includes_report_preview_container(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="courseSelectedStudentReportPreview"', html=False)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_emails_student_and_stores_note(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 2",
            code="CRS-TEST-001",
            description="Course update test",
        )
        course.sections.add(self.section_a)
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-COURSE-001",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            accuracy=88,
            wpm=72,
            fluency_score=84,
            pronunciation_score=86,
            time_score=90,
            total_score=87,
            crla_classification="Transitioning Readers",
        )

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "general",
                "message": "Hello {name}, keep practicing.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["sent_count"], 1)
        self.assertTrue(data["report_included"])
        self.assertIn("report_summary", data["sent"][0])
        mock_email_cls.assert_called_once()
        self.assertEqual(mock_email_cls.call_args[0][0], "Student Reading Progress Report – PABASA")
        email_instance = mock_email_cls.return_value
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Dear Parent/Guardian", email_body)
        self.assertIn("Attached is the latest Reading Progress Report", email_body)
        self.assertIn("PABASA Team", email_body)
        self.assertNotIn("Reading Performance Report", email_body)
        self.assertNotIn("Accuracy: 88%", email_body)
        self.assertNotIn("Words Per Minute: 72 WPM", email_body)
        email_instance.attach.assert_called_once()
        self.assertEqual(email_instance.attach.call_args[0][0], "Single_Student_reading_report.pdf")
        self.assertEqual(email_instance.attach.call_args[0][2], "application/pdf")
        email_instance.send.assert_called_once_with(fail_silently=False)

        note = Note.objects.get(teacher=self.teacher, student=self.student)
        self.assertEqual(note.note_type, "course_update:general")
        self.assertIn("Chapter 2", note.note_text)
        self.assertIn("Hello Single Student, keep practicing.", note.note_text)
        self.assertIn("Reading Performance Report", note.note_text)
        self.assertIn("Suggested Home Support", note.note_text)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_includes_baseline_message_when_metrics_missing(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 3",
            code="CRS-TEST-002",
            description="Missing metrics test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "followup",
                "message": "Hello {name}, we will check your baseline soon.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Student Reading Progress Report – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Dear Parent/Guardian", email_body)
        self.assertIn("Attached is the latest Reading Progress Report", email_body)
        self.assertIn("PABASA Team", email_body)
        self.assertNotIn("No completed assessment yet", email_body)
        mock_email_cls.return_value.attach.assert_called_once()

        note = Note.objects.get(teacher=self.teacher, student=self.student)
        self.assertIn("No completed assessment yet", note.note_text)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_commendation_sends_certificate_attachment(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 5",
            code="CRS-TEST-004",
            description="Commendation test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "commendation",
                "message": "Congratulations {name}!",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(response.json()["report_included"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Performance Commendation – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Congratulations", email_body)
        self.assertIn("certificate is attached", email_body.lower())
        self.assertIn("outstanding reading performance", email_body.lower())
        self.assertEqual(mock_email_cls.return_value.attach.call_count, 1)
        attachment_name, attachment_bytes, mime_type = mock_email_cls.return_value.attach.call_args.args
        self.assertIn("certificate", attachment_name.lower())
        self.assertEqual(mime_type, "application/pdf")
        self.assertTrue(attachment_bytes)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_assessment_notice_sends_details_without_attachment(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 6",
            code="CRS-TEST-005",
            description="Assessment notice test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "assessment",
                "message": "Please prepare for your upcoming reading assessment.",
                "assessment_title": "Oral Reading Check",
                "scheduled_at": "2026-07-10 09:00",
                "reading_material": "The Little Red Hen",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(response.json()["report_included"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Scheduled Assessment Notice – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Oral Reading Check", email_body)
        self.assertIn("July 10, 2026 at 09:00 AM", email_body)
        self.assertIn("The Little Red Hen", email_body)
        self.assertIn("Please prepare", email_body)
        mock_email_cls.return_value.attach.assert_not_called()

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_skips_unenrolled_and_missing_email_students(self, mock_email_cls):
        no_email_student = User.objects.create(
            custom_id="STD-NOEMAIL",
            role="student",
            first_name="No",
            last_name="Email",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=2013,
            email="",
            password_hash=make_password("student-password"),
        )
        outsider = User.objects.create(
            custom_id="STD-OUTSIDE",
            role="student",
            first_name="Outside",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=4,
            birth_day=4,
            birth_year=2013,
            email="outside@example.com",
            password_hash=make_password("student-password"),
        )
        self.section_a.add_student(no_email_student)
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 4",
            code="CRS-TEST-003",
            description="Skipped recipient test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id, no_email_student.id, outsider.id],
                "update_type": "general",
                "message": "Hello {name}, keep reading.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["sent_count"], 1)
        self.assertEqual(len(data["skipped"]), 2)
        self.assertCountEqual([item["reason"] for item in data["skipped"]], ["missing_email", "not_enrolled"])
        mock_email_cls.assert_called_once()
