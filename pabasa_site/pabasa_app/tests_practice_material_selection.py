from types import SimpleNamespace

from django.test import SimpleTestCase

from .views import _serialize_student_practice_material


class PracticeMaterialSelectionTests(SimpleTestCase):
    def test_serialized_material_includes_mode_difficulty_and_level(self):
        material = SimpleNamespace(
            id=7,
            title="Free Easy Level 1",
            difficulty_level="easy",
            item_type="word",
            status="published",
            content_text="hello world",
            content_json={"mode": "free", "difficulty": "easy", "level": "level_1"},
            created_at=None,
        )

        serialized = _serialize_student_practice_material(material)

        self.assertEqual(serialized["mode"], "free")
        self.assertEqual(serialized["difficulty"], "easy")
        self.assertEqual(serialized["level"], "level_1")
