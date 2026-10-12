"""Section synchronization uses disposable calendars/enrollments, never runtime data."""
import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import views
from .models import Assessment, CalendarEvent, Enrollment, School, SchoolCalendar, Section, StudentActivityProgress, User


class ManagementSyncFixtures:
    def setUp(self):
        self.school = School.objects.create(name='Disposable Sync School', code='SYNC')
        self.teacher = self.user('teacher', 'teacher')
        self.other_teacher = self.user('other', 'teacher')
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        self.section = self.new_section('SYNC-A', self.teacher)
        self.other_section = self.new_section('SYNC-B', self.other_teacher)
        self.student = self.user('student', 'student')
        self.enrollment = Enrollment.objects.create(student=self.student, section=self.section)
        self.set_term(1)
        clock = patch('pabasa_app.views.system_today', return_value=date(2026, 10, 12))
        clock.start()
        self.addCleanup(clock.stop)
        session = self.client.session
        session.update({'user_id': self.teacher.pk, 'user_role': 'teacher'})
        session.save()

    def user(self, key, role='student'):
        return User.objects.create(custom_id='SYNC-' + key, role=role, first_name=key, last_name='Test',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email=key + '@sync.example.invalid', password_hash='!', school_record=self.school)

    def new_section(self, code, teacher):
        return Section.objects.create(school=self.school, school_calendar=self.calendar, teacher=teacher,
            class_code=code, class_name=code, subject='Reading', grade_level='Grade 2')

    def set_term(self, term):
        self.calendar.events.all().delete()
        for kind, day in [('school_opening', '2026-10-01'), ('school_closing', '2026-12-01')]:
            CalendarEvent.objects.create(school_calendar=self.calendar, term=term, event_type=kind,
                title=kind, start_date=date.fromisoformat(day), end_date=date.fromisoformat(day))

    def sync(self, **params):
        return self.client.get(reverse('get_teacher_students_api'),
            {'section_id': self.section.pk, 'sync': 'management', **params})


