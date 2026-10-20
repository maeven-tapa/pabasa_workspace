"""Completion-only review availability; all fixtures live in the test database."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import tests_lesson15_reading as fixtures
from .models import Assessment, Enrollment, Material, SchoolCalendar, StudentActivityProgress, StudentActivityRecordingSubmission


class PrescribedReviewAvailabilityTests(TestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def availability(self, client=None, **params):
        return (client or self.teacher_client).get(reverse('teacher_prescribed_review_availability'),
            {'student_id': self.student.pk, **params})

    def progress(self, key='lesson-15-gawain-3', **fields):
        return StudentActivityProgress.objects.create(student=self.student, activity_key=key,
            school_calendar=self.calendar, term=1, **fields)

    def test_not_started_and_in_progress_are_disabled_even_with_reviewed_recording(self):
        key = 'prescribed-lesson-15-gawain-3'
        self.assertFalse(self.availability(activity_id=key).json()['completed'][key])
        self.progress(current_index=1, completed_items=1)
        StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key='lesson-15-gawain-3', item_index=0,
            fluency_classification='GREEN', classification_source='teacher', review_status='reviewed')
        self.assertFalse(self.availability(activity_id=key).json()['completed'][key])

    def test_completed_pending_reviews_enabled_and_activity_isolated_after_refresh(self):
        progress = self.progress(current_index=22, activity_completed=True)
        self.progress(key='lesson-13-gawain-1', current_index=1)
        data = self.availability().json()['completed']
        self.assertTrue(data['prescribed-lesson-15-gawain-3'])
        self.assertFalse(data['prescribed-lesson-13-gawain-1'])
        # Availability does not require any recording or teacher grade.
        progress.activity_completed = False
        progress.save(update_fields=['activity_completed'])
        self.assertFalse(self.availability().json()['completed']['prescribed-lesson-15-gawain-3'])

    def test_old_terms_calendars_and_legacy_completion_do_not_enable_review(self):
        key = 'lesson-13-gawain-1'
        old_calendar = SchoolCalendar.objects.create(school_year='2025-2026', current_term=1, is_active=False)
        for calendar, term in [(self.calendar, 2), (old_calendar, 1), (None, None)]:
            StudentActivityProgress.objects.create(student=self.student, activity_key=key,
                school_calendar=calendar, term=term, activity_completed=True)
        self.assertFalse(self.availability(activity_id='prescribed-' + key).json()['completed']['prescribed-' + key])
        self.progress(key=key, activity_completed=True)
        self.assertTrue(self.availability(activity_id='prescribed-' + key).json()['completed']['prescribed-' + key])

    def test_no_current_term_fails_closed(self):
        self.progress(activity_completed=True)
        self.scope['term'] = None
        self.assertEqual(self.availability().json()['completed'], {})

    def test_teacher_and_current_enrollment_authorization(self):
        self.assertEqual(self.availability(self.client_for(self.other)).status_code, 403)
        self.assertEqual(self.availability(self.student_client).status_code, 302)  # existing role guard redirects
        Enrollment.objects.filter(student=self.student).update(status='completed', is_active=False)
        self.assertEqual(self.availability().status_code, 403)

    def test_missing_and_invalid_students_rejected_and_post_not_allowed(self):
        url = reverse('teacher_prescribed_review_availability')
        self.assertEqual(self.teacher_client.get(url).status_code, 400)
        self.assertEqual(self.availability(student_id=999999).status_code, 403)
        self.assertEqual(self.teacher_client.post(url, {'student_id': self.student.pk}).status_code, 405)

    def test_all_prescribed_review_activities_use_progress_not_grading(self):
        keys = ['lesson-1-gawain-1', 'session-4-gawain-1', 'session-4-gawain-2',
                'lesson-13-gawain-1', 'session-5-lesson-14-gawain-4',
                'lesson-15-gawain-3', 'lesson-29-gawain-3']
        for key in keys:
            self.progress(key=key, activity_completed=True)
        before = list(StudentActivityProgress.objects.filter(student=self.student).values())
        response = self.availability()
        self.assertEqual(response.json()['completed'], {'prescribed-' + key: True for key in keys})
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(list(StudentActivityProgress.objects.filter(student=self.student).values()), before)

    def test_material_backed_prescribed_cards_require_scoped_completed_assessment(self):
        material = Material.objects.create(title='Disposable prescribed recording', item_type='paragraph',
            teacher=self.teacher, content_json={'activity_type': 'retell_story', 'source_type': 'prescribed'})
        attempt = Assessment.objects.create(title=material.title, code='test-review-attempt',
            teacher=self.teacher, student=self.student, material=material, assessment_type='paragraph',
            attempt_status='started', supplementary_school_calendar=self.calendar, supplementary_term=1)
        key = f'material-{material.pk}'
        self.assertFalse(self.availability(activity_id=key).json()['completed'][key])
        attempt.attempt_status, attempt.completed_at = 'completed', timezone.now()
        attempt.supplementary_term = 2
        attempt.save()
        self.assertFalse(self.availability(activity_id=key).json()['completed'][key])
        attempt.supplementary_term = 1
        attempt.save()
        self.assertTrue(self.availability(activity_id=key).json()['completed'][key])

    def test_submitted_trace_say_is_reviewable_before_approval_in_current_term_only(self):
        key = 'prescribed-lesson-29-gawain-3'
        progress = self.progress(key='lesson-29-gawain-3', current_index=11,
                                 completed_items=11, state={'submitted': True, 'awaiting_teacher_verdict': True})
        data = self.availability(activity_id=key).json()
        self.assertFalse(data['completed'][key])
        self.assertTrue(data['reviewable'][key])
        rows = self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
                                       {'student_id': self.student.pk}).json()
        self.assertTrue(rows['submitted'])
        self.assertFalse(rows['completed'])
        progress.term = 2
        progress.save(update_fields=['term'])
        self.assertFalse(self.availability(activity_id=key).json()['reviewable'][key])
        rows = self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
                                       {'student_id': self.student.pk}).json()
        self.assertFalse(rows['submitted'])

    def test_trace_say_elapsed_time_survives_saves_and_reaches_teacher_card(self):
        url = reverse('lesson29_trace_say_progress')
        for seconds in (45, 17):
            response = self.student_client.post(url, {'action':'save_elapsed', 'elapsed_seconds':seconds}, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['progress']['state']['elapsed_seconds'], 45)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-29-gawain-3')
        progress.state.update(current_item=11, phase='complete', traces=[[] for _ in range(33)])
        progress.save(update_fields=['state'])
        response = self.student_client.post(reverse('lesson29_trace_say_complete'),
                                            {'elapsed_seconds':88}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
                                       {'student_id':self.student.pk}).json()
        self.assertEqual(data['duration_seconds'], 88)
        self.assertTrue(data['submitted_at'])
        self.assertTrue(data['submitted'])
        self.assertFalse(data['completed'])

    def test_trace_say_legacy_attempt_has_no_invented_elapsed_time(self):
        self.progress(key='lesson-29-gawain-3', state={'submitted':True})
        data = self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
                                       {'student_id':self.student.pk}).json()
        self.assertIsNone(data['duration_seconds'])
        self.assertTrue(data['submitted_at'])

    def test_trace_review_updates_current_term_and_preserves_history(self):
        old = self.progress(key='lesson-29-gawain-3', current_index=11, total_items=11,
                            state={'submitted':True, 'elapsed_seconds':100})
        current = StudentActivityProgress.objects.create(student=self.student, school_calendar=self.calendar,
            term=2, activity_key='lesson-29-gawain-3', current_index=11, total_items=11,
            state={'submitted':True})
        self.scope['term'] = 2
        before = StudentActivityProgress.objects.filter(pk=old.pk).values().get()
        url = reverse('teacher_lesson29_trace_say_review_action')
        response = self.teacher_client.post(url, {'student_id':self.student.pk, 'action':'retry'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        current.refresh_from_db()
        self.assertEqual(current.current_index, 0)
        self.assertEqual(StudentActivityProgress.objects.filter(pk=old.pk).values().get(), before)
        StudentActivityRecordingSubmission.objects.bulk_create([
            StudentActivityRecordingSubmission(student=self.student, activity_key='lesson-29-gawain-3',
                school_calendar=self.calendar, term=2, item_index=i, teacher_score=1, audio_file=f'test-only-{i}.webm') for i in range(11)])
        current.state = {'submitted':True}
        current.save(update_fields=['state'])
        response = self.teacher_client.post(url, {'student_id':self.student.pk, 'action':'checked'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        current.refresh_from_db()
        self.assertTrue(current.activity_completed)
        self.assertEqual(StudentActivityProgress.objects.filter(pk=old.pk).values().get(), before)

    def test_trace_review_does_not_fall_back_to_an_old_term(self):
        old = self.progress(key='lesson-29-gawain-3', state={'submitted':True})
        self.scope['term'] = 2
        response = self.teacher_client.post(reverse('teacher_lesson29_trace_say_review_action'),
            {'student_id':self.student.pk, 'action':'retry'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        old.refresh_from_db()
        self.assertEqual(old.state, {'submitted':True})

    def test_late_elapsed_save_preserves_submission_and_review_access(self):
        progress = self.progress(key='lesson-29-gawain-3', current_index=11, completed_items=11,
            state={'current_item':11, 'phase':'complete', 'traces':[[]]*33,
                   'submitted':True, 'awaiting_teacher_verdict':True,
                   'submitted_at':'2026-10-20T12:00:00+00:00', 'elapsed_seconds':88})
        before = StudentActivityProgress.objects.filter(pk=progress.pk).values().get()
        response = self.student_client.post(reverse('lesson29_trace_say_progress'),
            {'action':'save_elapsed', 'elapsed_seconds':120}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentActivityProgress.objects.filter(pk=progress.pk).values().get(), before)
        key = 'prescribed-lesson-29-gawain-3'
        self.assertTrue(self.availability(activity_id=key).json()['reviewable'][key])
        progress.activity_completed = True
        progress.save(update_fields=['activity_completed'])
        response = self.student_client.post(reverse('lesson29_trace_say_complete'),
            {'elapsed_seconds':999}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.state['elapsed_seconds'], 88)

    def test_nonfinite_trace_elapsed_values_never_raise_server_error(self):
        for seconds in ('1e999', 'Infinity', '-Infinity', 'NaN', None, {}, -5):
            response = self.student_client.post(reverse('lesson29_trace_say_progress'),
                {'action':'save_elapsed', 'elapsed_seconds':seconds}, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['progress']['state']['elapsed_seconds'], 0)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-29-gawain-3')
        progress.state.update(current_item=11, phase='complete', traces=[[]]*33)
        progress.save(update_fields=['state'])
        response = self.student_client.post(reverse('lesson29_trace_say_complete'),
            {'elapsed_seconds':'1e999'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        progress.refresh_from_db()
        self.assertEqual(progress.state['elapsed_seconds'], 0)
