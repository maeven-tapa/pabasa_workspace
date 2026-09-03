import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from .models import Enrollment, Material, School, Section, StoryResponseSubmission, User


class StoryResponseReviewTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Story Review School", code="STORY-REVIEW")
        self.teacher = User.objects.create(custom_id="T-STORY", role="teacher", first_name="T", last_name="Teacher", sex="female", birth_month=1, birth_day=1, birth_year=1990, email="teacher-story@example.com", password_hash="x")
        self.student = User.objects.create(custom_id="S-STORY", role="student", first_name="S", last_name="Student", sex="female", birth_month=1, birth_day=1, birth_year=2018, email="student-story@example.com", password_hash="x")
        self.section = Section.objects.create(school=self.school, class_code="STORY", class_name="Story", teacher=self.teacher, assessment_week_enabled=True)
        Enrollment.objects.create(student=self.student, section=self.section)
        self.story = Material.objects.create(teacher=self.teacher, section=self.section, title="The Story", item_type="paragraph", status="published", content_json={"activity_type": "story_reading", "storyTitle": "The Story", "storyText": "Once."})
        self.material = Material.objects.create(teacher=self.teacher, section=self.section, title="Tell me", item_type="paragraph", type="assessment", status="published", student_access=True, content_json={"activity_type": "story_response", "source_story_reading_material_id": self.story.id, "response_prompt": "What happened?"})
        self.material.assigned_sections.add(self.section)

    def login_as(self, user):
        session = self.client.session
        session.update({"user_id": user.id, "user_role": user.role, "email": user.email})
        session.save()

    def test_submission_review_and_grade_are_persisted(self):
        self.login_as(self.student)
        response = self.client.post(reverse("story_response_submit"), {"material_id": f"material-{self.material.id}", "response_text": "It happened.", "audio": SimpleUploadedFile("answer.webm", b"audio")})
        self.assertEqual(response.status_code, 200)
        submission = StoryResponseSubmission.objects.get(student=self.student, material=self.material)
        self.assertTrue(submission.audio_file)

        self.login_as(self.teacher)
        review = self.client.get(reverse("teacher_story_response_review"), {"material_id": self.material.id})
        self.assertEqual(review.json()["submissions"][0]["status"], "Pending Grade")
        self.assertEqual(review.json()["submissions"][0]["response_text"], "It happened.")
        grade = self.client.post(reverse("teacher_story_response_grade"), data=json.dumps({"submission_id": submission.id, "grade": 4}), content_type="application/json")
        self.assertEqual(grade.status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.grade, 4)
        self.assertEqual(submission.status, "graded")
        self.assertTrue(self.client.get(reverse("teacher_story_response_review"), {"material_id": self.material.id}).json()["submissions"][0]["grade_locked"])
        locked = self.client.post(reverse("teacher_story_response_grade"), data=json.dumps({"submission_id": submission.id, "grade": 5}), content_type="application/json")
        self.assertEqual(locked.status_code, 409)

        export = self.client.get(reverse("export_material_results"), {"material_id": self.material.id})
        self.assertEqual(export.status_code, 200)
        sheet = load_workbook(BytesIO(export.content), data_only=True).active
        self.assertEqual(sheet["G5"].value, "4")
        self.assertEqual(sheet["H5"].value, "80%")
        self.assertEqual(sheet["I5"].value, "Graded")

    def test_student_completion_payload_is_submission_backed_and_route_blocks_retake(self):
        self.login_as(self.student)
        first = self.client.post(reverse("story_response_submit"), {
            "material_id": f"material-{self.material.id}",
            "audio": SimpleUploadedFile("answer.webm", b"audio"),
        })
        self.assertEqual(first.status_code, 200)

        materials = self.client.get(reverse("get_class_materials"), {"section_id": self.section.id})
        self.assertEqual(materials.status_code, 200)
        story_item = next(item for item in materials.json()["materials"]["paragraph"] if item["raw_id"] == self.material.id)
        self.assertTrue(story_item["student_has_completed"])
        self.assertTrue(story_item["story_response_submitted"])
        self.assertIsNone(story_item["story_response_grade"])

        activity_page = self.client.get(reverse("story_response_page"), {"id": f"material-{self.material.id}"})
        self.assertEqual(activity_page.status_code, 302)
        duplicate = self.client.post(reverse("story_response_submit"), {
            "material_id": f"material-{self.material.id}",
            "audio": SimpleUploadedFile("answer-again.webm", b"audio"),
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_submission_accepts_csrf_protected_browser_request(self):
        self.login_as(self.student)
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session.update({"user_id": self.student.id, "user_role": self.student.role, "email": self.student.email})
        session.save()

        page = client.get(reverse("story_response_page"), {"id": f"material-{self.material.id}"})
        self.assertEqual(page.status_code, 200)
        csrf_token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("story_response_submit"),
            {
                "material_id": f"material-{self.material.id}",
                "response_text": "",
                "duration_seconds": "0",
                "audio": SimpleUploadedFile("answer.webm", b"audio"),
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(StoryResponseSubmission.objects.filter(student=self.student, material=self.material).exists())

    def test_unrelated_activity_is_not_story_response(self):
        self.login_as(self.teacher)
        self.assertNotEqual(self.material.content_json.get("activity_type"), "story_reading")
        self.assertEqual(self.client.get(reverse("teacher_story_response_review"), {"material_id": self.story.id}).status_code, 404)
