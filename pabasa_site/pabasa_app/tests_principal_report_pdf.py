"""Presentation, content retention and pagination contracts for Principal PDFs."""
from copy import deepcopy
from datetime import datetime, timezone as dt_timezone
from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pypdf import PdfReader

from .principal_exports import REPORT_TYPES, pdf_response, report_rows
from .principal_report_pdf import _percentage


def example_snapshot(**overrides):
    """Synthetic, clearly separate from school database records."""
    snapshot = {
        'school_name': 'Salawag Elementary School',
        'scope_calendar': SimpleNamespace(school_year='2026-2027'),
        'scope_term': '2', 'scope_phase': 'midtest', 'scope_phase_label': 'Midline Mid-Test',
        'scope_section_label': 'All sections',
        'snapshot_at': datetime(2026, 11, 10, 4, 30, tzinfo=dt_timezone.utc),
        'metric_definition': 'Active/completed Grade 2 enrollments in the selected school year; latest finalized official CRLA result per learner. Accuracy includes recorded zero values; missing values are not zero.',
        'total_students': 240, 'total_teachers': 8, 'total_sections': 8,
        'total_assessments': 17, 'official_completed_students': 198,
        'completion_rate': 82.5, 'average_score': 74.6, 'accuracy_samples': 192,
        'aral_eligible_students': 121, 'aral_progress_students': 97,
        'aral_recorded_exits': 11, 'pending_review_students': 14,
        'prescribed_counts': {'completed': 861},
        'supplementary_counts': {'assigned': 320, 'completed': 276},
        'grade_rows': [], 'assessment_rows': [], 'classification_rows': [],
        'missing_official_students': 42, 'section_rows': [], 'follow_up_rows': [],
    }
    snapshot.update(overrides)
    return snapshot


class PrincipalPdfPresentationTests(SimpleTestCase):
    def render(self, snapshot=None, report_type='school', rows_override=None):
        snapshot = snapshot or example_snapshot()
        headers, rows = report_rows(snapshot, report_type)
        if rows_override is not None:
            rows = rows_override
        original = deepcopy((snapshot, headers, rows))
        response = pdf_response(snapshot, report_type, headers, rows)
        self.assertEqual((snapshot, headers, rows), original)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn(f'principal_{report_type}_report_', response['Content-Disposition'])
        reader = PdfReader(BytesIO(response.content))
        text = ' '.join(' '.join(page.extract_text() or '' for page in reader.pages).split())
        return reader, text

    def test_school_report_preserves_all_metrics_scope_and_definitions(self):
        snapshot = example_snapshot()
        reader, text = self.render(snapshot)
        self.assertEqual(len(reader.pages), 2)
        for _, value in report_rows(snapshot)[1]:
            self.assertIn(str(value), text)
        for label, value in report_rows(snapshot)[1][8:]:
            self.assertIn(f'{label} {value}', text, 'Each metric must retain its corresponding value.')
        for title in ['School Reading', 'Performance Report', 'EXECUTIVE OVERVIEW',
                      'CRLA Assessment Performance', 'ARAL Program Engagement',
                      'Learning Activities & Supplementary Engagement']:
            self.assertIn(title, text)
        self.assertIn(snapshot['metric_definition'], text)
        self.assertIn('November 10, 2026 12:30 PM', text)
        self.assertIn('Assessment period: midtest', text)
        self.assertIn('Midline Mid-Test', text)
        self.assertIn('Completion does not establish skill mastery.', text)
        for i, page in enumerate(reader.pages, 1):
            self.assertIn(f'Page {i} of 2', page.extract_text())
            self.assertIn('CONFIDENTIAL', page.extract_text())
            self.assertAlmostEqual(float(page.mediabox.width), 595.2756, places=2)

    def test_zero_accuracy_is_not_unavailable(self):
        reader, text = self.render(example_snapshot(average_score=0, completion_rate=0,
            official_completed_students=0, accuracy_samples=1))
        self.assertEqual(len(reader.pages), 2)
        self.assertIn('0%', text)
        self.assertNotIn('N/A', text)

    def test_empty_scope_and_missing_accuracy_are_not_fabricated(self):
        snapshot = example_snapshot(total_students=0, total_teachers=0, total_sections=0,
            total_assessments=0, official_completed_students=0, accuracy_samples=0,
            completion_rate=0, average_score=None, scope_calendar=None, scope_term='',
            scope_phase='', scope_phase_label='All CRLA periods')
        reader, text = self.render(snapshot)
        self.assertEqual(len(reader.pages), 2)
        self.assertIn('N/A', text)
        self.assertIn('Legacy / unassigned year', text)
        self.assertIn('0 learners completed / 0 enrolled', text)
        self.assertIn('All CRLA periods', text)

    def test_new_export_metrics_are_not_silently_dropped(self):
        snapshot = example_snapshot()
        rows = report_rows(snapshot)[1] + [['A future institutional metric', 'unique-value-784']]
        _, text = self.render(snapshot, rows_override=rows)
        self.assertIn('Additional Institutional Metrics', text)
        self.assertIn('A future institutional metric', text)
        self.assertIn('unique-value-784', text)

    def test_other_exports_preserve_every_header_and_row(self):
        for report_type in REPORT_TYPES:
            if report_type == 'school':
                continue
            with self.subTest(report_type=report_type):
                snapshot = example_snapshot()
                headers, _ = report_rows(snapshot, report_type)
                rows = [[f'row-{i}-cell-{j}' for j in range(len(headers))] for i in range(28)]
                reader, text = self.render(snapshot, report_type, rows)
                for header in headers:
                    self.assertIn(header, text)
                for row in rows:
                    for value in row:
                        self.assertIn(value, text)
                for i, page in enumerate(reader.pages, 1):
                    self.assertIn(f'Page {i} of {len(reader.pages)}', page.extract_text())
                if len(headers) > 6:
                    self.assertGreater(float(reader.pages[1].mediabox.width), float(reader.pages[1].mediabox.height))

    def test_long_follow_up_text_splits_without_losing_content(self):
        rows = [['A & B <School>', 'Section ' + 'Long Name ' * 10, 'Sample Teacher',
                 'Recorded follow-up evidence. ' * 190 + 'END-OF-RECORD']]
        reader, text = self.render(example_snapshot(), 'intervention', rows)
        self.assertGreater(len(reader.pages), 2)
        self.assertIn('A & B <School>', text)
        self.assertIn('END-OF-RECORD', text)
        self.assertGreater(text.count('Follow-up reason'), 1)

    def test_empty_detailed_exports_are_explicit(self):
        _, text = self.render(example_snapshot(), 'assessment')
        self.assertIn('No records in the selected scope.', text)

    def test_percentage_visuals_do_not_accept_invalid_or_missing_values(self):
        for value in [None, '', 'N/A', float('nan'), float('inf'), -1, 101]:
            self.assertIsNone(_percentage(value))
        self.assertEqual(_percentage(0), 0)
        self.assertEqual(_percentage(100), 100)

    def test_renderer_has_no_database_queries(self):
        # SimpleTestCase forbids database access, including accidental lazy queries.
        self.render(example_snapshot())


