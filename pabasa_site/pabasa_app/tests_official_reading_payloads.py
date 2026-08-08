from types import SimpleNamespace

from django.test import SimpleTestCase

from pabasa_app.views import _official_reading_item_sections


class OfficialReadingPayloadTests(SimpleTestCase):
    def test_parses_pre_post_material_items_from_content_json_payload(self):
        material = SimpleNamespace(
            title="Beginning of School Year Reading Assessment",
            code="PRE-001",
            language="Filipino",
            item_type="paragraph",
            content_text="",
            content_json={
                "assessment_key": "bosy_crla_pretest",
                "items": [
                    {"type": "word", "text": "Binti"},
                    {"type": "sentence", "text": "Naglalaba si Tatay sa palanggana."},
                    {"type": "paragraph", "text": "Ang pagong at ang kuneho.", "title": "Ang Pagong at ang Kuneho"},
                ],
            },
        )

        sections = _official_reading_item_sections(material)

        self.assertEqual(sections["words"], ["Binti"])
        self.assertEqual(sections["sentences"], ["Naglalaba si Tatay sa palanggana."])
        self.assertEqual(sections["passages"][0]["title"], "Ang Pagong at ang Kuneho")
        self.assertEqual(sections["passages"][0]["content"], "Ang pagong at ang kuneho.")
        self.assertEqual(sections["items"], ["Binti", "Naglalaba si Tatay sa palanggana.", "Ang pagong at ang kuneho."])
