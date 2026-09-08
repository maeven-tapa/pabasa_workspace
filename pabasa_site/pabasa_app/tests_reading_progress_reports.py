from io import BytesIO
from datetime import timedelta
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from unittest.mock import patch

from .aral_activity_catalog import resolve_activity
from .models import Assessment, Course, Enrollment, Material, Note, School, Section, StoryReadingProgress, StoryResponseSubmission, User
from .reading_progress_reports import FINALIZED_CRLA_REMARK, build_student_reading_progress_report
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
        self.assertIn('STUDENT READING PROGRESS REPORT', text)
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
