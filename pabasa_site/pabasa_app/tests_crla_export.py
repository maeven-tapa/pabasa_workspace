from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
import uuid

from .models import Assessment, Enrollment, Material, School, Section, StoryReadingProgress, User
from .scoring import build_assessment_score_payload, crla_reading_profile, crla_sentence_score
from .utils.crla_export import (
    _part_1_reading_level,
    _row_formulas,
    _story_number,
    convert_crla_workbook_to_pdf,
    export_crla_excel,
)
from .utils.crla_results import latest_completed_official_crla_results


def test_section_create(**kwargs):
    school = kwargs.pop("school", None)
    if school is None:
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f"Fixture School {suffix}", code=f"FIXTURE-{suffix}")
    return Section.objects.create(school=school, **kwargs)


class CrlaExportResultTests(TestCase):
    def test_pdf_conversion_renders_every_template_sheet_in_order(self):
        source = BytesIO((Path(settings.BASE_DIR) / "templates" / "CRLA3_Grade2TagalogScoresheet_v3.xlsx").read_bytes())
        source.name = "complete.xlsx"
        expected_sheets = [
            "G2 MT Reading Scoresheet",
            "G2 FIL Reading Scoresheet",
            "Class Record",
            "Class Summary",
            "Scoring Reference",
            "List",
        ]

        def render_with_fake_libreoffice(command, **kwargs):
            rendered_workbook = load_workbook(command[-1], data_only=False)
            self.assertEqual(rendered_workbook.sheetnames, expected_sheets)
            self.assertTrue(all(sheet.sheet_state == "visible" for sheet in rendered_workbook.worksheets))
            for sheet in rendered_workbook.worksheets:
                self.assertEqual(sheet.page_setup.orientation, sheet.ORIENTATION_LANDSCAPE)
                self.assertEqual(sheet.page_setup.fitToWidth, 1)
                self.assertEqual(sheet.page_setup.fitToHeight, 0)
                self.assertTrue(sheet.sheet_properties.pageSetUpPr.fitToPage)
            self.assertEqual(rendered_workbook["G2 MT Reading Scoresheet"].page_setup.paperSize, 8)
            self.assertEqual(rendered_workbook["Class Record"].page_setup.paperSize, 8)
            self.assertEqual(rendered_workbook["Scoring Reference"].page_setup.paperSize, 9)
            output_dir = Path(command[command.index("--outdir") + 1])
            (output_dir / "complete.pdf").write_bytes(b"%PDF-1.4\ncomplete workbook\n")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("pabasa_app.utils.crla_export._libreoffice_executable", return_value="soffice"), patch(
            "pabasa_app.utils.crla_export.subprocess.run", side_effect=render_with_fake_libreoffice
        ):
            pdf = convert_crla_workbook_to_pdf(source)

        self.assertEqual(pdf.name, "complete.pdf")
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))

    def test_reading_profile_uses_comprehension_priority_for_cross_band_results(self):
        cases = (
            # A Part 1-only completion is Low Emerging.
            (10, None, None, None, "Low Emerging Reader"),
            # Part 2 classification is determined by comprehension when bands differ.
            (11, 1, 76, 0, "High Emerging Reader"),
            (11, 1, 24, 5, "Reading At Grade Level"),
            (11, 2, 49, 4, "Transitioning Reader"),
            (11, 1, 26, 1, "Developing Reader"),
            (11, 1, 51, 3, "Transitioning Reader"),
            (11, 1, 76, 5, "Reading At Grade Level"),
        )
        for part1, story, percentage, answers, expected in cases:
            with self.subTest(part1=part1, percentage=percentage, answers=answers):
                self.assertEqual(
                    crla_reading_profile(part1, story, percentage, answers), expected,
                )
        self.assertIsNone(crla_reading_profile(11, None, 80, 5))
        self.assertIsNone(crla_reading_profile(11, 1, None, 5))
        self.assertIsNone(crla_reading_profile(11, 1, 80, None))

    def test_grade_2_part_2_final_profile_89_percent_and_five_answers(self):
        """A valid Story 2 result must not inherit the Part 1 level."""
        self.assertEqual(
            crla_reading_profile(19, 2, 89, 5),
            "Reading At Grade Level",
        )

    def test_grade_2_part_2_final_profile_boundaries(self):
        cases = (
            (75, 5, "Transitioning Reader"),
            (76, 5, "Reading At Grade Level"),
            (100, 5, "Reading At Grade Level"),
            (89, 4, "Transitioning Reader"),
            (89, 5, "Reading At Grade Level"),
            (89, 6, "Reading At Grade Level"),
        )
        for accuracy, answers, expected in cases:
            with self.subTest(accuracy=accuracy, answers=answers):
                self.assertEqual(
                    crla_reading_profile(19, 2, accuracy, answers), expected,
                )

    def test_canonical_profile_is_persisted_and_selected_for_teacher_views(self):
        teacher = self.make_user("CRLA-CANON-T", "teacher", "Mia", "Lopez")
        student = self.make_user("CRLA-CANON-S", "student", "Asd", "Basco")
        section = test_section_create(
            class_code="G2-CANON", class_name="Grade 2 Canonical", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="Official CRLA", code="CRLA-CANON-ROOT",
            assessment_type="paragraph", status="published", is_system_owned=True,
            system_assessment_key="bosy_crla_pretest",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-CANON-MAT",
            item_type="paragraph", type="assessment", assessment_kind="crla", is_official_reading=True,
        )
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "crla_score_data": {
                "task1_score": 7, "task2_type": "Task 2H / Sentences", "sentences_read": 4,
                "story_number": 2, "story_total_words": 95, "words_read": 47,
                "miscues": 48, "duration_seconds": 590, "comprehension_correct": 4,
            },
        })
        root.record_attempt(student, material=material, status="completed", **payload)

        persisted = Assessment.objects.get(source_assessment=root, student=student)
        self.assertEqual(persisted.crla_classification, "Transitioning Reader")
        self.assertEqual(persisted.crla_score_data["crla_classification"], "Transitioning Reader")
        self.assertEqual(latest_completed_official_crla_results([student.id])[student.id].pk, persisted.pk)

    def test_completion_payload_persists_column_u_profile_not_client_label(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "classification": "High Emerging Reader",  # must not override Column U
            "crla_score_data": {
                "task1_score": 8,
                "task2_type": "Task 2H / Sentences",
                "sentences_read": 4,
                "story_number": 1,
                "story_total_words": 100,
                "words_read": 76,
                "miscues": 24,
                "duration_seconds": 60,
                "comprehension_correct": 5,
            },
        })
        self.assertEqual(payload["crla_classification"], "Reading At Grade Level")
        self.assertEqual(payload["crla_score_data"]["crla_classification"], "Reading At Grade Level")

    def test_server_derived_passage_percentage_overrides_browser_percentage_for_classification(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "crla_score_data": {
                "task1_score": 7, "task2_type": "Task 2H / Sentences", "sentences_read": 4,
                "story_number": 2, "story_total_words": 100, "words_read": 49,
                "story_read_percent": 90, "comprehension_correct": 4,
            },
        })
        self.assertEqual(payload["crla_classification"], "Transitioning Reader")
        self.assertEqual(payload["crla_score_data"]["passage_accuracy_percent"], 49)
        self.assertEqual(payload["crla_score_data"]["submitted_story_read_percent"], 90)

    def test_sentence_score_uses_official_four_sentence_table(self):
        self.assertEqual(
            [crla_sentence_score(count) for count in range(5)],
            [0, 2, 5, 7, 10],
        )

    def test_sentence_completion_score_is_independent_of_miscue_count(self):
        cases = (
            (4, 0, 10), (4, 3, 10),
            (3, 0, 7), (3, 5, 7),
            (2, 2, 5), (1, 4, 2), (0, 0, 0),
        )
        for completed_sentences, miscues, expected_score in cases:
            with self.subTest(completed_sentences=completed_sentences, miscues=miscues):
                payload = build_assessment_score_payload({
                    "assessment_type": "sentence",
                    "crla_score_data": {
                        "task1_score": 8,
                        "task2_type": "Task 2H / Sentences",
                        "sentences_read": completed_sentences,
                        "miscues": miscues,
                    },
                })
                self.assertEqual(payload["crla_score_data"]["task2_score"], expected_score)

    def test_sentence_miscues_do_not_change_completed_sentence_score_or_payload(self):
        payload = build_assessment_score_payload({
            "assessment_type": "sentence",
            # These remain word-level evidence only; four completed sentences
            # still earn the Task 2H maximum.
            "incorrect_words": 3,
            "crla_score_data": {
                "task1_score": 8,
                "task2_type": "Task 2H / Sentences",
                "sentences_read": 4,
                "miscues": 3,
            },
        })
        self.assertEqual(payload["crla_score_data"]["sentences_read"], 4)
        self.assertEqual(payload["crla_score_data"]["task2_score"], 10)
        self.assertEqual(payload["crla_score_data"]["part1_total_score"], 18)
        self.assertEqual(payload["final_score"], 18)

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

    def test_generated_formula_logic_matches_official_crla_ranges(self):
        cases = (
            (5, 4, None, 9, "Full Refresher"),
            (6, 5, None, 11, "Moderate Refresher"),
            (10, None, 4, 14, "Moderate Refresher"),
            (10, None, 7, 17, "Light Refresher"),
            (10, None, 10, 20, "Light Refresher"),
            (10, None, 17, 27, "Grade Ready"),
        )
        formulas = _row_formulas(20)
        self.assertEqual(
            formulas["I"],
            '=IF(AND(F20="",G20="",H20=""),"",SUM(F20:H20))',
        )
        self.assertEqual(
            formulas["J"],
            '=IF(I20="","",IF(I20<=10,"Full Refresher",IF(I20<17,"Moderate Refresher",IF(I20<27,"Light Refresher","Grade Ready"))))',
        )
        self.assertEqual(
            formulas["P"],
            '=IF(AND(M20>0,OR(N20>0,O20>0)),(M20/((N20*60)+O20))*60,"")',
        )
        self.assertEqual(
            formulas["Q"],
            '=IF(AND(K20<>"",M20>0),IFERROR(M20/IF(K20=2,$P$7,$M$7),""),"")',
        )
        for task1, rhymes, sentences, total, level in cases:
            with self.subTest(task1=task1, rhymes=rhymes, sentences=sentences):
                self.assertEqual(task1 + (rhymes or 0) + (sentences or 0), total)
                self.assertEqual(
                    "Full Refresher" if total <= 10 else
                    "Moderate Refresher" if total < 17 else
                    "Light Refresher" if total < 27 else "Grade Ready",
                    level,
                )

    def test_story_number_uses_persisted_selected_story_title(self):
        self.assertEqual(_story_number({}, {"selected_story": "Si Pagong at Kuneho"}), 1)
        self.assertEqual(_story_number({}, {"selected_story": "Isang Kakaibang Araw"}), 2)
        self.assertIsNone(_story_number({}, {"selected_story": "Unknown Story"}))

    def make_user(self, custom_id, role, first_name, last_name, **extra):
        return User.objects.create(
            custom_id=custom_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
            middle_initial=extra.pop("middle_initial", ""),
            suffix=extra.pop("suffix", ""),
            sex=extra.pop("sex", "female"),
            birth_month=1,
            birth_day=1,
            birth_year=2018 if role == "student" else 1990,
            email=f"{custom_id.lower()}@example.com",
            password_hash=make_password("password"),
            **extra,
        )

    def test_export_uses_persisted_completed_sentence_count_not_miscues(self):
        teacher = self.make_user("CRLA-MISCUE-T", "teacher", "Mia", "Lopez")
        student = self.make_user("CRLA-MISCUE-S", "student", "Toni", "Cruz")
        section = test_section_create(
            class_code="G2-MISCUE", class_name="Grade 2 Miscue", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        enrollment = Enrollment.objects.create(student=student, section=section)
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="CRLA sentence export", code="CRLA-MISCUE-ROOT",
            assessment_type="sentence", status="published",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-MISCUE-MAT",
            item_type="sentence", type="assessment", assessment_kind="crla",
        )
        payload = build_assessment_score_payload({
            "assessment_type": "sentence",
            "crla_score_data": {
                "task1_score": 8,
                "task2_type": "Task 2H / Sentences",
                "sentences_read": 4,
                "miscues": 3,
            },
        })
        Assessment.objects.create(
            teacher=teacher, enrollment=enrollment, material=material, source_assessment=root,
            student=student, title="CRLA sentence result", code="CRLA-MISCUE-RESULT",
            assessment_type="sentence", status="published", attempt_status="completed",
            completed_at=timezone.now(), crla_classification="High Emerging Reader",
            crla_score_data=payload["crla_score_data"],
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
        self.assertEqual(sheet["F11"].value, 8)
        self.assertEqual(sheet["H11"].value, 10)

    def test_export_uses_assigned_teacher_and_persisted_story_two_results(self):
        admin = self.make_user("CRLA-ADMIN", "admin", "PABASA", "Admin")
        teacher = self.make_user(
            "CRLA-TEACHER", "teacher", "Maria", "Santos",
            middle_initial="G", suffix="Jr.", school="Incorrect profile school",
        )
        student = self.make_user("CRLA-STUDENT", "student", "Lina", "Reyes", lrn="123456789012")
        school = School.objects.create(name="Mabini Elementary School", code="MABINI-ES")
        section = test_section_create(
            class_code="G2-RIZAL", class_name="Grade 2 Rizal", teacher=teacher,
            school=school, subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        enrollment = Enrollment.objects.create(student=student, section=section)
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
        student.preference = {"reading_assessment_state": {"crla_result_states": {
            str(material.id): {
                "material_id": str(material.id), "stage": "completed", "branch": "story",
                "task1_score": 10, "task2_sentences_score": 4, "part1_total_score": 14,
                "selected_story": "Si Pagong at Kuneho", "story_total_words": 96,
                "words_read": 96, "miscues": 0, "duration_seconds": 520,
                "wpm": 11.08, "story_read_percent": 100, "correct_answers": 4,
                "comprehension_correct": 4, "learner_experience_rating": 4,
                "classification": "Transitioning Reader",
            },
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=admin, enrollment=enrollment, material=material, source_assessment=root,
            student=student, title="CRLA result", code="CRLA-EXPORT-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), duration_seconds=125, word_count=70, wpm=33.6,
            accuracy=70, correct_items=3, crla_classification="Transitioning Reader", crla_score_data={
                "task1_score": 10, "task2_type": "Task 2H / Sentences", "task2_score": 4,
                "part1_total_score": 14, "story_number": 1, "story_total_words": 96,
                "words_read": 96, "miscues": 0, "duration_seconds": 519.99, "wpm": 11.08,
                "passage_accuracy_percent": 100, "comprehension_total": 6,
                "comprehension_correct": 4,
            },
        )

        workbook = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)
        self.assertEqual(workbook.sheetnames, [
            "G2 MT Reading Scoresheet",
            "G2 FIL Reading Scoresheet",
            "Class Record",
            "Class Summary",
            "Scoring Reference",
            "List",
        ])
        sheet = workbook["G2 MT Reading Scoresheet"]

        self.assertEqual(sheet["C4"].value, "MABINI-ES")
        self.assertEqual(sheet["C5"].value, "Mabini Elementary School")
        self.assertEqual(sheet["C6"].value, "Maria G. Santos Jr.")
        self.assertEqual(sheet["C8"].value, "Grade 2 Rizal")
        self.assertEqual(sheet["F11"].value, 10)
        self.assertIsNone(sheet["G11"].value)
        self.assertEqual(sheet["H11"].value, 10)
        self.assertTrue(str(sheet["I11"].value).startswith("="))
        self.assertTrue(str(sheet["J11"].value).startswith("="))
        self.assertEqual(sheet["K11"].value, 1)
        self.assertEqual(sheet["L11"].value, 0)
        self.assertEqual(sheet["M11"].value, 96)
        self.assertEqual((sheet["N11"].value, sheet["O11"].value), (8, 40))
        self.assertTrue(str(sheet["P11"].value).startswith("="))
        self.assertTrue(str(sheet["Q11"].value).startswith("="))
        self.assertEqual(sheet["R11"].value, 4)
        self.assertEqual(sheet["S11"].value, 4)
        self.assertEqual(sheet["T11"].value, "Level 3")
        self.assertEqual(sheet["U11"].value, "Transitioning Reader")
        self.assertEqual(sheet["V11"].value, "Needs continued reading practice")

    def test_export_metadata_leaves_teacher_blank_without_assigned_teacher(self):
        admin = self.make_user("CRLA-META-ADMIN", "admin", "PABASA", "Admin")
        student = self.make_user("CRLA-META-STUDENT", "student", "Nilo", "Reyes")
        school = School.objects.create(name="Metadata School", code="META-SCHOOL")
        section = test_section_create(
            class_code="G2-META", class_name="Grade 2 Metadata", school=school,
            teacher=None, subject="Filipino",
        )
        enrollment = Enrollment.objects.create(student=student, section=section)
        root = Assessment.objects.create(
            teacher=admin, title="Official CRLA", code="CRLA-META-NO-TEACHER",
            assessment_type="paragraph", status="published", is_system_owned=True,
            system_assessment_key="bosy_crla_pretest",
        )
        Assessment.objects.create(
            teacher=admin, enrollment=enrollment, source_assessment=root, student=student,
            title="CRLA result", code="CRLA-META-NO-TEACHER-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), crla_classification="Low Emerging Reader",
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]

        self.assertEqual(sheet["C4"].value, "META-SCHOOL")
        self.assertEqual(sheet["C5"].value, "Metadata School")
        self.assertIsNone(sheet["C6"].value)
        self.assertEqual(sheet["C8"].value, "Grade 2 Metadata")

    def test_export_metadata_does_not_fallback_when_school_fields_are_empty(self):
        admin = self.make_user("CRLA-NO-SCHOOL-ADMIN", "admin", "PABASA", "Admin", school="Admin School")
        teacher = self.make_user("CRLA-NO-SCHOOL-TEACHER", "teacher", "Ana", "Cruz")
        student = self.make_user("CRLA-NO-SCHOOL-STUDENT", "student", "Rosa", "Santos")
        school = School.objects.create(name="", code="")
        section = test_section_create(
            class_code="G2-NO-SCHOOL", class_name="Grade 2 No School", school=school,
            teacher=teacher, subject="Filipino",
        )
        enrollment = Enrollment.objects.create(student=student, section=section)
        root = Assessment.objects.create(
            teacher=admin, title="Official CRLA", code="CRLA-META-NO-SCHOOL",
            assessment_type="paragraph", status="published", is_system_owned=True,
            system_assessment_key="midline_crla_midtest",
        )
        Assessment.objects.create(
            teacher=admin, enrollment=enrollment, source_assessment=root, student=student,
            title="CRLA result", code="CRLA-META-NO-SCHOOL-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), crla_classification="Low Emerging Reader",
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]

        self.assertFalse(sheet["C4"].value)
        self.assertFalse(sheet["C5"].value)
        self.assertEqual(sheet["C6"].value, "Ana Cruz")
        self.assertEqual(sheet["C8"].value, "Grade 2 No School")

    def test_export_metadata_blanks_ambiguous_mixed_section_results(self):
        admin = self.make_user("CRLA-MIXED-ADMIN", "admin", "PABASA", "Admin")
        teacher_one = self.make_user("CRLA-MIXED-T1", "teacher", "Ana", "Cruz")
        teacher_two = self.make_user("CRLA-MIXED-T2", "teacher", "Luz", "Reyes")
        student_one = self.make_user("CRLA-MIXED-S1", "student", "Lina", "Santos")
        student_two = self.make_user("CRLA-MIXED-S2", "student", "Nilo", "Garcia")
        school_one = School.objects.create(name="North School", code="NORTH")
        school_two = School.objects.create(name="South School", code="SOUTH")
        section_one = test_section_create(
            class_code="G2-NORTH", class_name="Grade 2 North", school=school_one,
            teacher=teacher_one, subject="Filipino",
        )
        section_two = test_section_create(
            class_code="G2-SOUTH", class_name="Grade 2 South", school=school_two,
            teacher=teacher_two, subject="Filipino",
        )
        root = Assessment.objects.create(
            teacher=admin, title="Official CRLA", code="CRLA-META-MIXED",
            assessment_type="paragraph", status="published", is_system_owned=True,
            system_assessment_key="eosy_crla_posttest",
        )
        for index, (student, section) in enumerate(((student_one, section_one), (student_two, section_two)), start=1):
            enrollment = Enrollment.objects.create(student=student, section=section)
            Assessment.objects.create(
                teacher=admin, enrollment=enrollment, source_assessment=root, student=student,
                title="CRLA result", code=f"CRLA-META-MIXED-RESULT-{index}",
                assessment_type="paragraph", status="published", attempt_status="completed",
                completed_at=timezone.now(), crla_classification="Low Emerging Reader",
            )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]

        for cell in ("C4", "C5", "C6", "C8"):
            self.assertIsNone(sheet[cell].value)

    def test_low_emerging_branch_leaves_part_two_cells_blank(self):
        teacher = self.make_user("CRLA-T2", "teacher", "Ana", "Cruz")
        student = self.make_user("CRLA-S2", "student", "Nilo", "Dela Cruz")
        section = test_section_create(
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
            "task1_score": 1, "task2_rhymes_score": 9, "part1_total_score": 10,
            "classification": "Low Emerging Reader", "learner_experience_rating": 3,
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="early result", code="CRLA-EARLY-RESULT",
            assessment_type="word", status="published", attempt_status="completed",
            completed_at=timezone.now(), duration_seconds=20, word_count=6, wpm=18, accuracy=60,
            crla_classification="Low Emerging Reader",
            crla_score_data={
                "task1_score": 6,
                "task2_type": "Task 2L / Rhymes",
                "task2_rhymes_score": 3,
                "part1_total_score": 9,
            },
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
        self.assertEqual((sheet["F11"].value, sheet["G11"].value), (6, 3))
        self.assertIsNone(sheet["H11"].value)
        self.assertTrue(str(sheet["I11"].value).startswith("="))
        self.assertTrue(str(sheet["J11"].value).startswith("="))
        self.assertEqual(sheet["G11"].value, 3)
        for column in ("K", "L", "M", "N", "O", "R", "T"):
            self.assertIsNone(sheet[f"{column}11"].value)
        self.assertEqual(sheet["S11"].value, 3)
        self.assertTrue(str(sheet["P11"].value).startswith("="))
        self.assertTrue(str(sheet["Q11"].value).startswith("="))
        self.assertEqual(sheet["U11"].value, "Low Emerging Reader")
        self.assertEqual(sheet["V11"].value, "Needs intensive reading intervention")

    def test_export_keeps_official_formula_cells_and_persists_story_miscues(self):
        teacher = self.make_user("CRLA-T3", "teacher", "Luz", "Delgado")
        student = self.make_user("CRLA-S3", "student", "Rosa", "Santos")
        section = test_section_create(
            class_code="G2-SAMPAGUITA", class_name="Grade 2 Sampaguita", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="CRLA Story Export", code="CRLA-STORY-EXPORT",
            assessment_type="paragraph", status="published",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-STORY-MAT",
            item_type="paragraph", type="assessment", assessment_kind="crla",
            content_json={"passages": [{"title": "Story One"}, {"title": "Story Two"}]},
        )
        student.preference = {"reading_assessment_state": {"crla_result_states": {
            str(material.id): {
                "material_id": str(material.id), "stage": "completed", "branch": "story",
                "task1_score": 8, "task2_sentences_score": 7, "part1_total_score": 15,
                "selected_story": "Isang Kakaibang Araw", "story_total_words": 100,
                "words_read": 70, "miscues": 3, "duration_seconds": 125,
                "wpm": 33.6, "story_read_percent": 70, "correct_answers": 3,
                "comprehension_correct": 3, "classification": "Transitioning Reader",
            },
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="story result", code="CRLA-STORY-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), duration_seconds=125, word_count=70, wpm=33.6,
            accuracy=70, correct_items=3, crla_classification="Transitioning Reader", crla_score_data={
                "task1_score": 8, "task2_type": "Task 2H / Sentences", "task2_score": 7,
                "story_number": 2, "words_read": 70, "miscues": 3,
                "duration_seconds": 125, "wpm": 33.6, "passage_accuracy_percent": 70,
                "comprehension_correct": 3,
            },
        )
        StoryReadingProgress.objects.create(
            student=student, material=material, story_title="Story Two", total_words=100,
            words_read=70, correct_words=70, miscues=3, accuracy=70, wpm=33.6,
            correct_sentences=3, duration_seconds=125, completed=True,
            completed_at=timezone.now(),
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
        self.assertEqual(sheet["F11"].value, 8)
        self.assertEqual(sheet["H11"].value, 10)
        self.assertTrue(str(sheet["I11"].value).startswith("="))
        self.assertTrue(str(sheet["J11"].value).startswith("="))
        self.assertEqual(sheet["K11"].value, 2)
        self.assertEqual(sheet["L11"].value, 3)
        self.assertEqual(sheet["M11"].value, 70)
        self.assertEqual((sheet["N11"].value, sheet["O11"].value), (2, 5))
        self.assertTrue(str(sheet["P11"].value).startswith("="))
        self.assertTrue(str(sheet["Q11"].value).startswith("="))
        self.assertEqual(sheet["R11"].value, 3)

    def test_transition_to_story_without_story_reading_keeps_part_two_blank(self):
        teacher = self.make_user("CRLA-T4", "teacher", "Tina", "Reyes")
        student = self.make_user("CRLA-S4", "student", "Noel", "Ramos")
        section = test_section_create(
            class_code="G2-TRANSITION", class_name="Grade 2 Transition", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="CRLA Transition", code="CRLA-TRANSITION",
            assessment_type="sentence", status="published",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-TRANSITION-MAT",
            item_type="sentence", type="assessment", assessment_kind="crla",
        )
        student.preference = {"reading_assessment_state": {"crla_result_states": {
            str(material.id): {
                "material_id": str(material.id), "stage": "transition_to_story",
                "selected_story": "Si Pagong at Kuneho", "story_total_words": 96,
                "words_read": 96, "duration_seconds": 300, "story_read_percent": 100,
            },
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="transition result", code="CRLA-TRANSITION-RESULT",
            assessment_type="sentence", status="published", attempt_status="completed",
            completed_at=timezone.now(), crla_score_data={
                "task1_score": 8, "task2_type": "Task 2H / Sentences", "task2_score": 7,
                "words_read": 96, "duration_seconds": 300, "passage_accuracy_percent": 100,
            },
        )

        workbook = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)
        sheet = workbook["G2 MT Reading Scoresheet"]
        for column in ("K", "L", "N", "O"):
            self.assertIsNone(sheet[f"{column}11"].value)
        # M is a template-owned formula cell; with no Part 2 evidence its
        # calculated value remains blank rather than the formula being removed.
        self.assertTrue(str(sheet["M11"].value).startswith("="))
        self.assertIsNone(sheet["R11"].value)
        self.assertTrue(str(sheet["P11"].value).startswith("="))
        self.assertTrue(str(sheet["Q11"].value).startswith("="))
        calculated = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=True)["G2 MT Reading Scoresheet"]
        self.assertIsNone(calculated["M11"].value)
        self.assertIsNone(calculated["Q11"].value)

    def test_export_uses_completed_part2_attempt_when_resumable_state_is_partial(self):
        """A completed result must not lose Part 2 to a stale transition state."""
        teacher = self.make_user("CRLA-T-PART2", "teacher", "Pia", "Santos")
        student = self.make_user("CRLA-S-PART2", "student", "Nico", "Cruz")
        section = test_section_create(
            class_code="G2-PART2", class_name="Grade 2 Part 2", teacher=teacher,
            subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
        )
        root = Assessment.objects.create(
            teacher=teacher, section=section, title="CRLA Part 2 fallback", code="CRLA-PART2-FALLBACK",
            assessment_type="paragraph", status="published",
        )
        material = Material.objects.create(
            assessment=root, section=section, teacher=teacher, code="CRLA-PART2-MAT",
            item_type="paragraph", type="assessment", assessment_kind="crla",
        )
        # This reproduces the pre-fix race: the browser result request has
        # completed, while the resumable state still says Part 2 is pending.
        student.preference = {"reading_assessment_state": {"crla_result_states": {
            str(material.id): {"material_id": str(material.id), "stage": "transition_to_story"},
        }}}
        student.save(update_fields=["preference", "updated_at"])
        Assessment.objects.create(
            teacher=teacher, section=section, material=material, source_assessment=root,
            student=student, title="completed Part 2", code="CRLA-PART2-RESULT",
            assessment_type="paragraph", status="published", attempt_status="completed",
            completed_at=timezone.now(), crla_classification="Transitioning Reader", crla_score_data={
                "task1_score": 8, "task2_type": "Task 2H / Sentences", "task2_score": 7,
                "story_number": 2, "story_total_words": 100, "words_read": 0,
                "miscues": 0, "duration_seconds": 0, "wpm": 0,
                "passage_accuracy_percent": 0, "comprehension_correct": 0,
                "crla_classification": "Transitioning Reader",
            },
        )

        sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
        self.assertEqual(sheet["K11"].value, 2)
        self.assertEqual(sheet["L11"].value, 0)
        self.assertEqual(sheet["M11"].value, 0)
        self.assertEqual((sheet["N11"].value, sheet["O11"].value), (0, 0))
        self.assertEqual(sheet["R11"].value, 0)
        # S is the learner-experience rating.  Observation Level is column T.
        # This completed fixture deliberately has no learner-experience rating.
        self.assertIsNone(sheet["S11"].value)
        self.assertEqual(sheet["T11"].value, "Level 3")
        self.assertEqual(sheet["U11"].value, "Transitioning Reader")

    def test_story_metrics_export_for_each_official_crla_phase(self):
        phases = (
            ("bosy", "pretest", "bosy_crla_pretest"),
            ("midline", "midtest", "midline_crla_midtest"),
            ("eosy", "posttest", "eosy_crla_posttest"),
        )
        for index, (period, phase, key) in enumerate(phases, start=1):
            with self.subTest(phase=phase):
                teacher = self.make_user(f"CRLA-T-PH-{index}", "teacher", "Phase", f"Teacher{index}")
                student = self.make_user(f"CRLA-S-PH-{index}", "student", "Phase", f"Student{index}")
                section = test_section_create(
                    class_code=f"G2-PHASE-{index}", class_name=f"Grade 2 Phase {index}", teacher=teacher,
                    subject="Filipino", students=[{"student_id": student.id, "is_active": True}],
                )
                root = Assessment.objects.create(
                    teacher=teacher, section=section, title=f"CRLA {period}", code=f"CRLA-PHASE-{index}",
                    assessment_type="paragraph", status="published", is_system_owned=True,
                    system_assessment_key=key, system_assessment_period=period,
                    system_assessment_phase=phase,
                )
                material = Material.objects.create(
                    assessment=root, section=section, teacher=teacher, code=f"CRLA-PHASE-MAT-{index}",
                    item_type="paragraph", type="assessment", assessment_kind="crla",
                    is_system_owned=True, is_official_reading=True,
                    system_assessment_key=f"{key}-MATERIAL", system_assessment_period=period,
                    system_assessment_phase=phase,
                )
                student.preference = {"reading_assessment_state": {"crla_result_states": {
                    str(material.id): {
                        "material_id": str(material.id), "stage": "completed",
                        "selected_story": "Si Pagong at Kuneho", "story_total_words": 96,
                        "words_read": 72, "miscues": 24, "duration_seconds": 125,
                        "wpm": 34.56, "story_read_percent": 75,
                        "comprehension_correct": 3, "classification": "Transitioning Reader",
                    },
                }}}
                student.save(update_fields=["preference", "updated_at"])
                Assessment.objects.create(
                    teacher=teacher, section=section, material=material, source_assessment=root,
                    student=student, title=f"{period} result", code=f"CRLA-PHASE-RESULT-{index}",
                    assessment_type="paragraph", status="published", attempt_status="completed",
                    completed_at=timezone.now(), crla_classification="Transitioning Reader", crla_score_data={
                        "task1_score": 8, "task2_type": "Task 2H / Sentences", "task2_score": 7,
                        # Generic fields disagree on purpose; only the
                        # material-scoped Story Reading values may export.
                        "duration_seconds": 9, "words_read": 1, "passage_accuracy_percent": 1,
                    },
                )

                sheet = load_workbook(BytesIO(export_crla_excel(root.id).getvalue()), data_only=False)["G2 MT Reading Scoresheet"]
                self.assertEqual(sheet["C4"].value, section.school.code)
                self.assertEqual(sheet["C5"].value, section.school.name)
                self.assertEqual(sheet["C6"].value, f"Phase Teacher{index}")
                self.assertEqual(sheet["C8"].value, section.class_name)
                self.assertEqual(sheet["K11"].value, 1)
                self.assertEqual((sheet["N11"].value, sheet["O11"].value), (2, 5))
                self.assertEqual(sheet["M11"].value, 72)
                self.assertTrue(str(sheet["Q11"].value).startswith("="))
