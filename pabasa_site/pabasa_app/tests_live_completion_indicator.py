from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from .models import Assessment, Material, School, SchoolCalendar, Section, User
from .views import (
    _official_crla_completed_result_for_material,
    _official_crla_completed_student_ids_for_material,
)


class LiveCompletionIndicatorTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Indicator School', code='INDICATOR')
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
        self.teacher = self.make_user('teacher', 'teacher')
        self.section = Section.objects.create(school=self.school, school_calendar=self.calendar,
            teacher=self.teacher, class_code='INDICATOR', class_name='Indicator Class')
        self.material = Material.objects.get(system_assessment_key='bosy_crla_pretest')

    def make_user(self, key, role='student'):
        return User.objects.create(custom_id='indicator-'+key, role=role,
            first_name='Synthetic', last_name='Indicator', middle_initial='', suffix='',
            sex='female', birth_month=1, birth_day=1, birth_year=2012,
            password_hash='unused', school_record=self.school)

    def student(self, key):
        student = self.make_user(key)
        self.section.add_student(student)
        return student

    def result(self, student, when, primary='Low Emerging Reader', legacy='', **extra):
        return Assessment.objects.create(student=student, teacher=self.teacher, material=self.material,
            code='IND-'+str(student.pk)+'-'+str(Assessment.objects.count()), title='Indicator Result',
            assessment_type='word', attempt_status='completed', completed_at=when,
            crla_classification=primary, classification=legacy, **extra)

    def assert_equivalent(self, students):
        expected = {s.pk for s in students if _official_crla_completed_result_for_material(s,self.material)}
        self.assertEqual(_official_crla_completed_student_ids_for_material(students,self.material),expected)
        return expected

    def test_calendar_boundaries_and_classification_precedence_match_result_selector(self):
        dates = [datetime(2026,5,31,23,59),datetime(2026,6,1),
                 datetime(2027,5,31,23,59),datetime(2027,6,1)]
        students = [self.student(str(i)) for i in range(8)]
        for student, when in zip(students,dates):
            self.result(student,timezone.make_aware(when))
        now=timezone.make_aware(datetime(2026,10,18))
        self.result(students[4],now,primary=' ',legacy='Low Emerging Reader')
        self.result(students[5],now,primary='',legacy='Legacy nonempty classification')
        self.result(students[6],now,primary='Existing noncanonical primary',legacy='')
        self.result(students[7],now,primary='',legacy='')
        self.assertEqual(self.assert_equivalent(students),{students[i].pk for i in (1,2,5,6)})

    def test_old_valid_result_does_not_rescue_current_unclassified_or_incomplete_result(self):
        student=self.student('old')
        self.result(student,timezone.make_aware(datetime(2025,10,18)))
        self.result(student,timezone.make_aware(datetime(2026,10,18)),primary='',legacy='')
        incomplete=self.result(student,timezone.make_aware(datetime(2026,10,18)))
        Assessment.objects.filter(pk=incomplete.pk).update(attempt_status='in_progress')
        self.assertEqual(self.assert_equivalent([student]),set())

    def test_each_student_keeps_their_enrolled_calendar_and_material_boundary(self):
        current=self.student('current-calendar')
        prior=self.make_user('prior-calendar')
        calendar=SchoolCalendar.objects.create(school_year='2025-2026',current_term=1,is_active=False)
        section=Section.objects.create(school=self.school,school_calendar=calendar,teacher=self.teacher,
            class_code='INDICATOR-OLD',class_name='Prior Indicator Class')
        section.add_student(prior)
        self.result(current,timezone.make_aware(datetime(2025,10,18)))
        self.result(prior,timezone.make_aware(datetime(2025,10,18)))
        foreign=self.student('other-material')
        result=self.result(foreign,timezone.make_aware(datetime(2026,10,18)))
        Assessment.objects.filter(pk=result.pk).update(material=None)
        self.assertEqual(self.assert_equivalent([current,prior,foreign]),{prior.pk})

    def test_thirty_results_read_scalar_fields_without_per_student_result_queries(self):
        students=[self.student('roster-'+str(i)) for i in range(30)]
        now=timezone.make_aware(datetime(2026,10,18))
        for student in students:self.result(student,now)
        students=list(User.objects.filter(pk__in=[s.pk for s in students]).select_related('school_record'))
        with self.assertNumQueries(32):
            self.assertEqual(_official_crla_completed_student_ids_for_material(students,self.material),{s.pk for s in students})

    def test_empty_or_unfinished_roster_does_not_resolve_thirty_calendars(self):
        students=[self.student('unfinished-'+str(i)) for i in range(30)]
        with self.assertNumQueries(1):
            self.assertEqual(_official_crla_completed_student_ids_for_material(students,self.material),set())
        self.assertEqual(_official_crla_completed_student_ids_for_material([],self.material),set())
        self.assertEqual(_official_crla_completed_student_ids_for_material(students,None),set())
