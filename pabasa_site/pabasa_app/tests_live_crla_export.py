"""Regression coverage from temporary Live CRLA evidence to workbook cells."""
from io import BytesIO
from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook

from .models import Assessment, CalendarEvent, LiveAssessmentSession, Material, School, SchoolCalendar, Section, User
from .scoring import build_assessment_score_payload, crla_task2_kind
from .utils.crla_export import _student_values, export_crla_excel
from .utils.crla_results import latest_completed_official_crla_results
from .views import (
    _build_live_session_completion_payload, _complete_assessment_for_student,
    _end_live_assessment_session, _update_live_student_state,
)


class LiveCrlaEvidenceTests(TestCase):
    def test_rhymes_label_is_never_detected_as_task_2h(self):
        for label in ('Task 2L / Rhymes', 'rhymes', '2L'):
            self.assertEqual(crla_task2_kind(label), 'rhymes')
        for label in ('Task 2H / Sentences', 'sentences', '2H'):
            self.assertEqual(crla_task2_kind(label), 'sentences')
        payload = build_assessment_score_payload({'assessment_type': 'word', 'crla_score_data': {
            'task1_score': 6, 'task2_type': 'Task 2L / Rhymes', 'task2_rhymes_score': 3,
        }})
        self.assertEqual(payload['crla_score_data']['task2_score'], 3)
        self.assertEqual(payload['crla_score_data']['part1_total_score'], 9)
        self.assertIsNone(payload['crla_score_data']['sentences_read'])

    def test_partial_recovery_does_not_blank_scores_and_accepts_real_zero(self):
        session = SimpleNamespace(student_states={'1': {'recovery_state': {
            'task1_score': 8, 'task2_sentences_score': 5, 'words_read': 12,
            'comprehension_correct': 2, 'learner_experience_rating': 4,
        }}})
        _update_live_student_state(session, 1, {'recovery_state': {
            'task1_score': None, 'task2_sentences_score': '', 'words_read': 0,
            'comprehension_correct': 0, 'learner_experience_rating': None,
        }})
        self.assertEqual(session.student_states['1']['recovery_state'], {
            'task1_score': 8, 'task2_sentences_score': 5, 'words_read': 0,
            'comprehension_correct': 0, 'learner_experience_rating': 4,
        })

    def test_sentence_export_preserves_each_mapped_score_without_remapping_as_count(self):
        student = SimpleNamespace(lrn='', first_name='Student', last_name='Test', middle_initial='', suffix='', sex='', preference={})
        for score in (0, 2, 5, 7, 10):
            with self.subTest(score=score):
                attempt = SimpleNamespace(material_id=1, completed_at=None, started_at=None, created_at=None,
                    crla_classification='High Emerging Reader', classification='High Emerging Reader',
                    crla_score_data={'task1_score': 8, 'task2_type': 'Task 2H / Sentences',
                        'task2_rhymes_score': 10, 'task2_sentences_score': score, 'part1_total_score': 18 + score})
                values = _student_values(student, attempt, {}, None)
                self.assertEqual(values['task_2l_score'], 10)
                self.assertEqual(values['task_2h_score'], score)

    def test_task2_completion_keeps_automatic_rhymes_credit_and_real_zero(self):
        for count, score in enumerate((0, 2, 5, 7, 10)):
            with self.subTest(count=count):
                payload = build_assessment_score_payload({'assessment_type': 'sentence', 'crla_score_data': {
                    'task1_score': 8, 'task2_type': 'Task 2H / Sentences', 'task2_rhymes_score': 10,
                    'task2_sentences_score': score, 'sentences_read': count,
                }})
                self.assertEqual(payload['crla_score_data']['task2_score'], score)
                self.assertEqual(payload['crla_score_data']['part1_total_score'], 18 + score)


class LiveCrlaWorkbookTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Live Export School', code='LIVE-EXPORT')
        self.calendar = SchoolCalendar.objects.create(school_year='Live Export Year', current_term=1, is_active=True)
        today = timezone.localdate()
        for event_type, start, end in (
            ('school_opening', today - timedelta(days=2), today - timedelta(days=2)),
            ('pre_assessment', today - timedelta(days=1), today + timedelta(days=1)),
            ('school_closing', today + timedelta(days=20), today + timedelta(days=20)),
        ):
            CalendarEvent.objects.create(school_calendar=self.calendar, school=self.school,
                scope=CalendarEvent.SCOPE_SCHOOL, term=1, title=event_type,
                event_type=event_type, start_date=start, end_date=end)
        self.teacher = self.make_user('teacher', 'teacher')
        self.section = Section.objects.create(school=self.school, teacher=self.teacher,
            class_code='LIVE-EXPORT', class_name='Live Export Class', subject='Reading',
            school_calendar=self.calendar, assessment_week_enabled=True)
        self.root = Assessment.objects.create(teacher=self.teacher, section=self.section,
            title='Live CRLA Export', code='LIVE-EXPORT-ROOT', assessment_type='paragraph', status='published',
            is_system_owned=True, system_assessment_key='bosy_crla_pretest')
        self.material = Material.objects.get(system_assessment_key='bosy_crla_pretest')
        Material.objects.filter(pk=self.material.pk).update(assessment=self.root, section=self.section)
        self.material.refresh_from_db()

    def make_user(self, identifier, role='student'):
        return User.objects.create(custom_id='live-export-' + identifier, role=role,
            first_name=identifier, last_name='Learner', middle_initial='', suffix='', sex='female',
            birth_month=1, birth_day=1, birth_year=2010, email=identifier + '@example.com',
            password_hash='unused', school_record=self.school)

    def test_end_session_exports_completed_students_from_both_batches_with_skips(self):
        students, states, assignments = [], {}, {}
        for index in range(12):
            student = self.make_user(f'{index:02d}')
            self.section.add_student(student)
            students.append(student)
            assignments[str(student.id)] = 1 if index < 10 else 2
            evidence = {
                'stage': 'completed', 'temporary_completed': True, 'learner_experience_rating': 3,
                'task1_score': 8, 'task2_type': 'Task 2H / Sentences', 'task2_rhymes_score': 10,
                'task2_sentences_score': 5, 'sentences_read': 2, 'part1_total_score': 23,
                'story_number': 1, 'story_total_words': 96, 'words_read': 0 if index == 0 else 48,
                'miscues': 0, 'duration_seconds': 60, 'comprehension_correct': 0 if index == 0 else 3,
                'comprehension_total': 6, 'crla_results': [None, None, None, True, True, True],
            }
            if index % 2:
                evidence.update(task1_score=6, task2_type='Task 2L / Rhymes', task2_rhymes_score=5,
                    task2_sentences_score=None, sentences_read=None, part1_total_score=11)
            states[str(student.id)] = {'status': 'completed', 'progress': 1, 'elapsed_seconds': 90,
                # Learner Experience can be restored on a Words URL. Its mode
                # and partial payload must not replace completed Part 2 evidence.
                'completion_payload': {'assessment_type': 'word', 'crla_score_data': {'task1_score': 8}},
                'recovery_state': evidence}
        session = LiveAssessmentSession.objects.create(id='live-export-batches', teacher=self.teacher,
            section=self.section, material=self.material, student_ids=[student.id for student in students],
            student_count=12, batch_assignments=assignments, current_batch=2, total_batches=2,
            status='started', start_at=timezone.now(), student_states=states)
        for student in students:
            payload = _build_live_session_completion_payload(session, student, states[str(student.id)])
            self.assertEqual(payload['assessment_type'], 'paragraph')
        _end_live_assessment_session(session)
        results = latest_completed_official_crla_results([student.id for student in students])
        self.assertEqual(len(results), 12)
        workbook = load_workbook(BytesIO(export_crla_excel(self.root.id, section_id=self.section.id).getvalue()))
        sheet = workbook['G2 MT Reading Scoresheet']
        exported_names = set()
        for row in range(11, 23):
            learner_name = sheet[f'C{row}'].value
            exported_names.add(learner_name)
            index = int(learner_name.split()[0])
            sentence_branch = index % 2 == 0
            self.assertEqual(sheet[f'F{row}'].value, 8 if sentence_branch else 6)
            self.assertEqual(sheet[f'G{row}'].value, 10 if sentence_branch else 5)
            self.assertEqual(sheet[f'H{row}'].value, 5 if sentence_branch else None)
            self.assertEqual(sheet[f'K{row}'].value, 1)
            self.assertEqual(sheet[f'L{row}'].value, 0)
            self.assertEqual(sheet[f'M{row}'].value, 0 if index == 0 else 48)
            self.assertEqual(sheet[f'O{row}'].value, 0)
            self.assertEqual(sheet[f'N{row}'].value, 1)
            self.assertEqual(sheet[f'R{row}'].value, 0 if index == 0 else 3)
            self.assertEqual(sheet[f'S{row}'].value, 3)
            self.assertTrue(sheet[f'U{row}'].value)
            self.assertIn(f'M{row}<>""', sheet[f'Q{row}'].value)
            self.assertNotIn(f'M{row}>0', sheet[f'Q{row}'].value)
        self.assertEqual(exported_names, {f'{index:02d} Learner' for index in range(12)})
        self.assertEqual(Assessment.objects.filter(student__in=students, material=self.material).count(), 12)

    def test_end_reads_latest_completed_snapshot_and_accepts_zero_progress(self):
        student = self.make_user('zero')
        self.section.add_student(student)
        session = LiveAssessmentSession.objects.create(id='live-export-latest', teacher=self.teacher,
            section=self.section, material=self.material, student_ids=[student.id], student_count=1,
            status='started', start_at=timezone.now(), student_states={str(student.id): {'status': 'reading'}})
        # The teacher's Python object predates this acknowledged student write.
        evidence = {'stage': 'completed', 'temporary_completed': True, 'task1_score': 0,
            'task2_type': 'Task 2L / Rhymes', 'task2_rhymes_score': 0, 'part1_total_score': 0,
            'learner_experience_rating': 3}
        LiveAssessmentSession.objects.filter(pk=session.pk).update(student_states={str(student.id): {
            'status': 'completed', 'progress': 0, 'elapsed_seconds': 0, 'recovery_state': evidence}})
        _end_live_assessment_session(session)
        result = latest_completed_official_crla_results([student.id])[student.id]
        self.assertEqual(result.crla_score_data['task1_score'], 0)
        self.assertEqual(result.crla_score_data['task2_rhymes_score'], 0)
        self.assertEqual(result.crla_classification, 'Low Emerging Reader')

    def test_failed_result_save_does_not_end_session_or_erase_student_evidence(self):
        student = self.make_user('failure')
        self.section.add_student(student)
        states = {str(student.id): {'status': 'completed', 'progress': 1, 'recovery_state': {
            'stage': 'completed', 'temporary_completed': True, 'task1_score': 4,
            'part1_total_score': 4, 'learner_experience_rating': 3}}}
        session = LiveAssessmentSession.objects.create(id='live-export-failure', teacher=self.teacher,
            section=self.section, material=self.material, student_ids=[student.id], student_count=1,
            status='started', start_at=timezone.now(), student_states=states)
        with patch('pabasa_app.views._complete_assessment_for_student', return_value=JsonResponse({'success': False}, status=403)):
            with self.assertRaises(ValueError):
                _end_live_assessment_session(session)
        session.refresh_from_db()
        self.assertEqual(session.status, 'started')
        self.assertEqual(session.student_states, states)
        self.assertIsNone(session.ends_at)

    def test_final_payload_keeps_completion_evidence_when_recovery_is_partial(self):
        session = SimpleNamespace(id='live-export-partial', material=self.material)
        payload = _build_live_session_completion_payload(session, None, {
            'completion_payload': {'crla_score_data': {'task1_score': 8, 'words_read': 48, 'story_number': 1}},
            'recovery_state': {'task1_score': None, 'words_read': None, 'story_number': None},
        })
        self.assertEqual(payload['crla_score_data']['task1_score'], 8)
        self.assertEqual(payload['crla_score_data']['words_read'], 48)
        self.assertEqual(payload['assessment_type'], 'paragraph')

    def test_later_student_save_failure_rolls_back_batch_finalization(self):
        students = [self.make_user('first-save'), self.make_user('second-save')]
        states = {}
        for student in students:
            self.section.add_student(student)
            states[str(student.id)] = {'status': 'completed', 'progress': 1, 'recovery_state': {
                'stage': 'completed', 'temporary_completed': True, 'task1_score': 4,
                'task2_type': 'Task 2L / Rhymes', 'task2_rhymes_score': 2,
                'part1_total_score': 6, 'learner_experience_rating': 3,
            }}
        session = LiveAssessmentSession.objects.create(id='live-export-rollback', teacher=self.teacher,
            section=self.section, material=self.material, student_ids=[student.id for student in students],
            student_count=2, status='started', start_at=timezone.now(), student_states=states)
        saved_students = []

        def save_result(student, **kwargs):
            if student.pk == students[1].pk:
                return JsonResponse({'success': False}, status=500)
            response = _complete_assessment_for_student(student, **kwargs)
            self.assertEqual(response.status_code, 200)
            saved_students.append(student.pk)
            return response

        with patch('pabasa_app.views._complete_assessment_for_student', side_effect=save_result):
            with self.assertRaises(ValueError):
                _end_live_assessment_session(session)
        self.assertEqual(saved_students, [students[0].pk])
        self.assertFalse(Assessment.objects.filter(student__in=students, material=self.material).exists())
        session.refresh_from_db()
        self.assertEqual(session.status, 'started')
        self.assertEqual(session.student_states, states)
        self.assertIsNone(session.ends_at)
