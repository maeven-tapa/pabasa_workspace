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
