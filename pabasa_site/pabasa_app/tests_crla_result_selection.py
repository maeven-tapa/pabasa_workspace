import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Assessment, Enrollment, Material, School, Section, User
from .utils.crla_export import _latest_attempts, canonical_crla_result_values
from .utils.crla_results import latest_completed_official_crla_results
from .views import _latest_completed_official_crla_results


class OfficialCrlaResultSelectionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="CRLA-SEL-T", role="teacher", first_name="Teacher", last_name="One",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="teacher-selection@example.test", password_hash="x",
        )
        self.student = User.objects.create(
            custom_id="CRLA-SEL-S", role="student", first_name="Student", last_name="One",
            sex="female", birth_month=1, birth_day=1, birth_year=2018,
            email="student-selection@example.test", password_hash="x",
        )
        self.root = Assessment.objects.create(
            title="Official CRLA", code="CRLA-SEL-ROOT", teacher=self.teacher,
            assessment_type="word", is_system_owned=True,
            system_assessment_key="bosy_crla_pretest",
        )
        self.material = Material.objects.create(
            title="Official CRLA material", code="CRLA-SEL-MAT", teacher=self.teacher,
            assessment=self.root, item_type="word", type="assessment",
            assessment_kind="crla", is_official_reading=True,
        )
        self.school = School.objects.create(name="Selection Test School", code="CRLA-SEL-SCHOOL")
        self.section_one = Section.objects.create(
            school=self.school, class_code="CRLA-SEL-ONE", class_name="Selection One",
            teacher=self.teacher, subject="Reading", grade_level="Grade 2",
        )
        self.section_two = Section.objects.create(
            school=self.school, class_code="CRLA-SEL-TWO", class_name="Selection Two",
            teacher=self.teacher, subject="Reading", grade_level="Grade 2",
        )
        self.enrollment_one = Enrollment.objects.create(student=self.student, section=self.section_one)
        self.enrollment_two = Enrollment.objects.create(student=self.student, section=self.section_two)

    def _result(self, code, *, status="completed", completed=True, classification="Low Emerging Reader", source=None, material=None, system=False, term=1, phase="pretest", enrollment=None, score_data=None, completed_at=None):
        return Assessment.objects.create(
            title=code, code=code, teacher=self.teacher, student=self.student,
            source_assessment=source or self.root, material=material if material is not None else self.material,
            enrollment=enrollment, system_assessment_phase=phase, official_term=term,
            assessment_type="word", attempt_status=status,
            completed_at=completed_at or (timezone.now() if completed else None),
            crla_classification=classification, is_system_owned=system,
            crla_score_data=score_data or {},
        )

    def test_scoped_selector_keeps_historical_term_and_phase_results(self):
        base = timezone.now()
        term_one = self._result("CRLA-SEL-T1", term=1, phase="pretest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=3))
        term_two = self._result("CRLA-SEL-T2", term=2, phase="pretest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=2))
        midline = self._result("CRLA-SEL-MID", term=1, phase="midtest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=1))

        selected_t1 = _latest_completed_official_crla_results(
            [self.student.id], section=self.section_one, crla_term=1, crla_phase="pretest",
        )
        selected_t2 = _latest_completed_official_crla_results(
            [self.student.id], section=self.section_one, crla_term=2, crla_phase="pretest",
        )
        selected_midline = _latest_completed_official_crla_results(
            [self.student.id], section=self.section_one, crla_term=1, crla_phase="midtest",
        )

        student_key = str(self.student.id)
        self.assertEqual(selected_t1[student_key].id, term_one.id)
        self.assertEqual(selected_t2[student_key].id, term_two.id)
        self.assertEqual(selected_midline[student_key].id, midline.id)

    def test_scoped_selector_isolates_section_and_does_not_false_pending(self):
        base = timezone.now()
        section_one_result = self._result("CRLA-SEL-SECTION-ONE", term=1, phase="pretest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=2), score_data={"task1_score": 7})
        section_two_result = self._result("CRLA-SEL-SECTION-TWO", term=1, phase="pretest", enrollment=self.enrollment_two, completed_at=base - timedelta(days=1))

        selected = _latest_completed_official_crla_results(
            [self.student.id], section=self.section_one, crla_term=1, crla_phase="pretest",
        )
        selected_result = selected[str(self.student.id)]
        self.assertEqual(selected_result.id, section_one_result.id)
        canonical_values = canonical_crla_result_values(self.student, selected_result)
        self.assertEqual(canonical_values["task_1_score"], 7)
        self.assertTrue({
            "assessment_date", "task_1_score", "task_2l_score", "task_2h_score",
            "part_1_total", "part_1_reading_level", "story_number", "miscues",
            "total_words_read", "reading_minutes", "reading_seconds", "words_per_minute",
            "correct_words_percentage", "comprehension_score", "learner_experience_rating",
            "observation_level", "reading_profile", "remarks",
        }.issubset(canonical_values))
        self.assertNotEqual(selected_result.id, section_two_result.id)

    def test_observation_level_update_changes_only_selected_scoped_result(self):
        base = timezone.now()
        selected = self._result("CRLA-SEL-OBS-T1", term=1, phase="pretest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=2), score_data={"task1_score": 7, "custom": "keep"})
        other_term = self._result("CRLA-SEL-OBS-T2", term=2, phase="pretest", enrollment=self.enrollment_one, completed_at=base - timedelta(days=1), score_data={"observation_level": "Level 1"})

        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = "teacher"
        session.save()
        response = self.client.post(
            reverse("update_teacher_crla_observation_level"),
            data=json.dumps({
                "student_id": self.student.id, "section_id": self.section_one.id,
                "term": 1, "assessment": "pretest", "observation_level": "Level 4",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        selected.refresh_from_db()
        other_term.refresh_from_db()
        self.assertEqual(selected.crla_score_data["observation_level"], "Level 4")
        self.assertEqual(selected.crla_score_data["custom"], "keep")
        self.assertEqual(other_term.crla_score_data["observation_level"], "Level 1")
        self.assertEqual(
            canonical_crla_result_values(self.student, selected)["observation_level"],
            "Level 4",
        )

    def test_export_attempt_selection_is_scoped_before_latest(self):
        base = timezone.now()
        term_one = self._result(
            "CRLA-SEL-EXPORT-T1", term=1, phase="pretest", enrollment=self.enrollment_one,
            completed_at=base - timedelta(days=2), score_data={"observation_level": "Level 2"},
        )
        term_two = self._result(
            "CRLA-SEL-EXPORT-T2", term=2, phase="pretest", enrollment=self.enrollment_one,
            completed_at=base - timedelta(days=1), score_data={"observation_level": "Level 4"},
        )
        other_section = self._result(
            "CRLA-SEL-EXPORT-OTHER", term=1, phase="pretest", enrollment=self.enrollment_two,
            completed_at=base, score_data={"observation_level": "Level 1"},
        )

        selected_t1 = _latest_attempts(
            self.root, section_id=self.section_one.id, crla_term=1, crla_phase="pretest",
        )
        selected_t2 = _latest_attempts(
            self.root, section_id=self.section_one.id, crla_term=2, crla_phase="pretest",
        )

        self.assertEqual(selected_t1[self.student.id].id, term_one.id)
        self.assertEqual(selected_t1[self.student.id].crla_score_data["observation_level"], "Level 2")
        self.assertEqual(selected_t2[self.student.id].id, term_two.id)
        self.assertNotEqual(selected_t1[self.student.id].id, other_section.id)

    def test_only_latest_valid_official_crla_result_qualifies(self):
        valid = self._result("CRLA-SEL-VALID")
        self._result("CRLA-SEL-INCOMPLETE", status="started", completed=False, classification="Reading At Grade Level")
        self._result("CRLA-SEL-MISSING", classification="")
        Assessment.objects.create(
            title="System non-CRLA", code="CRLA-SEL-SYSTEM", teacher=self.teacher,
            student=self.student, assessment_type="word", attempt_status="completed",
            completed_at=timezone.now(), crla_classification="Reading At Grade Level",
            is_system_owned=True,
        )

        selected = latest_completed_official_crla_results(student_ids=[self.student.id])
        self.assertEqual(selected[self.student.id].id, valid.id)

    def test_later_valid_official_result_replaces_earlier_valid_result(self):
        self._result("CRLA-SEL-FIRST", classification="Low Emerging Reader")
        latest = self._result("CRLA-SEL-LATEST", classification="Transitioning Reader")

        selected = latest_completed_official_crla_results(student_ids=[self.student.id])
        self.assertEqual(selected[self.student.id].id, latest.id)

    def test_legacy_plural_profile_is_selected_and_normalized(self):
        legacy = self._result(
            "CRLA-SEL-LEGACY",
            classification="Low Emerging Readers",
        )
        legacy.crla_classification = ""
        legacy.classification = "Low Emerging Readers"
        legacy.save(update_fields=["crla_classification", "classification", "updated_at"])

        selected = latest_completed_official_crla_results(student_ids=[self.student.id])

        self.assertEqual(selected[self.student.id].id, legacy.id)
        self.assertEqual(
            selected[self.student.id].crla_classification,
            "Low Emerging Reader",
        )

    def test_terminal_student_state_creates_the_authoritative_result(self):
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = "student"
        session.save()

        response = self.client.post(
            reverse("persist_student_end_assessment_state"),
            data=json.dumps({
                "material_id": f"material-{self.material.id}",
                "stage": "early_completed_words",
                "task1_score": 4,
                "task2_rhymes_score": 2,
                "part1_total_score": 6,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        result = self.material.assessment_results.get(
            student=self.student,
            attempt_status="completed",
        )
        self.assertEqual(result.crla_classification, "Low Emerging Reader")
        selected = latest_completed_official_crla_results(student_ids=[self.student.id])
        self.assertEqual(selected[self.student.id].id, result.id)
