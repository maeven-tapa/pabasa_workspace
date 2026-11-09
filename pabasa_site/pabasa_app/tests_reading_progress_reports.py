from io import BytesIO
from datetime import timedelta
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from unittest.mock import patch

from .aral_activity_catalog import resolve_activity
from .models import Assessment, CalendarEvent, Course, Enrollment, Material, Note, School, SchoolCalendar, Section, StoryReadingProgress, StoryResponseSubmission, StudentActivityProgress, StudentActivityRecordingSubmission, User
from .reading_progress_reports import FINALIZED_CRLA_REMARK, build_student_reading_progress_report
from .reading_report_details import SINGLE_CRLA_PERIOD_NOTICE, collect_workbook_performance, summarize_workbook_progress
from .system_clock import today as system_today
from .views import _build_reading_report_pdf


class ReadingProgressReportTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(custom_id='TCH-RPT', role='teacher', first_name='Report', last_name='Teacher', email='teacher-report@example.com', sex='female', birth_month=1, birth_day=1, birth_year=1990)
        self.student = User.objects.create(custom_id='STD-RPT', role='student', first_name='Reading', last_name='Student', email='student-report@example.com', grade_level='Grade 2', sex='male', birth_month=1, birth_day=1, birth_year=2015)
        school = School.objects.create(name='Report School', code='RPT-SCHOOL')
        self.section = Section.objects.create(school=school, teacher=self.teacher, class_name='Rizal', class_code='RPT-101', subject='Reading')
        Enrollment.objects.create(student=self.student, section=self.section, assigned_teacher=self.teacher, is_active=True)
        self.course = Course.objects.create(teacher=self.teacher, title='Reading', code='CRS-RPT')
        self.course.sections.add(self.section)

    def material(self, activity_type, week=1):
        return Material.objects.create(teacher=self.teacher, section=self.section, title=activity_type, code=f'M-{activity_type}-{week}', item_type='word', content_json={'activity_type': activity_type}, assigned_week=week)

    def completed_activity(self, material, **values):
        return Assessment.objects.create(teacher=self.teacher, section=self.section, material=material, student=self.student, title=material.title, code=f'A-{material.id}', assessment_type='word', attempt_status='completed', completed_at=timezone.now(), is_active=True, **values)

    def set_reporting_year(self):
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=2)
        self.section.school_calendar = calendar
        self.section.save(update_fields=['school_calendar'])
        Enrollment.objects.filter(student=self.student, section=self.section).update(school_calendar=calendar)
        return calendar

    def activate_reporting_term(self, calendar, term=2):
        today = system_today()
        CalendarEvent.objects.create(school_calendar=calendar, term=term, title='Opening',
            event_type='school_opening', start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=5), is_published=True)
        CalendarEvent.objects.create(school_calendar=calendar, term=term, title='Closing',
            event_type='school_closing', start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=10), is_published=True)

    def report(self):
        return build_student_reading_progress_report(self.student, sections=[self.section], course=self.course)

    def official_result(self, code, key=None, **overrides):
        from .views import _calendar_current_term
        term = _calendar_current_term(self.section.school_calendar) if self.section.school_calendar_id else None
        key = key or {1: 'bosy_crla_pretest', 2: 'midline_crla_midtest', 3: 'eosy_crla_posttest'}.get(term, 'bosy_crla_pretest')
        values = dict(teacher=self.teacher, section=self.section, student=self.student,
                      enrollment=Enrollment.objects.get(student=self.student, section=self.section),
                      title=code, code=code, assessment_type='paragraph', system_assessment_key=key,
                      attempt_status='completed', completed_at=timezone.now(),
                      crla_classification='Developing Reader', accuracy=80, wpm=40)
        values.update(overrides)
        return Assessment.objects.create(**values)

    def pdf_text(self, report=None):
        return '\n'.join(page.extract_text() or '' for page in PdfReader(
            BytesIO(_build_reading_report_pdf(report or self.report()))).pages)

    def test_history_selects_latest_per_period_and_preserves_zero_comprehension(self):
        self.set_reporting_year()
        self.official_result('BOSY-OLD', completed_at=timezone.now() - timedelta(days=10))
        latest = self.official_result('BOSY-NEW', crla_score_data={'comprehension_correct': 0, 'comprehension_total': 5})
        self.official_result('MID', 'midline_crla_midtest')
        self.official_result('EOSY', 'eosy_crla_posttest', accuracy=None, wpm=None)
        report = self.report()
        rows = report['crla_history']['rows']
        self.assertEqual([row['period'] for row in rows], ['BoSY', 'Midline', 'EoSY'])
        self.assertEqual(rows[0]['assessment_id'], latest.pk)
        self.assertEqual(rows[0]['comprehension'], '0/5 correct')
        self.assertNotIn('message', report['crla_history'])
        self.assertIn('0/5 correct', self.pdf_text(report))

    def test_history_excludes_other_students_years_review_and_no_submission(self):
        calendar = self.set_reporting_year()
        kept = self.official_result('VALID')
        old_year = SchoolCalendar.objects.create(school_year='2025-2026', current_term=1)
        old_section = Section.objects.create(school=self.section.school, teacher=self.teacher,
            school_calendar=old_year, class_name='Old', class_code='OLD-HISTORY', subject='Reading')
        self.official_result('OLD-YEAR', 'midline_crla_midtest', enrollment=None, section=old_section)
        self.official_result('REVIEW', 'midline_crla_midtest', needs_manual_review=True)
        self.official_result('UNSUBMITTED', 'eosy_crla_posttest', remarks=FINALIZED_CRLA_REMARK)
        self.official_result('WRONG-STUDENT', 'midline_crla_midtest', student=None)
        self.official_result('CONFLICTING-YEAR', 'midline_crla_midtest', section=old_section)
        report = self.report()
        self.assertEqual([row['assessment_id'] for row in report['crla_history']['rows']], [kept.pk])
        self.assertEqual(report['crla_history']['school_year'], calendar.school_year)
        self.assertEqual(report['crla_history']['message'], SINGLE_CRLA_PERIOD_NOTICE)
        self.assertIn(SINGLE_CRLA_PERIOD_NOTICE, self.pdf_text(report).replace('\n', ' '))

    def test_history_requires_verified_year_and_does_not_change_existing_crla(self):
        result = self.official_result('UNSCOPED')
        report = self.report()
        self.assertEqual(report['crla']['assessment_id'], result.pk)
        self.assertEqual(report['crla_history']['rows'], [])
        self.assertIn('could not be verified', report['crla_history']['message'])
        self.set_reporting_year()
        Assessment.objects.filter(pk=result.pk).update(section=None, enrollment=None)
        self.assertEqual(self.report()['crla_history']['rows'], [])

    def test_workbook_merges_progress_recordings_aliases_and_keeps_terms_separate(self):
        calendar = self.set_reporting_year()
        for key in ['lesson-4-gawain-2', 'session-2-lesson-4-gawain-2']:
            StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
                term=1, activity_key=key, completed_items=6, correct_items=6, total_items=6,
                activity_completed=True)
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='session-2-lesson-4-gawain-2', completed_items=2, total_items=6)
        for index, status, score in [(0, 'checked', 0), (1, 'submitted', None), (2, 'retry', None)]:
            StudentActivityRecordingSubmission.objects.create(student=self.student, school_calendar=calendar,
                term=2, activity_key='session-2-lesson-4-gawain-2', item_index=index,
                audio_file=f'test-only/item-{index}.webm', status=status, teacher_score=score)
        report = self.report()
        self.assertEqual(len(report['workbook']['rows']), 2)
        self.assertEqual(report['workbook']['completed_count'], 1)
        self.assertEqual(report['workbook']['ongoing_count'], 1)
        current = report['workbook']['rows'][1]
        self.assertEqual(current['completion_percent'], 33.3)
        self.assertIn('Teacher score: 0/1 reviewed recording items', current['results'])
        self.assertIn('1 submitted; awaiting teacher review', current['review_status'])
        self.assertIn('1 retry requested', current['review_status'])
        self.assertEqual(current['session'], 2)
        self.assertEqual(current['gawain'], 2)
        summary = summarize_workbook_progress(report['workbook'])
        self.assertEqual([period['term'] for period in summary['periods']], [1, 2])
        self.assertEqual(summary['periods'][0]['completed'], 1)
        self.assertEqual(summary['periods'][1]['ongoing'], 1)
        self.assertEqual(summary['periods'][1]['recordings_reviewed'], 1)
        self.assertEqual(summary['periods'][1]['recordings_pending'], 1)
        self.assertEqual(summary['periods'][1]['recordings_retry'], 1)

    def test_workbook_labels_unverified_period_and_avoids_invalid_percentages(self):
        calendar = self.set_reporting_year()
        old_calendar = SchoolCalendar.objects.create(school_year='2025-2026', current_term=1)
        StudentActivityProgress.objects.create(student=self.student, school_calendar=old_calendar,
            term=1, activity_key='lesson-1-gawain-1', activity_completed=True)
        StudentActivityProgress.objects.create(student=self.student, activity_key='aral-l24-g4-x-syllable-builder',
            completed_items=3, correct_items=3, total_items=0)
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='aral-s9-a1-family-drawing', activity_completed=True,
            completed_items=1, total_items=1, state={'submitted': True, 'pending_review': True})
        rows = self.report()['workbook']['rows']
        self.assertEqual(len(rows), 2)
        unverified = next(row for row in rows if not row['period_verified'])
        self.assertIsNone(unverified['completion_percent'])
        self.assertIn('unverified', unverified['period'])
        pending = next(row for row in rows if row['period_verified'])
        self.assertFalse(pending['completed'])
        self.assertEqual(pending['review_status'], 'Pending teacher review')
        self.assertEqual(pending['results'], [])
        summary = summarize_workbook_progress(self.report()['workbook'])
        self.assertEqual(summary['excluded_count'], 1)
        self.assertEqual(len(summary['periods']), 1)
        self.assertEqual(summary['periods'][0]['awaiting_review'], 1)

    def test_workbook_uses_answer_evidence_and_teacher_verdict_without_inventing_grades(self):
        calendar = self.set_reporting_year()
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-15-gawain-1', completed_items=2, total_items=5,
            state={'answer_records': [{'correct': False}, {'correct': True}]})
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='aral-s9-a1-family-drawing', completed_items=1, total_items=1,
            activity_completed=True, state={'checked': True})
        rows = self.report()['workbook']['rows']
        answers = next(row for row in rows if row['activity_key'] == 'lesson-15-gawain-1')
        self.assertEqual(answers['results'], ['Submitted answers: 1/2 correct'])
        checked = next(row for row in rows if row['activity_key'] == 'aral-s9-a1-family-drawing')
        self.assertEqual(checked['review_status'], 'Teacher checked')
        self.assertEqual(checked['results'], [])

    def test_workbook_recording_only_does_not_imply_activity_completion(self):
        self.set_reporting_year()
        StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key='session-5-lesson-14-gawain-4', item_index=0,
            audio_file='test-only/pending.webm', review_status='pending')
        row = self.report()['workbook']['rows'][0]
        self.assertFalse(row['completed'])
        self.assertIsNone(row['completion_percent'])
        self.assertIn('completion not recorded', row['completion_status'])
        self.assertIn('pending teacher review', row['review_status'])
        self.assertEqual(row['results'], [])

    def test_new_sections_do_not_include_another_students_records(self):
        calendar = self.set_reporting_year()
        other = User.objects.create(custom_id='RPT-OTHER-STUDENT', role='student',
            first_name='Other', last_name='Learner', sex='female', birth_month=1, birth_day=1,
            birth_year=2015, email='other-learner@example.com')
        self.official_result('OTHER-RESULT', student=other, enrollment=None)
        StudentActivityProgress.objects.create(student=other, school_calendar=calendar,
            term=2, activity_key='lesson-1-gawain-1', activity_completed=True)
        StudentActivityRecordingSubmission.objects.create(student=other,
            school_calendar=calendar, term=2, activity_key='lesson-1-gawain-1',
            audio_file='test-only/other.webm', status='checked', teacher_score=1)
        report = self.report()
        self.assertEqual(report['workbook']['rows'], [])
        self.assertEqual(report['crla_history']['rows'], [])

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_preview_and_send_both_include_saved_workbook_and_history(self, email_cls):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('SHARED-REPORT', crla_score_data={'comprehension_correct': 3, 'comprehension_total': 5})
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-15-gawain-1', completed_items=2, total_items=5,
            state={'answer_records': [{'correct': True}, {'correct': True}]})
        session = self.client.session
        session.update({'user_id': self.teacher.id, 'user_role': 'teacher'})
        session.save()
        preview = self.client.get(reverse('preview_course_reading_report'),
            {'course_id': self.course.id, 'student_id': self.student.id})
        self.assertEqual(preview.status_code, 200)
        for update_type in ['general', 'followup']:
            response = self.send_section_update(update_type=update_type)
            self.assertEqual(response.status_code, 200)
            sent_pdf = email_cls.return_value.attach.call_args.args[1]
            for payload in [preview.content, sent_pdf]:
                text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(payload)).pages)
                self.assertIn('CRLA PROGRESS HISTORY', text)
                self.assertIn('3/5 correct', text)
                self.assertIn('ARAL WORKBOOK PERFORMANCE', text)
                self.assertIn('Submitted answers: 2/2 correct', text)
                self.assertIn('Continue Session 5, Lesson 15, Gawain 1', ' '.join(text.split()))
                self.assertIn('Prescribed ARAL Workbook', text)
                self.assertIn('Ongoing: 1', text)
                self.assertIn('P1 Continue Session 5, Lesson 15, Gawain 1', ' '.join(text.split()))

    def test_workbook_recommendations_use_dated_term_and_collect_only_once(self):
        calendar = self.set_reporting_year()
        calendar.current_term = 1  # The actual dated block, not this display field, wins.
        calendar.save(update_fields=['current_term'])
        self.activate_reporting_term(calendar, term=2)
        self.official_result('RECO-BASELINE')
        for term, completed, answers in [(1, False, [{'correct': False}]),
                                         (2, True, [{'correct': True}])]:
            StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
                term=term, activity_key='lesson-15-gawain-1', completed_items=1, total_items=1,
                activity_completed=completed, state={'answer_records': answers})
        with patch('pabasa_app.reading_progress_reports.collect_workbook_performance',
                   wraps=collect_workbook_performance) as collector:
            report = self.report()
        collector.assert_called_once()
        self.assertEqual(len(report['workbook']['rows']), 2)
        self.assertEqual(report['workbook']['current_term'], 2)
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])
        self.assertIn('1 of 93 prescribed activities', report['recommendations'][0])
        self.assertNotIn('Practice the items needing support', report['recommendations'][0])
        self.assertEqual(report['recommendations'], [item['text'] for item in report['recommendation_details']])

    def test_table_11_tests_one_and_five_have_p1_despite_perfect_supplementary(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('TABLE-11-BASELINE')
        for activity in ['word_meaning_match', 'clap_count_syllables']:
            self.completed_activity(self.material(activity), total_score=100, accuracy=100)
        progress = StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-1-gawain-1', activity_completed=True,
            completed_items=1, total_items=1)
        for test_number, completed_count in [(1, 1), (5, 3)]:
            with self.subTest(test_number=test_number):
                if test_number == 5:
                    progress.activity_key = 'lesson-4-gawain-1'
                    progress.save(update_fields=['activity_key'])
                    for key in ['lesson-6-gawain-1', 'lesson-7-gawain-1']:
                        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
                            term=2, activity_key=key, activity_completed=True)
                before = StudentActivityProgress.objects.filter(student=self.student).count()
                report = self.report()
                self.assertEqual(StudentActivityProgress.objects.filter(student=self.student).count(), before,
                                 'Reporting must not create unstarted activity records.')
                self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])
                program = report['workbook']['program']
                self.assertTrue(program['verified'])
                self.assertEqual(program['total_count'], 93)
                self.assertEqual(program['completed_count'], completed_count)
                self.assertEqual(len(program['unrecorded_activity_keys']), 93 - completed_count)
                self.assertIn(f'{completed_count} of 93 prescribed activities', self.pdf_text(report))

    def test_verified_eligible_student_with_no_workbook_records_still_needs_to_continue(self):
        from .prescribed_test_fixtures import prescribed_term_fixture
        prescribed_term_fixture(self.student, teacher=self.teacher, section=self.section,
                                term=2, today=system_today())
        self.completed_activity(self.material('word_meaning_match'), accuracy=100)
        report = self.report()
        self.assertEqual(report['workbook']['rows'], [])
        self.assertTrue(report['workbook']['program']['verified'])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])
        self.assertIn('0 of 93 prescribed activities', report['recommendations'][0])

    def test_grade_level_student_is_not_assigned_the_entire_workbook_by_reporting(self):
        from .prescribed_test_fixtures import prescribed_term_fixture
        calendar, _section, _enrollment, _result = prescribed_term_fixture(
            self.student, teacher=self.teacher, section=self.section, term=2,
            today=system_today(), classification='Reading At Grade Level')
        self.completed_activity(self.material('word_meaning_match'), accuracy=100)
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-1-gawain-1', activity_completed=True)
        report = self.report()
        self.assertFalse(report['workbook']['program']['verified'])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P5'])
        self.assertIn('Practice Mode', report['recommendations'][0])
        self.assertEqual(len(report['workbook']['rows']), 1)
        self.assertEqual(len(report['aral_activities']), 1)

    def test_no_official_result_has_only_p0_and_keeps_saved_activity_information(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-1-gawain-1', completed_items=1, total_items=5)
        self.completed_activity(self.material('word_meaning_match'), accuracy=0)
        report = self.report()
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P0'])
        self.assertEqual(len(report['workbook']['rows']), 1)
        self.assertEqual(len(report['aral_activities']), 1)
        self.assertIn('for Midline, school year 2026-2027', report['recommendations'][0])
        text = ' '.join(self.pdf_text(report).split())
        self.assertIn('P0 An official CRLA result', text)
        self.assertNotIn('Continue assigned ARAL', text)

    def test_prior_period_grade_level_does_not_replace_missing_current_crla(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        prior = self.official_result('PRIOR-GRADE-LEVEL', 'bosy_crla_pretest',
                                     crla_classification='Reading At Grade Level')
        report = self.report()
        self.assertEqual(report['crla']['assessment_id'], prior.pk, 'Preserve the existing CRLA section.')
        self.assertFalse(report['recommendation_crla']['available'])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P0'])
        self.official_result('CURRENT-DEVELOPING', 'midline_crla_midtest',
                             crla_classification='Developing Reader')
        self.assertEqual([item['code'] for item in self.report()['recommendation_details']], ['P1'])

    def test_prior_school_year_grade_level_cannot_supply_current_p5(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        old_calendar = SchoolCalendar.objects.create(school_year='2025-2026', current_term=2, is_active=False)
        old_section = Section.objects.create(school=self.section.school, teacher=self.teacher,
            school_calendar=old_calendar, class_name='Previous', class_code='P5-OLD', subject='Reading')
        self.official_result('OLD-GRADE-LEVEL', 'midline_crla_midtest', enrollment=None,
                             section=old_section, crla_classification='Reading At Grade Level')
        self.assertEqual([item['code'] for item in self.report()['recommendation_details']], ['P0'])

    def test_unreviewed_or_unsubmitted_crla_does_not_establish_p5_or_aral_advice(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('PENDING-GRADE-LEVEL', crla_classification='Reading At Grade Level',
                             needs_manual_review=True)
        self.assertEqual([item['code'] for item in self.report()['recommendation_details']], ['P0'])
        self.official_result('FINALIZED-NO-SUBMISSION', crla_classification='Low Emerging Reader',
                             total_score=0, remarks=FINALIZED_CRLA_REMARK)
        report = self.report()
        self.assertTrue(report['crla']['finalized_without_submission'])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P0'])

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_preview_and_send_display_p0_and_p5_with_their_actual_messages(self, email_cls):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        for code in ['P0', 'P5']:
            with self.subTest(code=code):
                if code == 'P5':
                    self.official_result('GRADE-LEVEL-SEND', crla_classification='Readers at Grade Level')
                self.send_section_update()
                sent_pdf = email_cls.return_value.attach.call_args.args[1]
                preview = self.client.get(reverse('preview_course_reading_report'),
                    {'course_id': self.course.id, 'student_id': self.student.id})
                self.assertEqual(preview.status_code, 200)
                for payload in [sent_pdf, preview.content]:
                    text = ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(BytesIO(payload)).pages).split())
                    actions = text.split('09 NEXT STEPS', 1)[1]
                    self.assertNotIn('Continue assigned ARAL', actions)
                    self.assertIn('P0 An official CRLA result' if code == 'P0' else "P5 Your child's official CRLA classification", actions)
                    if code == 'P5':
                        self.assertIn('using Practice Mode', actions)
                    else:
                        self.assertIn('may use Practice Mode', actions)

    def test_completing_the_whole_current_program_allows_p4_without_supplementary(self):
        from .views import _prescribed_activity_order
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('WHOLE-WORKBOOK')
        StudentActivityProgress.objects.bulk_create([
            StudentActivityProgress(student=self.student, school_calendar=calendar, term=2,
                activity_key=key, activity_completed=True) for key in _prescribed_activity_order()])
        report = self.report()
        self.assertEqual(report['workbook']['program']['completed_count'], 93)
        self.assertEqual(report['workbook']['program']['remaining_activity_keys'], [])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P4'])

    def test_workbook_reviewed_zero_and_pending_recordings_have_separate_evidence(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('RECO-ORAL')
        key = 'session-5-lesson-14-gawain-4'
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key=key, activity_completed=True, completed_items=2, total_items=2)
        reviewed = StudentActivityRecordingSubmission.objects.create(student=self.student,
            school_calendar=calendar, term=2, activity_key=key, item_index=0,
            audio_file='test-only/reviewed.webm', status='checked', review_status='reviewed',
            teacher_score=0, checked_by=self.teacher, checked_at=timezone.now())
        pending = StudentActivityRecordingSubmission.objects.create(student=self.student,
            school_calendar=calendar, term=2, activity_key=key, item_index=1,
            audio_file='test-only/pending.webm', status='submitted', review_status='pending', teacher_score=0)
        report = self.report()
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1', 'P2', 'P3'])
        p2 = report['recommendation_details'][1]
        self.assertEqual([item['record_id'] for item in p2['evidence']], [reviewed.pk])
        facts = report['workbook']['rows'][0]['evidence']
        pending_fact = next(item for item in facts['recordings'] if item['submission_id'] == pending.pk)
        self.assertIsNone(pending_fact['teacher_score'])
        self.assertNotIn('automated', report['recommendations'][-1])
        self.assertNotIn('WPM', report['recommendations'][-1])

    def test_workbook_ongoing_counts_do_not_invent_low_accuracy(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('RECO-ONGOING')
        progress = StudentActivityProgress.objects.create(student=self.student,
            school_calendar=calendar, term=2, activity_key='lesson-15-gawain-1',
            completed_items=2, total_items=6, correct_items=0)
        self.assertEqual([item['code'] for item in self.report()['recommendation_details']], ['P1'])
        progress.state = {'answer_records': [{'item_id': 'word-1', 'correct': False}]}
        progress.save(update_fields=['state'])
        report = self.report()
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1', 'P2'])
        self.assertEqual(report['recommendation_details'][1]['evidence'][0]['record_id'], progress.pk)

    def test_workbook_pending_drawing_is_not_a_failed_answer_or_oral_reading_result(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('RECO-DRAWING')
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='aral-s9-a1-family-drawing', activity_completed=False,
            state={'pending_review': True, 'answer_records': [{'correct': False}]})
        StudentActivityRecordingSubmission.objects.create(student=self.student,
            school_calendar=calendar, term=2, activity_key='aral-s9-a1-family-drawing',
            audio_file='test-only/drawing.webm', review_status='pending')
        report = self.report()
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])
        self.assertEqual(report['workbook']['rows'][0]['evidence']['scored_answers'], [])
        self.assertFalse(report['workbook']['rows'][0]['evidence']['oral_reading'])

    def test_unverified_workbook_records_stay_visible_but_do_not_drive_current_advice(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        self.official_result('RECO-UNVERIFIED')
        StudentActivityProgress.objects.create(student=self.student,
            activity_key='lesson-15-gawain-1', activity_completed=True,
            state={'answer_records': [{'correct': False}]})
        report = self.report()
        self.assertEqual(len(report['workbook']['rows']), 1)
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])
        self.assertIsNone(report['recommendation_details'][0]['activity'])

    def test_workbook_without_active_term_does_not_infer_one_from_saved_rows(self):
        calendar = self.set_reporting_year()
        self.official_result('RECO-NO-TERM')
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=calendar.current_term, activity_key='lesson-15-gawain-1', activity_completed=True,
            state={'answer_records': [{'correct': False}]})
        report = self.report()
        self.assertIsNone(report['workbook']['current_term'])
        self.assertEqual([item['code'] for item in report['recommendation_details']], ['P1'])

    def test_inactive_calendar_cannot_drive_current_workbook_advice(self):
        calendar = self.set_reporting_year()
        self.activate_reporting_term(calendar)
        calendar.is_active = False
        calendar.save(update_fields=['is_active'])
        self.section.refresh_from_db()
        self.official_result('RECO-INACTIVE')
        StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=2, activity_key='lesson-15-gawain-1', activity_completed=True,
            state={'answer_records': [{'correct': False}]})
        self.assertEqual([item['code'] for item in self.report()['recommendation_details']], ['P1'])

    def test_pdf_new_section_order_and_empty_states_preserve_existing_sections(self):
        text = self.pdf_text()
        sections = ['STUDENT INFORMATION', 'CRLA INITIAL ASSESSMENT', 'CRLA PROGRESS HISTORY',
                    'SUPPLEMENTARY ARAL ACTIVITIES', 'ARAL WORKBOOK PERFORMANCE',
                    'READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', 'READING PROGRESS', "TEACHER'S NOTE", 'NEXT STEPS']
        positions = [text.index('\n' + section + '\n') for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('No workbook progress or recording submissions', text)
        self.assertIn('provide targeted reading support', text.replace('\n', ' '))
        self.assertNotIn('ARAL INTERVENTION', text)

    def test_pdf_long_workbook_table_paginates_and_repeats_headers(self):
        report = self.report()
        from .prescribed_activity_catalog import PRESCRIBED_ACTIVITIES
        for key in list(PRESCRIBED_ACTIVITIES)[:32]:
            StudentActivityProgress.objects.create(student=self.student, activity_key=key,
                completed_items=1, total_items=3)
        report = self.report()
        pdf = PdfReader(BytesIO(_build_reading_report_pdf(report)))
        self.assertGreater(len(pdf.pages), 2)
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
        self.assertGreater(text.count('Results / teacher review'), 1)
        for item in report['workbook']['rows']:
            self.assertIn(item['title'], text.replace('\n', ' '))
        self.assertIn('NEXT STEPS', text)

    def test_collector_uses_latest_official_crla_and_completed_aral_only(self):
        Assessment.objects.create(teacher=self.teacher, section=self.section, student=self.student, title='Old CRLA', code='CRLA-OLD', assessment_type='paragraph', system_assessment_key='bosy_crla_pretest', attempt_status='completed', completed_at=timezone.now() - timedelta(days=2), crla_classification='Low Emerging Reader', total_score=4)
        Assessment.objects.create(teacher=self.teacher, section=self.section, student=self.student, title='Midline CRLA', code='CRLA-MID', assessment_type='paragraph', system_assessment_key='midline_crla_midtest', system_assessment_period='Midline', attempt_status='completed', completed_at=timezone.now(), crla_classification='Developing Reader', total_score=8, accuracy=85, wpm=44, crla_score_data={'story_number': 2, 'correct_answers': 3})
        picture = self.material('picture_word_matching', 3)
        self.completed_activity(picture, total_score=7, accuracy=70, correct_items=7, items_completed=10)
        incomplete = self.material('sound_detective', 4)
        Assessment.objects.create(teacher=self.teacher, section=self.section, material=incomplete, student=self.student, title='Incomplete', code='A-INCOMPLETE', assessment_type='word', attempt_status='started', is_active=True)
        report = build_student_reading_progress_report(self.student, sections=[self.section], course=self.course)
        self.assertEqual(report['crla']['assessment_title'], 'Midline CRLA')
        self.assertEqual(report['crla']['reading_profile'], 'Developing Reader')
        self.assertEqual(report['crla']['part2_results']['story_number'], 2)
        self.assertEqual([row['activity_id'] for row in report['aral_activities']], ['picture_word_matching'])
        competencies = {row['name']: row['completed_count'] for row in report['competencies']}
        self.assertEqual(competencies['Phonics'], 1)
        self.assertEqual(competencies['Vocabulary'], 1)
        self.assertEqual(competencies['Oral Language'], 0)

    def test_skills_summary_excludes_workbook_crla_and_unperformed_supplementary_activities(self):
        picture = self.material('picture_word_matching', 3)
        self.completed_activity(picture, accuracy=70)
        self.material('sound_detective', 4)  # Assigned content alone is not practice evidence.
        workbook = self.material('aral-l22-g2-c-word-reading', 5)
        self.completed_activity(workbook, accuracy=95)
        crla = self.material('reading_practice', 6)
        crla.assessment_kind = 'crla'
        crla.save(update_fields=['assessment_kind'])
        self.completed_activity(crla, accuracy=80)
        report = self.report()
        self.assertEqual(len(report['aral_activities']), 3, 'Keep the other report sections intact.')
        practiced = {item['name']: item['completed_count'] for item in report['competencies']}
        self.assertEqual(practiced['Phonics'], 1)
        self.assertEqual(practiced['Vocabulary'], 1)
        self.assertEqual(practiced['Fluency'], 0)
        self.assertEqual(practiced['Phonological Awareness'], 0)
        text = self.pdf_text(report)
        section = text.split('READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', 1)[1].split('READING PROGRESS', 1)[0]
        self.assertIn('Picture-Word Matching', section)
        self.assertNotIn('Fluency', section)
        self.assertNotIn('Phonological Awareness', section)

    def test_skills_summary_excludes_official_source_results_and_other_students(self):
        source = Assessment.objects.create(teacher=self.teacher, title='Official source',
            code='SKILL-CRLA-SOURCE', assessment_type='word', system_assessment_key='bosy_crla_pretest')
        reading = self.material('sentence_reading', 4)
        self.completed_activity(reading, source_assessment=source)
        other = User.objects.create(custom_id='SKILL-OTHER', role='student', first_name='Other',
            last_name='Learner', sex='female', birth_month=1, birth_day=1, birth_year=2015)
        retell = self.material('retell_story', 5)
        Assessment.objects.create(teacher=self.teacher, section=self.section, material=retell,
            student=other, title='Other response', code='SKILL-OTHER-RESULT', assessment_type='word',
            attempt_status='completed', completed_at=timezone.now())
        report = self.report()
        self.assertTrue(all(not item['activities'] for item in report['competencies']))
        self.assertEqual([item['activity_id'] for item in report['aral_activities']], ['sentence_reading'])

    def test_finalized_zero_provenance_and_story_rows_are_preserved(self):
        Assessment.objects.create(teacher=self.teacher, section=self.section, student=self.student, title='Final CRLA', code='CRLA-FINAL', assessment_type='paragraph', system_assessment_key='eosy_crla_posttest', attempt_status='completed', completed_at=timezone.now(), crla_classification='Low Emerging Reader', total_score=0, remarks=FINALIZED_CRLA_REMARK)
        story = self.material('story_reading', 5)
        StoryReadingProgress.objects.create(student=self.student, material=story, completed=True, completed_at=timezone.now(), total_words=20, correct_words=18, miscues=2, accuracy=90, wpm=50, reading_score=90, word_alignment=[{}])
        response = self.material('story_response', 6)
        StoryResponseSubmission.objects.create(student=self.student, material=response, status='pending')
        report = build_student_reading_progress_report(self.student, sections=[self.section], course=self.course)
        self.assertTrue(report['crla']['finalized_without_submission'])
        activities = {row['activity_id']: row for row in report['aral_activities']}
        self.assertEqual(activities['story_reading']['status'], 'completed')
        self.assertEqual(activities['story_response']['status'], 'pending')
        self.assertIn('Story Reading', [item['activity_name'] for item in next(row for row in report['competencies'] if row['name'] == 'Fluency')['activities']])
        self.assertIn('Story Response', [item['activity_name'] for item in next(row for row in report['competencies'] if row['name'] == 'Oral Language')['activities']])

    def test_catalog_mapping_and_pdf_sections(self):
        self.assertEqual(resolve_activity({'activity_slug': 'picture_word_matching'})[0], 'picture_word_matching')
        self.assertEqual(resolve_activity({'activity_type': '5w_story_questions'})[0], 'five_w_story_questions')
        report = build_student_reading_progress_report(self.student, sections=[self.section], course=self.course)
        report['crla'] = {'available': True, 'finalized_without_submission': True, 'assessment_period': 'Post', 'reading_profile': 'Low Emerging Reader', 'completed_at': timezone.now().isoformat(), 'total_score': 0, 'part2_results': {}}
        pdf = _build_reading_report_pdf(report, message='')
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(pdf)).pages)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn('STUDENT READING PROGRESS REPORT', ' '.join(text.split()))
        self.assertIn('No student submission was recorded', text)
        self.assertIn("TEACHER'S NOTE", text)
        self.assertNotIn('Mastered', text)

    def test_preview_requires_course_teacher_and_returns_pdf(self):
        session = self.client.session
        session['user_id'] = self.teacher.id
        session['user_role'] = 'teacher'
        session.save()
        response = self.client.get(reverse('preview_course_reading_report'), {'course_id': self.course.id, 'student_id': self.student.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        other = User.objects.create(custom_id='TCH-OTHER', role='teacher', first_name='Other', last_name='Teacher', email='other-report@example.com', sex='male', birth_month=1, birth_day=1, birth_year=1990)
        session['user_id'] = other.id
        session.save()
        self.assertEqual(self.client.get(reverse('preview_course_reading_report'), {'course_id': self.course.id, 'student_id': self.student.id}).status_code, 404)

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_regular_send_attaches_structured_pdf_and_records_blank_note(self, email_cls):
        session = self.client.session
        session['user_id'] = self.teacher.id
        session['user_role'] = 'teacher'
        session.save()
        response = self.client.post(reverse('send_course_update'), data=json.dumps({'course_id': self.course.id, 'student_ids': [self.student.id], 'update_type': 'general', 'message': ''}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['report_included'])
        attachment = email_cls.return_value.attach.call_args.args
        self.assertTrue(attachment[1].startswith(b'%PDF'))
        self.assertEqual(attachment[2], 'application/pdf')
        self.assertTrue(Note.objects.filter(teacher=self.teacher, student=self.student, note_type='course_update:general').exists())

    def send_section_update(self, **overrides):
        session = self.client.session
        session.update({'user_id': self.teacher.id, 'user_role': 'teacher'})
        session.save()
        payload = {'course_id': f'section-{self.section.id}',
                   'student_ids': [self.student.id], 'update_type': 'general', 'message': ''}
        payload.update(overrides)
        return self.client.post(reverse('send_course_update'), data=json.dumps(payload),
                                content_type='application/json')

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_section_updates_preserve_delivery_pdf_and_notice_behavior(self, email_cls):
        for update_type in ['general', 'followup', 'commendation', 'assessment']:
            with self.subTest(update_type=update_type):
                email_cls.reset_mock()
                response = self.send_section_update(update_type=update_type)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['sent_count'], 1)
                email_cls.return_value.send.assert_called_once()
                if update_type == 'assessment':
                    email_cls.return_value.attach.assert_not_called()
                else:
                    self.assertTrue(email_cls.return_value.attach.call_args.args[1].startswith(b'%PDF'))
                self.assertTrue(Note.objects.filter(
                    teacher=self.teacher, student=self.student,
                    note_type=f'course_update:{update_type}').exists())

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_section_update_rejects_other_teacher_inactive_and_invalid_sections(self, email_cls):
        for course_id in ['section-invalid', 'invalid']:
            self.assertEqual(self.send_section_update(course_id=course_id).status_code, 400)
        other = User.objects.create(custom_id='RPT-OTHER', role='teacher', first_name='Other',
            last_name='Teacher', email='other@example.com', sex='female',
            birth_month=1, birth_day=1, birth_year=1990)
        self.section.teacher = other
        self.section.save(update_fields=['teacher'])
        self.assertEqual(self.send_section_update().status_code, 404)
        self.section.teacher = self.teacher
        self.section.is_active = False
        self.section.save(update_fields=['teacher', 'is_active'])
        self.assertEqual(self.send_section_update().status_code, 404)
        email_cls.assert_not_called()

    @patch('pabasa_app.views.EmailMultiAlternatives')
    def test_section_update_rejects_unenrolled_and_skips_missing_email_students(self, email_cls):
        Enrollment.objects.filter(student=self.student).update(is_active=False, status='completed')
        response = self.send_section_update()
        # The endpoint's existing enrollment guard rejects before sending.
        self.assertEqual(response.status_code, 403)
        self.assertIn('actively enrolled', response.json()['error'])
        Enrollment.objects.filter(student=self.student).update(is_active=True, status='active')
        self.student.email = ''
        self.student.save(update_fields=['email'])
        response = self.send_section_update()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['skipped'][0]['reason'], 'missing_email')
        email_cls.assert_not_called()
