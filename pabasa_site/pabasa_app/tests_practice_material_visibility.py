from django.test import TestCase
from .models import Material, School, Section, User
from .views import _save_admin_practice_material, _systemwide_practice_queryset


class PracticeMaterialVisibilityTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Practice A", code="P-A")
        self.school_b = School.objects.create(name="Practice B", code="P-B")
        self.teacher_a = User.objects.create(custom_id="PT-A", role="teacher", first_name="A", last_name="Teacher", sex="female", birth_month=1, birth_day=1, birth_year=1990, email="practice-a@example.com", password_hash="x", school_record=self.school_a)
        self.teacher_b = User.objects.create(custom_id="PT-B", role="teacher", first_name="B", last_name="Teacher", sex="female", birth_month=1, birth_day=1, birth_year=1990, email="practice-b@example.com", password_hash="x", school_record=self.school_b)
        self.section_a = Section.objects.create(school=self.school_a, class_code="PA-001", class_name="A", teacher=self.teacher_a, subject="Reading")
        self.system = Material.objects.create(title="System Practice", type="practice", source_type="shared", is_system_owned=True, status="published", is_active=True, difficulty_level="easy", language="English", content_json={"mode": "free", "difficulty": "easy", "level": "level_1", "items": ["a"]})
        self.orphan = Material.objects.create(title="Orphan Practice", type="practice", source_type="personal", is_system_owned=False, status="published", is_active=True, difficulty_level="easy", language="English", content_json={"mode": "free", "difficulty": "easy", "level": "level_1", "items": ["b"]})
        self.section_material = Material.objects.create(title="Section Practice", type="practice", teacher=self.teacher_a, section=self.section_a, source_type="personal", status="published", is_active=True, difficulty_level="easy", language="English")

    def test_only_explicit_system_practice_is_global(self):
        ids = set(_systemwide_practice_queryset().values_list("id", flat=True))
        self.assertIn(self.system.id, ids)
        self.assertNotIn(self.orphan.id, ids)
        self.assertNotIn(self.section_material.id, ids)

    def test_system_rule_is_school_independent_but_orphan_is_not(self):
        self.assertEqual(_systemwide_practice_queryset().count(), 1)

    def test_admin_saved_practice_is_explicitly_system_wide(self):
        class FormStub:
            cleaned_data = {"mode": "free", "difficulty_level": "easy", "level": "level_2", "language": "English", "status": "published", "content_text": "cat"}
            def practice_items(self):
                return ["cat"]
        material = _save_admin_practice_material(FormStub())
        self.assertTrue(material.is_system_owned)
        self.assertEqual(material.source_type, "shared")
        self.assertIsNone(material.teacher_id)
        self.assertIn(material.id, _systemwide_practice_queryset().values_list("id", flat=True))
