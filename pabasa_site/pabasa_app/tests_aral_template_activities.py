import json
import uuid

from django.test import TestCase
from django.urls import reverse

from .models import Material, School, Section, User


class DedicatedAralTemplateActivityTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        self.school = School.objects.create(name=f"ARAL School {suffix}", code=f"ARAL-{suffix}")
        self.teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="Reader",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1,
            birth_year=1990, email=f"teacher-{suffix}@example.com", password_hash="hashed",
            teacher_role="Teacher", school_record=self.school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Grade", last_name="Two",
            middle_initial="", suffix="", sex="male", birth_month=1, birth_day=1,
            birth_year=2018, email=f"student-{suffix}@example.com", password_hash="hashed",
            school_record=self.school,
        )
        self.section = Section.objects.create(
            school=self.school, class_code=f"CLASS-{suffix}", class_name="Grade 2",
            header="Reading", description="", teacher=self.teacher, subject="English",
            is_active=True,
        )
        self.section.add_student(self.student)

    def login_student(self):
        session = self.client.session
        session.update({
            "user_id": self.student.id, "user_role": "student",
            "email": self.student.email, "custom_id": self.student.custom_id,
        })
        session.save()

    def login_teacher(self):
        session = self.client.session
        session.update({
            "user_id": self.teacher.id, "user_role": "teacher",
            "email": self.teacher.email, "custom_id": self.teacher.custom_id,
        })
        session.save()

    def make_material(self, activity_key, **content):
        material = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Teacher Editable Title",
            item_type="word" if activity_key == "word_meaning_match" else "paragraph",
            content_text="ready-to-use content", type="assessment", source_type="template",
            assessment_kind="regular", status="published", is_active=True, student_access=True,
            assigned_week=4, assigned_weeks=[4], language=content.get("language", "English"),
            content_json={"activity_key": activity_key, "language": "English", **content},
        )
        material.assigned_sections.add(self.section)
        return material

    def test_vocabulary_page_receives_object_payload_and_uses_dedicated_template(self):
        material = self.make_material(
            "word_meaning_match", reading_set="School Day",
            instructions="Read the context clue.",
            items=[{"word": "lesson", "sentence": "We finished our lesson.",
                    "choices": ["a learning activity", "a snack", "a toy"], "answer_index": 0}],
        )
        self.login_student()

        response = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "word-meaning-match"}),
            {"id": material.id, "section_id": self.section.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["word_meaning_activity"]["title"], "Teacher Editable Title")
        self.assertEqual(response.context["word_meaning_activity"]["assigned_week"], 4)
        self.assertContains(response, "Read the context clue.")
        self.assertContains(response, "word-meaning-activity-data")
        self.assertNotContains(response, "/reading_ui/")
        self.assertNotContains(response, "What is PABASA")

    def test_fluency_route_is_selected_by_slug_not_editable_title_or_item_type(self):
        material = self.make_material(
            "fluency_reading", language="Filipino", reading_set="Ang Aking Umaga",
            passage="Maaga akong gumising. Handa na ako sa paaralan.",
            phrases=["Maaga akong gumising.", "Handa na ako sa paaralan."],
        )
        material.title = "Any teacher title"
        material.item_type = "word"
        material.save(update_fields=["title", "item_type"])
        self.login_student()

        correct = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "fluency-reading"}),
            {"id": material.id},
        )
        wrong = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "word-meaning-match"}),
            {"id": material.id},
        )

        self.assertEqual(correct.status_code, 200)
        self.assertEqual(correct.context["fluency_activity"]["passage"], "Maaga akong gumising. Handa na ako sa paaralan.")
        self.assertRedirects(wrong, reverse("assessment"), fetch_redirect_response=False)

    def test_crla_material_cannot_enter_dedicated_aral_route(self):
        material = self.make_material("word_meaning_match")
        material.assessment_kind = "crla"
        material.save(update_fields=["assessment_kind"])
        self.login_student()

        response = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "word-meaning-match"}),
            {"id": material.id},
        )

        self.assertRedirects(response, reverse("assessment"), fetch_redirect_response=False)

    def test_update_keeps_primary_week_in_sync_with_assigned_weeks(self):
        material = self.make_material(
            "word_meaning_match", reading_set_id="word_meaning_match-english-6",
            reading_set="Home and Family", items=[{
                "word": "home", "sentence": "Our home is safe.",
                "choices": ["a place to live", "food", "a toy"], "answer_index": 0,
            }],
        )
        self.login_teacher()
        updated_content = {**material.content_json, "assigned_weeks": [7]}

        response = self.client.post(
            reverse("teacher_update_material"),
            data=json.dumps({
                "material_id": material.id, "title": material.title, "reading_type": "word",
                "content": json.dumps(updated_content), "usage_type": "assessment",
                "source_type": "template", "template_title": "Word Meaning Match",
                "template_lesson": "Vocabulary Development", "language": "English",
                "assigned_weeks": [7],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.assigned_week, 7)
        self.assertEqual(material.assigned_weeks, [7])
        self.assertEqual(material.content_json["assigned_weeks"], [7])

    def test_create_saves_week_and_rejects_opposite_language_set(self):
        self.login_teacher()
        content = {
            "activity_key": "word_meaning_match", "activity_type": "word_meaning_match",
            "template_title": "Word Meaning Match", "template_lesson": "Vocabulary Development",
            "language": "English", "reading_set_id": "word_meaning_match-english-6",
            "reading_set": "Home and Family", "instructions": "Read and choose.",
            "items": [{"word": "home", "sentence": "Our home is safe.",
                       "choices": ["a place to live", "food", "a toy"], "answer_index": 0}],
        }
        payload = {
            "title": "My Vocabulary Activity", "reading_type": "word",
            "content": json.dumps(content), "status": "published", "usage_type": "assessment",
            "section_id": self.section.id, "assigned_week": "Week 3", "assigned_weeks": ["Week 3"],
            "language": "English", "assessment_kind": "regular", "source_type": "template",
            "template_title": "Word Meaning Match", "template_lesson": "Vocabulary Development",
        }

        created = self.client.post(
            reverse("add_reading_material"), data=json.dumps(payload), content_type="application/json",
        )

        self.assertEqual(created.status_code, 200)
        material = Material.objects.get(title="My Vocabulary Activity")
        self.assertEqual(material.assigned_week, 3)
        self.assertEqual(material.assigned_weeks, [3])
        self.assertEqual(material.content_json["activity_key"], "word_meaning_match")

        mixed_content = {**content, "language": "Filipino"}
        rejected = self.client.post(
            reverse("add_reading_material"),
            data=json.dumps({**payload, "title": "Mixed Language", "language": "Filipino",
                             "content": json.dumps(mixed_content)}),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(Material.objects.filter(title="Mixed Language").exists())