class ClassManagementSyncTests(ManagementSyncFixtures, TestCase):
    def test_dated_term_transition_updates_calendar_without_changing_membership(self):
        before = list(Enrollment.objects.values())
        first = self.sync(include_calendar='1').json()
        self.assertEqual(first['calendar']['term'], 1)
        self.set_term(3)
        next_data = self.sync(include_calendar='1', roster_version=first['roster_version']).json()
        self.assertEqual(next_data['calendar']['label'], 'School Year 2026-2027 | Term 3')
        self.assertTrue(next_data['unchanged'])
        self.calendar.refresh_from_db()
        self.assertEqual(self.calendar.current_term, 1)  # Intentionally stale legacy field.
        self.assertEqual(list(Enrollment.objects.values()), before)

    def test_initial_header_and_feed_agree(self):
        self.set_term(3)
        with patch('pabasa_app.views._dashboard_context', side_effect=lambda request, role, extra: extra):
            response = self.client.get(reverse('class_management'), {'section_id': self.section.pk})
        self.assertContains(response, 'School Year 2026-2027 | Term 3')
        self.assertContains(response, self.student.custom_id)
        self.assertEqual(response.context['roster_version'], self.sync().json()['roster_version'])

    def test_no_active_term_never_falls_back_to_stored_term_one(self):
        self.calendar.events.all().delete()
        data = self.sync(include_calendar='1').json()
        self.assertIsNone(data['calendar']['term'])
        self.assertEqual(data['calendar']['label'], 'School Year 2026-2027 | No Active Term')
        self.assertEqual(data['total_students'], 1)

    def test_inactive_calendar_unavailable_and_year_enrollments_excluded(self):
        self.calendar.is_active = False
        self.calendar.save()
        data = self.sync(include_calendar='1').json()
        self.assertIsNone(data['calendar']['id'])
        self.assertEqual(data['total_students'], 0)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'active')

    def test_enrollment_drop_reactivation_and_transfer(self):
        newcomer = self.user('new')
        self.section.add_student(newcomer)
        self.assertEqual(self.sync().json()['total_students'], 2)
        result = self.client.post(reverse('teacher_drop_student'),
            json.dumps({'section_id': self.section.pk, 'student_id': self.student.pk}), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.sync().json()['total_students'], 1)
        self.enrollment.refresh_from_db()
        self.assertEqual((self.enrollment.status, self.enrollment.is_active), ('dropped', False))
        self.section.add_student(self.student)
        self.assertEqual(self.sync().json()['total_students'], 2)
        self.other_section.add_student(self.student)
        data = self.sync().json()
        self.assertEqual([item['id'] for item in data['students']], [newcomer.pk])
        self.assertEqual(Enrollment.objects.filter(student=self.student, status='active').count(), 1)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'completed')

    def test_same_ids_changed_metadata_produces_new_version_and_escaped_rows(self):
        before = self.sync().json()
        self.student.first_name = '<script>Changed</script>'
        self.student.save()
        data = self.sync(roster_version=before['roster_version']).json()
        self.assertFalse(data['unchanged'])
        self.assertIn('&lt;script&gt;Changed&lt;/script&gt;', data['students'][0]['row_html'])
        self.assertNotIn('<script>Changed</script>', data['students'][0]['card_html'])

    def test_unchanged_feed_is_small_and_skips_dashboard_metrics(self):
        with patch('pabasa_app.views._teacher_student_roster_payload') as heavy:
            first = self.sync().json()
            second = self.sync(roster_version=first['roster_version'], calendar_scope=first['calendar']['scope'])
        heavy.assert_not_called()
        self.assertNotIn('calendar', second.json())
        self.assertTrue(second.json()['unchanged'])
        self.assertNotIn('students', second.json())
        self.assertLess(len(second.content), 250)
        self.assertEqual(second['Cache-Control'], 'no-store, private')

    def test_section_permissions_and_required_id(self):
        self.assertEqual(self.sync(section_id=self.other_section.pk).status_code, 403)
        self.assertEqual(self.sync(section_id='invalid').status_code, 400)
        self.assertEqual(self.sync(section_id='').status_code, 400)
        self.section.is_active = False
        self.section.save()
        self.assertEqual(self.sync().status_code, 403)

    def test_cross_school_section_is_not_available_even_if_assigned(self):
        foreign = School.objects.create(name='Other Sync School')
        self.section.school = foreign
        self.section.save()
        self.assertEqual(self.sync().status_code, 403)

    def test_completed_archived_and_mismatched_year_are_not_current_enrollments(self):
        archived = self.user('archived')
        Enrollment.objects.create(student=archived, section=self.section)
        archived.is_archived = True
        archived.save()
        completed = self.user('completed')
        Enrollment.objects.create(student=completed, section=self.section, status='completed')
        wrong_year = SchoolCalendar.objects.create(school_year='2025-2026', current_term=1, is_active=False)
        Enrollment.objects.filter(pk=self.enrollment.pk).update(school_calendar=wrong_year)
        self.assertEqual(self.sync().json()['total_students'], 0)

    def test_other_section_membership_and_legacy_json_cannot_leak_into_roster(self):
        outsider = self.user('outsider')
        self.other_section.add_student(outsider)
        self.section.students = [{'student_id': outsider.pk, 'custom_id': outsider.custom_id}]
        self.section.save()
        data = self.sync().json()
        self.assertEqual(data['total_students'], 1)
        self.assertEqual([item['id'] for item in data['students']], [self.student.pk])
        self.assertTrue(Enrollment.objects.filter(student=outsider, section=self.other_section, status='active').exists())

    def test_new_active_school_year_header_updates_without_transferring_old_membership(self):
        successor = SchoolCalendar.objects.create(school_year='2027-2028', current_term=1)
        next_section = self.new_section('SYNC-NEXT', self.teacher)
        next_section.school_calendar = successor
        next_section.save()
        self.calendar.is_active = False
        self.calendar.save()
        data = self.sync(include_calendar='1').json()
        self.assertEqual(data['calendar']['school_year'], '2027-2028')
        self.assertIsNone(data['calendar']['term'])
        self.assertEqual(data['total_students'], 0)
        self.enrollment.refresh_from_db()
        self.assertEqual((self.enrollment.school_calendar_id, self.enrollment.status), (self.calendar.pk, 'active'))
        self.assertFalse(Enrollment.objects.filter(student=self.student, school_calendar=successor).exists())

    def test_persisted_official_reading_classification_is_reused_and_updates(self):
        before = self.sync().json()
        result = Assessment.objects.create(title='Disposable CRLA', code='SYNC-CRLA', teacher=self.teacher,
            student=self.student, enrollment=self.enrollment, attempt_status='completed',
            completed_at=timezone.now(), system_assessment_key='bosy_crla_pretest', official_term=1,
            crla_classification='Low Emerging Reader')
        after = self.sync(roster_version=before['roster_version']).json()
        self.assertFalse(after['unchanged'])
        self.assertIn('Low Emerging Reader', after['students'][0]['row_html'])
        result.crla_classification = 'High Emerging Reader'
        result.save()
        self.assertIn('High Emerging Reader', self.sync().json()['students'][0]['card_html'])