class PrincipalPdfWorkflowTests(TestCase):
    def test_principal_export_uses_own_school_snapshot_and_selected_scope(self):
        from .models import School, SchoolCalendar, Section
        from .test_principal_school_isolation import _user
        school = School.objects.create(name='Principal PDF School', code='PDF-OWN')
        foreign = School.objects.create(name='Foreign PDF School', code='PDF-OTHER')
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=2, is_active=True)
        principal = _user('principal', 'PDF Principal', school)
        teacher = _user('teacher', 'PDF Teacher', school)
        learner = _user('student', 'PDF Learner', school, 'Grade 2')
        foreign_teacher = _user('teacher', 'Other Teacher', foreign)
        foreign_learner = _user('student', 'Other Learner', foreign, 'Grade 2')
        for code, owner, student, school_record in [
            ('PDF-A', teacher, learner, school), ('PDF-B', foreign_teacher, foreign_learner, foreign),
        ]:
            section = Section.objects.create(class_code=code, class_name=code, section=code,
                grade_level='Grade 2', school=school_record, teacher=owner, school_calendar=calendar)
            section.add_student(student)
        session = self.client.session
        session.update({'user_id': principal.pk, 'user_role': 'principal', 'custom_id': principal.custom_id,
                        'first_name': principal.first_name, 'last_name': principal.last_name, 'email': principal.email})
        session.save()
        response = self.client.get(reverse('principal_reports'), {
            'report_type': 'school', 'export': 'pdf', 'calendar_id': calendar.pk,
            'term': '2', 'phase': 'midtest',
        })
        self.assertEqual(response.status_code, 200)
        reader = PdfReader(BytesIO(response.content))
        text = ' '.join(' '.join(page.extract_text() for page in reader.pages).split())
        self.assertIn('Principal PDF School', text)
        self.assertNotIn('Foreign PDF School', text)
        self.assertIn('Total Enrolled Students 1', text)
        self.assertIn('Term: 2', text)
        self.assertIn('Assessment period: midtest', text)
        self.assertIn('2026-2027', text)
