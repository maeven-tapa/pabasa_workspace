"""Term ownership and server authorization for prescribed progress."""

import json
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, PrescribedActivityAccessSettings, School, StudentActivityProgress, User
from .views import _unlocked_prescribed_activity_keys
from .prescribed_test_fixtures import prescribed_term_fixture
from .views import _current_learning_context, _current_progress_queryset


class PrescribedTermLifecycleTests(TestCase):
    key = 'lesson-13-gawain-1'

    def setUp(self):
        self.today = timezone.localdate()
        self.school = School.objects.create(name='Lifecycle School', code='LIFECYCLE')
        self.student = User.objects.create(
            custom_id='LIFECYCLE-STUDENT', role='student', first_name='Term', last_name='Learner',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email='lifecycle-student@example.test', password_hash='x', school_record=self.school,
        )
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.page = reverse('prescribed_activity_page', kwargs={'activity_key': self.key})
        self.progress = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})
        self.complete = reverse('prescribed_activity_complete', kwargs={'activity_key': self.key})

    def scope(self, **kwargs):
        return prescribed_term_fixture(self.student, today=self.today, **kwargs)

    def post(self, url):
        return self.client.post(url, data=json.dumps({}), content_type='application/json')

    def test_aral_active_allows_page_and_writes(self):
        calendar, _section, _enrollment, _result = self.scope()
        self.assertEqual(_current_learning_context(self.student)['state'], 'ARAL_ACTIVE')
        self.assertEqual(self.client.get(self.page).status_code, 200)
        save_response = self.client.post(
            self.progress, data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(save_response.status_code, 200)
        progress = _current_progress_queryset(self.student).get(activity_key=self.key)
        progress.completed_items = 4
        progress.save(update_fields=['completed_items', 'updated_at'])
        self.assertEqual(self.post(self.complete).status_code, 200)
        self.assertEqual(calendar, _current_learning_context(self.student)['school_calendar'])

    def test_pending_denies_page_and_writes(self):
        self.scope(completed=False)
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')
        self.assertNotEqual(self.client.get(self.page).status_code, 200)
        self.assertEqual(self.post(self.progress).status_code, 403)
        self.assertEqual(self.post(self.complete).status_code, 403)
        self.assertEqual(self.post(reverse('lesson29_trace_say_progress')).status_code, 403)
        self.assertEqual(self.post(reverse('lesson29_trace_say_submit')).status_code, 403)

    def test_grade_level_denies_page_and_writes(self):
        self.scope(classification='Reading At Grade Level')
        self.assertEqual(_current_learning_context(self.student)['state'], 'GRADE_LEVEL')
        self.assertNotEqual(self.client.get(self.page).status_code, 200)
        self.assertEqual(self.post(self.progress).status_code, 403)
        self.assertEqual(self.post(self.complete).status_code, 403)
        self.assertEqual(self.post(reverse('lesson29_trace_say_progress')).status_code, 403)

    def test_end_date_inclusive_and_closed_next_day(self):
        self.scope(end=self.today)
        self.assertEqual(_current_learning_context(self.student)['state'], 'ARAL_ACTIVE')
        self.assertEqual(self.client.get(self.page).status_code, 200)
        with patch('pabasa_app.views.system_today', return_value=self.today + timedelta(days=1)):
            self.assertEqual(_current_learning_context(self.student)['state'], 'BETWEEN_TERMS')
            self.assertNotEqual(self.client.get(self.page).status_code, 200)
            self.assertEqual(self.post(self.progress).status_code, 403)

    def test_between_terms_denies(self):
        self.scope(end=self.today - timedelta(days=1))
        self.assertEqual(_current_learning_context(self.student)['state'], 'BETWEEN_TERMS')
        self.assertNotEqual(self.client.get(self.page).status_code, 200)

    def test_crla_status_classification_and_precedence(self):
        calendar, _section, _enrollment, result = self.scope()
        result.classification = 'Reading At Grade Level'
        result.save(update_fields=['classification'])
        self.assertEqual(_current_learning_context(self.student)['classification'], 'Developing Reader')
        result.crla_classification = ''
        result.classification = 'Developing Reader'
        result.save(update_fields=['crla_classification', 'classification'])
        self.assertEqual(_current_learning_context(self.student)['state'], 'ARAL_ACTIVE')
        result.classification = ''
        result.save(update_fields=['classification'])
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')
        result.crla_classification = 'Developing Reader'
        result.attempt_status = 'started'
        result.save(update_fields=['crla_classification', 'attempt_status'])
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')
        result.attempt_status = 'completed'
        result.completed_at = None
        result.save(update_fields=['attempt_status', 'completed_at'])
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')

    def test_legacy_row_remains_separate(self):
        legacy = StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.key, activity_completed=True,
            state={'old': True}, school_calendar=None, term=None,
        )
        calendar, _section, _enrollment, _result = self.scope()
        self.assertIsNone(_current_progress_queryset(self.student).filter(activity_key=self.key).first())
        current = StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1, activity_key=self.key,
            state={'new': True},
        )
        legacy.refresh_from_db()
        self.assertEqual(legacy.state, {'old': True})
        self.assertNotEqual(legacy.pk, current.pk)

    def test_term_two_starts_fresh_and_preserves_term_one_resume(self):
        calendar, section, enrollment, _result = self.scope(end=self.today)
        old_state = {'current_item': 3, 'answers': ['old'], 'traces': [1], 'matches': {'old': 1}}
        old = StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1, activity_key=self.key,
            current_index=3, activity_completed=True, state=old_state,
        )
        next_day = self.today + timedelta(days=1)
        prescribed_term_fixture(
            self.student, teacher=section.teacher, section=section, calendar=calendar,
            term=2, today=next_day, start=next_day, end=next_day + timedelta(days=7),
        )
        with patch('pabasa_app.views.system_today', return_value=next_day):
            lifecycle = _current_learning_context(self.student)
            self.assertEqual(lifecycle['state'], 'ARAL_ACTIVE')
            self.assertEqual(lifecycle['term'], 2)
            self.assertFalse(_current_progress_queryset(self.student, lifecycle).filter(activity_key=self.key).exists())
            page = self.client.get(self.page)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn(str(old_state), page.content.decode())
            current = StudentActivityProgress.objects.get(
                student=self.student, school_calendar=calendar, term=2, activity_key=self.key,
            )
        old.refresh_from_db()
        self.assertEqual(old.state, old_state)
        self.assertTrue(old.activity_completed)
        self.assertFalse(current.activity_completed)
        self.assertEqual(StudentActivityProgress.objects.filter(student=self.student).count(), 2)

    def test_new_school_year_starts_fresh(self):
        calendar, section, _enrollment, _result = self.scope()
        old = StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1, activity_key=self.key,
            activity_completed=True, state={'answers': ['previous year']},
        )
        # A new enrollment belongs to the new academic year.
        section.enrollments.filter(student=self.student).update(status='completed', is_active=False)
        next_year = self.today + timedelta(days=366)
        new_calendar, new_section, _new_enrollment, _new_result = prescribed_term_fixture(
            self.student, today=next_year, term=1,
        )
        with patch('pabasa_app.views.system_today', return_value=next_year):
            lifecycle = _current_learning_context(self.student)
            self.assertEqual(lifecycle['school_calendar'], new_calendar)
            self.assertFalse(_current_progress_queryset(self.student, lifecycle).filter(activity_key=self.key).exists())
            self.assertEqual(self.client.get(self.page).status_code, 200)
            current = StudentActivityProgress.objects.get(
                student=self.student, school_calendar=new_calendar, term=1, activity_key=self.key,
            )
        old.refresh_from_db()
        self.assertTrue(old.activity_completed)
        self.assertEqual(old.state, {'answers': ['previous year']})
        self.assertNotEqual(old.pk, current.pk)

    def test_old_term_result_does_not_unlock_next_term(self):
        calendar, section, _enrollment, _result = self.scope(end=self.today)
        next_day = self.today + timedelta(days=1)
        prescribed_term_fixture(
            self.student, teacher=section.teacher, section=section, calendar=calendar,
            term=2, today=next_day, completed=False, start=next_day,
        )
        with patch('pabasa_app.views.system_today', return_value=next_day):
            self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')
            self.assertEqual(self.post(self.progress).status_code, 403)

    def test_term_two_crla_does_not_unlock_term_three(self):
        calendar, section, _enrollment, _result = self.scope(term=2, end=self.today)
        next_day = self.today + timedelta(days=1)
        prescribed_term_fixture(
            self.student, teacher=section.teacher, section=section, calendar=calendar,
            term=3, today=next_day, completed=False, start=next_day,
        )
        with patch('pabasa_app.views.system_today', return_value=next_day):
            self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')

    def test_previous_school_year_crla_does_not_unlock_new_year(self):
        _calendar, section, _enrollment, _result = self.scope()
        section.enrollments.filter(student=self.student).update(status='completed', is_active=False)
        next_year = self.today + timedelta(days=366)
        prescribed_term_fixture(self.student, today=next_year, term=1, completed=False)
        with patch('pabasa_app.views.system_today', return_value=next_year):
            self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')
            self.assertEqual(self.post(self.progress).status_code, 403)

    def test_newest_valid_current_term_crla_is_authoritative(self):
        calendar, section, enrollment, older = self.scope(classification='Developing Reader')
        newer = Assessment.objects.create(
            student=self.student, teacher=section.teacher, enrollment=enrollment, material=older.material,
            system_assessment_key=older.system_assessment_key,
            system_assessment_phase=older.system_assessment_phase, official_term=1,
            attempt_status='completed',
            completed_at=timezone.make_aware(datetime.combine(self.today, time(13, 0))),
            crla_classification='Reading At Grade Level', classification='Developing Reader',
        )
        context = _current_learning_context(self.student)
        self.assertEqual(context['assessment'], newer)
        self.assertEqual(context['classification'], 'Reading At Grade Level')
        self.assertEqual(context['state'], 'GRADE_LEVEL')

    def test_school_enrollment_calendar_wins_when_multiple_calendars_exist(self):
        calendar, _section, _enrollment, _result = self.scope()
        prescribed_term_fixture(
            User.objects.create(
                custom_id='OTHER-STUDENT', role='student', first_name='Other', last_name='Learner',
                sex='male', birth_month=1, birth_day=1, birth_year=2018,
                email='other-student@example.test', password_hash='x',
                school_record=School.objects.create(name='Other School', code='OTHER-SCHOOL'),
            ),
            today=self.today + timedelta(days=366),
        )
        context = _current_learning_context(self.student)
        self.assertEqual(context['school_calendar'], calendar)
        self.assertEqual(context['state'], 'ARAL_ACTIVE')

    def test_multiple_legacy_null_rows_do_not_conflict_with_current_scope(self):
        first = StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.key, school_calendar=None, term=None,
        )
        second = StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.key, school_calendar=None, term=None,
        )
        calendar, _section, _enrollment, _result = self.scope()
        scoped = StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1, activity_key=self.key,
        )
        self.assertEqual(_current_progress_queryset(self.student).get(activity_key=self.key), scoped)
        self.assertEqual(
            StudentActivityProgress.objects.filter(pk__in=[first.pk, second.pk]).count(), 2,
        )

    def test_sequence_unlocking_ignores_previous_term_completion(self):
        PrescribedActivityAccessSettings.objects.update_or_create(
            pk=1, defaults={'unlock_all_activities': False},
        )
        calendar, _section, _enrollment, _result = self.scope()
        StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1,
            activity_key='lesson-1-gawain-1', activity_completed=True,
        )
        StudentActivityProgress.objects.create(
            student=self.student, school_calendar=calendar, term=1,
            activity_key='lesson-2-gawain-1', activity_completed=True,
        )
        term_two = {'school_calendar': calendar, 'term': 2}
        unlocked = _unlocked_prescribed_activity_keys(self.student, term_two)
        self.assertIn('lesson-1-gawain-1', unlocked)
        self.assertNotIn('lesson-2-gawain-1', unlocked)