class ClassManagementTermReadingTests(ManagementSyncFixtures, TestCase):
    def result(self, term=1, level='Low Emerging Reader', **overrides):
        values = dict(title='Disposable term CRLA', code=f'SYNC-CRLA-{Assessment.objects.count()}',
            teacher=self.teacher, student=self.student, enrollment=self.enrollment,
            attempt_status='completed', completed_at=timezone.now(), official_term=term,
            system_assessment_key='bosy_crla_pretest', crla_classification=level)
        values.update(overrides)
        return Assessment.objects.create(**values)

    def assert_level(self, data, level):
        student = next(item for item in data['students'] if item['id'] == self.student.pk)
        self.assertIn(f'data-reading-level="{level}"', student['row_html'])
        self.assertIn(f'data-reading-level="{level}"', student['card_html'])
        self.assertIn(f'data-sort-reading="{level}"', student['row_html'])
        self.assertEqual(student['row_html'].count('<td'), 6)
        self.assertIn('Not Finalized', student['row_html'])

    def test_term_one_two_three_finalization_pending_and_history_preservation(self):
        progress = StudentActivityProgress.objects.create(student=self.student, school_calendar=self.calendar,
            term=1, activity_key='s1-l1-g1', activity_completed=True, completed_items=1, total_items=1)
        original = self.result()
        original_state = Assessment.objects.filter(pk=original.pk).values().get()
        enrollment_state = Enrollment.objects.filter(pk=self.enrollment.pk).values().get()
        progress_state = StudentActivityProgress.objects.filter(pk=progress.pk).values().get()
        self.assert_level(self.sync().json(), 'Low Emerging Reader')
        self.set_term(2)
        self.assert_level(self.sync().json(), 'Pending')
        term_two = self.result(term=2, level='Developing Reader', attempt_status='started', completed_at=None)
        self.assert_level(self.sync().json(), 'Pending')
        term_two.attempt_status = 'completed'
        term_two.completed_at = timezone.now()
        term_two.save()
        self.assert_level(self.sync().json(), 'Developing Reader')
        self.set_term(3)
        self.assert_level(self.sync().json(), 'Pending')
        self.result(term=3, level='Transitioning Reader')
        self.assert_level(self.sync().json(), 'Transitioning Reader')
        self.assertEqual(Assessment.objects.filter(pk=original.pk).values().get(), original_state)
        self.assertEqual(Enrollment.objects.filter(pk=self.enrollment.pk).values().get(), enrollment_state)
        self.assertEqual(StudentActivityProgress.objects.filter(pk=progress.pk).values().get(), progress_state)
        self.set_term(1)
        self.assert_level(self.sync().json(), 'Low Emerging Reader')

    def test_changed_scope_includes_matching_header_even_without_periodic_calendar_flag(self):
        self.result()
        first = self.sync().json()
        self.set_term(2)
        second = self.sync(roster_version=first['roster_version'], calendar_scope=first['calendar']['scope']).json()
        self.assertEqual(second['calendar']['term'], 2)
        self.assertFalse(second['unchanged'])
        self.assert_level(second, 'Pending')
        self.assertEqual(second['total_students'], 1)

    def test_another_school_year_result_and_outcome_cannot_replace_current_values(self):
        self.set_term(2)
        current = self.result(term=2, level='Developing Reader')
        old_calendar = SchoolCalendar.objects.create(school_year='2025-2026', current_term=2, is_active=False)
        old_section = self.new_section('SYNC-OLD', self.teacher)
        old_section.school_calendar = old_calendar
        old_section.save()
        old_enrollment = Enrollment.objects.create(student=self.student, section=old_section,
            status='completed', outcome='retained')
        self.result(term=2, level='Reading At Grade Level', enrollment=old_enrollment)
        self.assert_level(self.sync().json(), 'Developing Reader')
        old_enrollment.refresh_from_db()
        self.assertEqual((old_enrollment.outcome, old_enrollment.status), ('retained', 'completed'))
        current.delete()  # With only a historical finalized result, the current term is Pending.
        self.assert_level(self.sync().json(), 'Pending')

    def test_other_section_or_another_students_enrollment_cannot_supply_a_level(self):
        historical = Enrollment.objects.create(student=self.student, section=self.other_section, status='completed')
        self.result(enrollment=historical, level='Reading At Grade Level')
        unrelated = self.user('unrelated')
        unrelated_enrollment = Enrollment.objects.create(student=unrelated, section=self.section)
        self.result(enrollment=unrelated_enrollment, level='Transitioning Reader')
        self.assert_level(self.sync().json(), 'Pending')

    def test_unscoped_legacy_result_or_unfinished_result_does_not_supply_a_level(self):
        self.result(official_term=None, level='Reading At Grade Level')
        self.result(attempt_status='started', level='Transitioning Reader')
        self.result(completed_at=None, level='Developing Reader')
        self.assert_level(self.sync().json(), 'Pending')

    def test_legacy_result_with_explicit_current_section_year_and_term_is_preserved(self):
        self.set_term(2)
        self.result(term=2, level='Developing Reader', enrollment=None, section=self.section)
        self.assert_level(self.sync().json(), 'Developing Reader')
        historical = Enrollment.objects.create(student=self.student, section=self.other_section, status='completed')
        self.result(term=2, level='Reading At Grade Level', enrollment=historical, section=self.section)
        self.assert_level(self.sync().json(), 'Developing Reader')

    def test_reused_material_phase_does_not_override_persisted_term(self):
        self.set_term(2)
        self.result(term=1, system_assessment_phase='midtest', level='Reading At Grade Level')
        self.assert_level(self.sync().json(), 'Pending')
        self.result(term=2, system_assessment_phase='pretest', level='Developing Reader')
        self.assert_level(self.sync().json(), 'Developing Reader')

    def test_latest_valid_result_in_current_term_wins_without_changing_classification(self):
        self.result(level='Low Emerging Readers')
        self.result(level='High Emerging Reader')
        self.result(term=2, level='Reading At Grade Level')
        self.result(level='', classification='')
        self.assert_level(self.sync().json(), 'High Emerging Reader')

    def test_aral_exit_and_eligibility_preferences_neither_remove_membership_nor_override_crla(self):
        self.result()
        self.student.preference = {'reading_assessment_state': {
            'aral_exit_override': True, 'aral_manual_status': 'ineligible',
            'aral_exit_scope': {'term': 1, 'phase': 'pretest'}, 'aral_eligible': False}}
        self.student.save()
        enrollment = Enrollment.objects.filter(pk=self.enrollment.pk).values().get()
        self.assert_level(self.sync().json(), 'Low Emerging Reader')
        self.set_term(2)
        self.assert_level(self.sync().json(), 'Pending')
        self.result(term=2, level='Developing Reader')
        self.assert_level(self.sync().json(), 'Developing Reader')
        self.student.preference['reading_assessment_state'].update(aral_manual_status='active', aral_eligible=True)
        self.student.save()
        data = self.sync().json()
        self.assert_level(data, 'Developing Reader')
        self.assertEqual(data['total_students'], 1)
        self.assertEqual(Enrollment.objects.filter(pk=self.enrollment.pk).values().get(), enrollment)

    def test_no_active_term_displays_pending_and_preserves_active_enrollment(self):
        self.result(level='Reading At Grade Level')
        self.calendar.events.all().delete()
        data = self.sync().json()
        self.assertIsNone(data['calendar']['term'])
        self.assert_level(data, 'Pending')
        self.assertEqual(data['total_students'], 1)

    def test_year_end_outcome_changes_sync_without_resetting_on_term_transition(self):
        first = self.sync().json()
        Enrollment.objects.filter(pk=self.enrollment.pk).update(outcome='retained')
        second = self.sync(roster_version=first['roster_version']).json()
        self.assertFalse(second['unchanged'])
        self.assertIn('Retained', second['students'][0]['row_html'])
        self.set_term(2)
        third = self.sync().json()
        self.assertIn('Retained', third['students'][0]['row_html'])
        self.assertEqual(third['total_students'], 1)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.outcome, 'retained')

    def test_real_year_end_finalization_keeps_outcome_and_removes_completed_membership(self):
        self.set_term(3)
        self.calendar.events.filter(event_type='school_closing').update(start_date=date(2026, 10, 12), end_date=date(2026, 10, 15))
        with patch('pabasa_app.views.timezone.localdate', return_value=date(2026, 10, 12)):
            response = self.client.post(reverse('teacher_finalize_student'),
                {'student_id': self.student.pk, 'section_id': self.section.pk, 'outcome': 'retained'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.sync().json()['total_students'], 0)
        self.set_term(1)
        self.enrollment.refresh_from_db()
        self.assertEqual((self.enrollment.outcome, self.enrollment.status), ('retained', 'completed'))
        self.assertEqual(self.sync().json()['total_students'], 0)

    def test_six_columns_and_initial_reading_labels_match_poll_response(self):
        self.set_term(2)
        self.result(term=1, level='Reading At Grade Level')
        with patch('pabasa_app.views._dashboard_context', side_effect=lambda request, role, extra: extra):
            response = self.client.get(reverse('class_management'), {'section_id': self.section.pk})
        self.assertEqual(response.context['students_table'][0]['reading_level'], 'Pending')
        import re
        head = response.content.decode().split('<thead>', 1)[1].split('</thead>', 1)[0]
        self.assertEqual(re.findall(r'<th>(.*?)</th>', head),
            ['Name', 'PABASA ID', 'Email', 'Reading Level', 'Year-End Outcome', 'Actions'])
        self.assert_level(self.sync().json(), 'Pending')
