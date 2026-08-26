from io import BytesIO

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook

from .models import Assessment, Material, Section, User
from .utils.crla_export import _part_1_reading_level, export_crla_excel


class CrlaExportResultTests(TestCase):
    def test_part_1_reading_level_uses_column_i_boundaries(self):
        expected = {
            0: "Full Refresher", 10: "Full Refresher",
            11: "Moderate Refresher", 16: "Moderate Refresher",
            17: "Light Refresher", 26: "Light Refresher",
            27: "Grade Ready", 30: "Grade Ready",
        }
        for total, level in expected.items():
            with self.subTest(total=total):
                self.assertEqual(_part_1_reading_level(total), level)
        self.assertIsNone(_part_1_reading_level(None))

    def make_user(self, custom_id, role, first_name, last_name, **extra):
        return User.objects.create(
            custom_id=custom_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
            middle_initial="",
            suffix="",
            sex=extra.pop("sex", "female"),
            birth_month=1,
            birth_day=1,
            birth_year=2018 if role == "student" else 1990,
            email=f"{custom_id.lower()}@example.com",
            password_hash=make_password("password"),
            **extra,
        )

    def test_export_uses_assigned_teacher_and_persisted_story_two_results(self):
        admin = self.make_user("CRLA-ADMIN", "admin", "PABASA", "Admin")
        teacher = self.make_user("CRLA-TEACHER", "teacher", "Maria", "Santos", school="Mabini School")
        student = self.make_user("CRLA-STUDENT", "student", "Lina", "Reyes", lrn="123456789012")
        section = Section.objects.create(
            class_code="G2-RIZAL", class_name="Grade 2 Rizal", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=admin, title="Official CRLA", code="CRLA-EXPORT-VALUES",
            assessment_type="paragraph", status="published", is_system_owned=True,
            system_assessment_key="eosy_crla_posttest",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=admin, title="Official CRLA",
            code="CRLA-EXPORT-MATERIAL", item_type="paragraph", type="assessment",
            assessment_kind="crla", is_system_owned=True, is_official_reading=True,
            content_json={"passages": [{"title": "Story One"}, {"title": "Story Two"}]},
        )
        student.preference = {
            "reading_assessment_state": {
                "student_end_assessment_state": {
                    "material_id": str(material.id), "stage": "completed", "branch": "sentences",
                    "task1_score": 8, "task2_sentences_score": 7, "part1_total_score": 25,
                    "selected_story": "Story Two", "total_words_read": 70,
                    "duration_seconds": 125, "wpm": 33.6, "story_read_percent": 70,
                    "correct_answers": 3, "learner_experience_rating": 4,
                    "classification": "Transitioning Reader",
                }
            }
        }
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="CRLA result", code="CRLA-EXPORT-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), duration_seconds=125, word_count=70, wpm=33.6,
            accuracy=70, correct_items=3,
        )

        workbook = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)
        sheet = workbook["G2 MT Reading Scoresheet"]

        self.assertEqual(sheet["C6"].value, "Maria Santos")
        self.assertEqual(sheet["F11"].value, 8)
        self.assertEqual(sheet["G11"].value, 10)
        self.assertEqual(sheet["H11"].value, 7)
        self.assertEqual(sheet["I11"].value, 25)
        self.assertEqual(sheet["J11"].value, "Light Refresher")
        self.assertEqual(sheet["K11"].value, 2)
        self.assertEqual(sheet["M11"].value, 70)
        self.assertEqual((sheet["N11"].value, sheet["O11"].value), (2, 5))
        self.assertEqual(sheet["P11"].value, 33.6)
        self.assertEqual(sheet["Q11"].value, 0.7)
        self.assertEqual(sheet["R11"].value, 3)
        self.assertEqual(sheet["S11"].value, 4)
        self.assertEqual(sheet["T11"].value, "Level 3")
        self.assertEqual(sheet["U11"].value, "Transitioning Reader")
        self.assertEqual(sheet["V11"].value, "Needs continued reading practice")

    def test_low_emerging_branch_leaves_part_two_cells_blank(self):
        teacher = self.make_user("CRLA-T2", "teacher", "Ana", "Cruz")
        student = self.make_user("CRLA-S2", "student", "Nilo", "Dela Cruz")
        section = Section.objects.create(
            class_code="G2-BONI", class_name="Grade 2 Bonifacio", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="CRLA Early Exit", code="CRLA-EARLY",
            assessment_type="word", status="published",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-EARLY-MAT",
            item_type="word", type="assessment", assessment_kind="crla",
        )
        student.preference = {"reading_assessment_state": {"student_end_assessment_state": {
            "material_id": str(material.id), "stage": "early_completed_words", "branch": "rhymes",
            "task1_score": 6, "task2_rhymes_score": 3, "part1_total_score": 9,
            "classification": "Low Emerging Reader",
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="early result", code="CRLA-EARLY-RESULT",
            assessment_type="word", status="published", attempt_status="completed",
            completed_at=timezone.now(), duration_seconds=20, word_count=6, wpm=18, accuracy=60,
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
        self.assertEqual((sheet["F11"].value, sheet["G11"].value), (6, 3))
        self.assertEqual(sheet["I11"].value, 9)
        self.assertEqual(sheet["J11"].value, "Full Refresher")
        for column in ("K", "M", "N", "O", "P", "Q", "R", "S", "T"):
            self.assertIsNone(sheet[f"{column}11"].value)
        self.assertEqual(sheet["U11"].value, "Low Emerging Reader")
        self.assertEqual(sheet["V11"].value, "Needs intensive reading intervention")
