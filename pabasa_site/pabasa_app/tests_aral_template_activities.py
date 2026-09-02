import json
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_vocabulary_completion_is_server_scored_saved_and_idempotent(self):
        material = self.make_material(
            "word_meaning_match", reading_set_id="word_meaning_match-english-6",
            reading_set="Home and Family", items=[
                {"word": "home", "sentence": "Our home is safe.",
                 "choices": ["a place to live", "food", "a toy"], "answer_index": 0},
                {"word": "meal", "sentence": "We share a meal.",
                 "choices": ["a game", "food we eat", "a room"], "answer_index": 1},
            ],
        )
        self.login_student()
        url = reverse(
            "aral_template_activity_complete",
            kwargs={"activity_slug": "word-meaning-match"},
        )
        payload = {
            "material_id": material.id,
            "duration_seconds": 41,
            "answers": [
                {"item_index": 0, "first_choice_index": 2,
                 "final_choice_index": 0, "attempts": 2},
                {"item_index": 1, "first_choice_index": 1,
                 "final_choice_index": 1, "attempts": 1},
            ],
        }

        response = self.client.post(url, json.dumps(payload), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        result_payload = response.json()["result"]
        self.assertTrue(result_payload["completed"])
        self.assertEqual(result_payload["correct_items"], 1)
        self.assertEqual(result_payload["items_completed"], 2)
        self.assertEqual(result_payload["accuracy"], 50.0)
        self.assertFalse(result_payload["passed"])
        result = material.assessment_results.get(student=self.student)
        self.assertEqual(result.attempt_status, "completed")
        self.assertEqual(result.duration_seconds, 41)
        self.assertEqual(result.word_count, 2)
        self.assertEqual(result.correct_items, 1)
        self.assertTrue(result.remarks.startswith("WORD_MEANING_MATCH_RESULT:"))

        duplicate = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["already_completed"])
        self.assertEqual(material.assessment_results.filter(student=self.student).count(), 1)

        reopened = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "word-meaning-match"}),
            {"id": material.id},
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertTrue(reopened.context["word_meaning_activity"]["completion"]["completed"])

    def test_vocabulary_completion_rejects_incomplete_or_unmastered_answers(self):
        material = self.make_material(
            "word_meaning_match", reading_set_id="word_meaning_match-english-6",
            items=[
                {"word": "home", "choices": ["house", "food"], "answer_index": 0},
                {"word": "meal", "choices": ["room", "food"], "answer_index": 1},
            ],
        )
        self.login_student()
        url = reverse(
            "aral_template_activity_complete",
            kwargs={"activity_slug": "word-meaning-match"},
        )

        incomplete = self.client.post(url, json.dumps({
            "material_id": material.id,
            "answers": [{"item_index": 0, "first_choice_index": 0,
                         "final_choice_index": 0, "attempts": 1}],
        }), content_type="application/json")
        self.assertEqual(incomplete.status_code, 400)

        unmastered = self.client.post(url, json.dumps({
            "material_id": material.id,
            "answers": [
                {"item_index": 0, "first_choice_index": 0,
                 "final_choice_index": 0, "attempts": 1},
                {"item_index": 1, "first_choice_index": 0,
                 "final_choice_index": 0, "attempts": 1},
            ],
        }), content_type="application/json")
        self.assertEqual(unmastered.status_code, 400)
        self.assertFalse(material.assessment_results.filter(student=self.student).exists())

    @patch("pabasa_app.views.transcribe_audio_bytes_with_model")
    def test_fluency_completion_calculates_cwpm_and_persists_transcript(self, transcribe):
        passage = "Maaga akong gumising. Handa na ako sa paaralan."
        transcribe.return_value = (passage, "chirp_3", "")
        material = self.make_material(
            "fluency_reading", language="Filipino",
            reading_set_id="fluency_reading-filipino-1",
            reading_set="Ang Aking Umaga", passage=passage,
            phrases=["Maaga akong gumising.", "Handa na ako sa paaralan."],
        )
        self.login_student()
        url = reverse(
            "aral_template_activity_complete",
            kwargs={"activity_slug": "fluency-reading"},
        )

        response = self.client.post(url, {
            "material_id": str(material.id),
            "duration_seconds": "30",
            "audio": SimpleUploadedFile("reading.webm", b"recorded-audio", "audio/webm"),
        })

        self.assertEqual(response.status_code, 200)
        result_payload = response.json()["result"]
        self.assertTrue(result_payload["completed"])
        self.assertEqual(result_payload["accuracy"], 100.0)
        self.assertEqual(result_payload["wpm"], result_payload["correct_items"] * 2)
        result = material.assessment_results.get(student=self.student)
        self.assertEqual(result.transcript, passage)
        self.assertEqual(result.attempt_status, "completed")
        self.assertEqual(result.duration_seconds, 30)
        self.assertTrue(result.mic_used)
        self.assertTrue(result.speech_recognition_used)
        self.assertTrue(result.remarks.startswith("FLUENCY_READING_RESULT:"))
        self.assertEqual(material.assessment_results.filter(student=self.student).count(), 1)

        duplicate = self.client.post(url, {"material_id": str(material.id)})
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["already_completed"])
        self.assertEqual(material.assessment_results.filter(student=self.student).count(), 1)
        transcribe.assert_called_once()

    @patch("pabasa_app.views.transcribe_audio_bytes_with_model")
    def test_fluency_no_speech_does_not_create_false_completion(self, transcribe):
        transcribe.return_value = ("", "chirp_3", "")
        material = self.make_material(
            "fluency_reading", language="Filipino",
            reading_set_id="fluency_reading-filipino-1",
            passage="Ako ay masayang nagbabasa.",
        )
        self.login_student()

        response = self.client.post(
            reverse("aral_template_activity_complete", kwargs={"activity_slug": "fluency-reading"}),
            {"material_id": str(material.id), "duration_seconds": "12",
             "audio": SimpleUploadedFile("reading.webm", b"silence", "audio/webm")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(material.assessment_results.filter(student=self.student).exists())

    @patch("pabasa_app.views.transcribe_audio_bytes_with_model")
    def test_fluency_api_rejects_wrong_slug_and_crla_without_transcribing(self, transcribe):
        material = self.make_material(
            "fluency_reading", passage="I read every day.",
            reading_set_id="fluency_reading-english-1",
        )
        self.login_student()
        wrong_slug = self.client.post(
            reverse("aral_template_activity_complete", kwargs={"activity_slug": "word-meaning-match"}),
            json.dumps({"material_id": material.id, "answers": []}),
            content_type="application/json",
        )
        self.assertEqual(wrong_slug.status_code, 404)

        material.assessment_kind = "crla"
        material.save(update_fields=["assessment_kind"])
        crla = self.client.post(
            reverse("aral_template_activity_complete", kwargs={"activity_slug": "fluency-reading"}),
            {"material_id": str(material.id), "duration_seconds": "10",
             "audio": SimpleUploadedFile("reading.webm", b"audio", "audio/webm")},
        )
        self.assertEqual(crla.status_code, 404)
        transcribe.assert_not_called()

    def test_dedicated_templates_use_server_audio_and_fluency_recorder(self):
        vocabulary = self.make_material(
            "word_meaning_match", reading_set_id="word_meaning_match-english-6",
            items=[{"word": "home", "choices": ["house", "food"], "answer_index": 0}],
        )
        fluency = self.make_material(
            "fluency_reading", reading_set_id="fluency_reading-english-1",
            passage="I read every day.",
        )
        self.login_student()

        vocabulary_page = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "word-meaning-match"}),
            {"id": vocabulary.id},
        )
        fluency_page = self.client.get(
            reverse("aral_template_activity_page", kwargs={"activity_slug": "fluency-reading"}),
            {"id": fluency.id},
        )

        self.assertEqual(vocabulary_page.status_code, 200)
        self.assertContains(vocabulary_page, "data.tts_url")
        self.assertContains(vocabulary_page, "data.completion_url")
        self.assertNotContains(vocabulary_page, "speechSynthesis")
        self.assertEqual(fluency_page.status_code, 200)
        self.assertContains(fluency_page, "MediaRecorder")
        self.assertContains(fluency_page, "data.tts_url")
        self.assertContains(fluency_page, "data.completion_url")
        self.assertNotContains(fluency_page, "speechSynthesis")
