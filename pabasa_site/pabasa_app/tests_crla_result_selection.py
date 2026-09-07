from django.test import TestCase
from django.utils import timezone

from .models import Assessment, Material, User
from .utils.crla_results import latest_completed_official_crla_results


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

    def _result(self, code, *, status="completed", completed=True, classification="Low Emerging Reader", source=None, material=None, system=False):
        return Assessment.objects.create(
            title=code, code=code, teacher=self.teacher, student=self.student,
            source_assessment=source or self.root, material=material if material is not None else self.material,
            assessment_type="word", attempt_status=status,
            completed_at=timezone.now() if completed else None,
            crla_classification=classification, is_system_owned=system,
        )

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
