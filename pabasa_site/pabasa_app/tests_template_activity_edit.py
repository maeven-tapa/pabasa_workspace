import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .models import Material, Section, User


class TemplateActivityEditRegressionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-TEMPLATE-EDIT", role="teacher",
            first_name="Template", last_name="Editor", middle_initial="", suffix="",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="template-editor@example.com", password_hash="hashed-password",
            teacher_role="Teacher",
        )
        self.section = Section.objects.create(
            class_code="TEMPLATE-EDIT", class_name="Grade 2", header="Reading Class",
            description="", teacher=self.teacher, subject="English", is_active=True,
        )
        session = self.client.session
        session.update({
            "user_id": self.teacher.id, "user_role": "teacher",
            "email": self.teacher.email, "custom_id": self.teacher.custom_id,
        })
        session.save()

    def test_template_update_preserves_record_and_template_payload(self):
        material = Material.objects.create(
            teacher=self.teacher, section=self.section,
            title="Original Phrase Activity", item_type="sentence",
            content_text="old phrase", type="assessment", source_type="template",
            status="published", is_active=True, assigned_week="Week 1",
            assigned_weeks=["Week 1"], content_json={
                "template_title": "Phrase Reading Practice",
                "template_lesson": "Phrase Reading",
                "template_type": "Phrase Reading Practice",
                "template_source": "template",
                "language": "English",
                "items": [{"phrase": "old phrase"}],
            },
        )
        material.assigned_sections.add(self.section)
        original_count = Material.objects.count()
        updated_content = {
            "template_title": "Phrase Reading Practice",
            "template_lesson": "Phrase Reading",
            "template_type": "Phrase Reading Practice",
            "template_source": "template",
            "language": "Filipino",
            "weeks": ["Week 2"],
            "assigned_weeks": ["Week 2"],
            "items": [{"phrase": "ang masayang bata"}],
            "phraseReading": {
                "language": "Tagalog", "setKey": "tagalog-phrase-1",
                "selectedIndices": [0],
            },
        }

        response = self.client.post(
            reverse("teacher_update_material"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "title": "Updated Phrase Activity",
                "reading_type": "sentence",
                "content": json.dumps(updated_content),
                "status": "published",
                "usage_type": "assessment",
                "assigned_week": "Week 2",
                "assigned_weeks": ["Week 2"],
                "language": "Filipino",
                "source_type": "template",
                "template_title": "Phrase Reading Practice",
                "template_lesson": "Phrase Reading",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(Material.objects.count(), original_count)
        material.refresh_from_db()
        self.assertEqual(material.title, "Updated Phrase Activity")
        self.assertEqual(material.content_text, "ang masayang bata")
        self.assertEqual(material.content_json["items"], [{"phrase": "ang masayang bata"}])
        self.assertEqual(material.content_json["phraseReading"]["setKey"], "tagalog-phrase-1")
        self.assertEqual(material.content_json["template_source"], "template")
        self.assertEqual(material.assigned_weeks, ["Week 2"])
        self.assertEqual(material.section_id, self.section.id)
        self.assertTrue(material.assigned_sections.filter(id=self.section.id).exists())
        self.assertEqual(response.json()["material"]["raw_id"], material.id)

    def test_shared_template_builder_has_only_primary_save_action(self):
        template_path = Path(settings.BASE_DIR) / "pabasa_app" / "templates" / "pabasa_app" / "courses.html"
        source = template_path.read_text(encoding="utf-8")

        self.assertIn('id="templateSaveBtn"', source)
        self.assertNotIn("templateSaveAssignBtn", source)
        self.assertNotIn("Save &amp; Assign", source)
        self.assertNotIn("assignOnly", source)

