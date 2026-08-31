import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Material
from .sound_detective import catalog, validate_configuration


class SoundDetectiveCatalogTests(SimpleTestCase):
    def test_languages_sets_and_example_metadata(self):
        bank = catalog()
        self.assertEqual(len(bank["English"]["sets"]), 10)
        self.assertEqual(len(bank["Filipino"]["sets"]), 5)
        english_m = bank["English"]["sets"][0]
        monkey = next(item for item in english_m["items"] if item["word"] == "monkey")
        self.assertEqual((english_m["sound"], monkey["position"]), ("/m/", "Beginning"))

    def test_validation_rejects_cross_set_items(self):
        bank = catalog()
        wrong_id = bank["English"]["sets"][1]["items"][0]["id"]
        with self.assertRaisesMessage(ValueError, "belong to the selected sound set"):
            validate_configuration({"language": "English", "sound_set": "set_1", "selected_word_ids": [wrong_id]})

    def test_validation_returns_authoritative_items(self):
        selected = [item["id"] for item in catalog()["Filipino"]["sets"][4]["items"]]
        result = validate_configuration({"language": "Filipino", "sound_set": "set_5", "selected_word_ids": selected, "number_of_questions": 4})
        self.assertEqual(result["target_sound"], "/k/")
        self.assertEqual(len(result["items"]), 6)
        self.assertTrue(all("/filipino/Set_5/" in item["image_url"] for item in result["items"]))


class SoundDetectivePageTests(TestCase):
    def test_saved_configuration_reopens_in_student_component(self):
        bank_set = catalog()["English"]["sets"][0]
        content = validate_configuration({"language": "English", "sound_set": "set_1", "selected_word_ids": [item["id"] for item in bank_set["items"]], "number_of_questions": 6})
        content.update({"template_title": "Sound Detective", "template_lesson": "Phonological Awareness"})
        material = Material.objects.create(title="My Sound Detective", item_type="word", type="assessment", source_type="template", content_json=content)
        response = self.client.get(reverse("sound_detective_page"), {"id": f"material-{material.id}"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["sound_detective_material_json"])
        self.assertEqual(payload["title"], "My Sound Detective")
        self.assertEqual(payload["items"][1]["position"], "Beginning")
