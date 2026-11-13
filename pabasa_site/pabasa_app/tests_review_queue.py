"""Review inbox behavior, scoped to disposable test records and local media."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from . import review_queue as inbox
from . import tests_lesson15_reading as fixtures
from .models import (Enrollment, Material, Notification, PrescribedReadingAttempt, SchoolCalendar,
    StoryResponseSubmission, StudentActivityProgress, StudentActivityRecordingSubmission,
    SupplementaryMaterialPublication, SupplementaryStudentAssignment, TeacherReviewInbox, User)


class ReviewQueueTests(TestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def setup_scope(self):
        if not hasattr(self, 'term_patch'):
            self.term_patch = patch('pabasa_app.views._calendar_current_term', return_value=1)
            self.term_mock = self.term_patch.start()
            self.addCleanup(self.term_patch.stop)
        self.enrollment = Enrollment.objects.get(student=self.student)
        return self.enrollment

    def progress(self, key='session-4-gawain-1', **fields):
        self.setup_scope()
        return StudentActivityProgress.objects.create(student=self.student, activity_key=key,
            **{'school_calendar': self.calendar, 'term': 1, 'activity_completed': True, **fields})

    def recording(self, key='session-4-gawain-1', index=0, **fields):
        return StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key=key, item_index=index, **{'school_calendar': self.calendar, 'term': 1,
            'audio_file': f'disposable/{key}-{index}.webm', **fields})

    def supplementary(self, mode='story_response', **fields):
        enrollment = self.setup_scope()
        material = Material.objects.create(teacher=self.teacher, section=enrollment.section,
            title='A small adventure', item_type='paragraph', status='published',
            content_json={'activity_type': mode})
        material.assigned_sections.add(enrollment.section)
        publication = SupplementaryMaterialPublication.objects.create(material=material,
            school_calendar=self.calendar, term=1, section=enrollment.section)
        submission = StoryResponseSubmission.objects.create(student=self.student, material=material,
            enrollment=enrollment, school_calendar=self.calendar, term=1,
            audio_file='disposable/story.webm', **fields)
        return submission, publication

    def queue(self, **params):
        self.setup_scope()
        response = self.teacher_client.get(reverse('teacher_review_queue_api'), params)
        self.assertEqual(response.status_code, 200, response.content[:200])
        return response.json()

    def task(self, key):
        return next(task for task in self.queue(status='all')['items'] if task['activity_key'] == key)

    def action(self, task, **data):
        return self.teacher_client.post(reverse('teacher_review_action'),
            {'task': task['id'], 'version': task['version'], **data}, content_type='application/json')

    def test_all_nine_prescribed_and_two_supplementary_types(self):
        for key, (_, _, mode) in inbox.ACTIVITIES.items():
            state = {'submitted': True} if mode in {'single', 'trace', 'drawing'} else {}
            progress = self.progress(key, state=state)
            if mode == 'lesson15':
                attempt = PrescribedReadingAttempt.objects.create(student=self.student,
                    school_calendar=self.calendar, term=1, activity_key=key, item_index=0,
                    audio_file='disposable/reading.webm')
                progress.state = {'item_results': {'0': {'attempt_id': str(attempt.attempt_id), 'review_version': 0}}}
                progress.save(update_fields=['state'])
            elif mode != 'drawing':
                recording = self.recording(key, substep=0 if key == 'session-4-gawain-2' else None)
                if mode == 'single':
                    progress.state['submission_id'] = recording.pk
                    progress.save(update_fields=['state'])
        self.supplementary('story_response')
        self.supplementary('retell_story')
        data = self.queue()
        self.assertEqual(data['summary']['pending'], 11)
        self.assertEqual(data['summary']['students'], 1)
        self.assertEqual(data['summary']['prescribed'], 9)
        self.assertEqual(data['summary']['supplementary'], 2)
        self.assertEqual(len({task['id'] for task in data['items']}), 11)

    def test_incomplete_progress_missing_audio_and_automatic_stage_excluded(self):
        self.progress(activity_completed=False)
        self.recording()
        self.progress('session-4-gawain-2')
        self.recording('session-4-gawain-2', substep=2)
        self.progress('lesson-13-gawain-1')
        self.recording('lesson-13-gawain-1', audio_file='')
        self.assertEqual(self.queue()['total'], 0)

    def test_partial_binary_reviews_and_score_zero_is_reviewed(self):
        self.progress()
        self.recording(index=0, status='checked', teacher_score=0)
        second = self.recording(index=1)
        task = self.task('session-4-gawain-1')
        self.assertEqual((task['status'], task['reviewed_items'], task['pending_items']), ('partial', 1, 1))
        response = self.action(task, action='item', submission_id=second.pk, score=1)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.queue()['total'], 0)
        self.assertEqual(self.queue(status='reviewed')['total'], 1)
        second.refresh_from_db()
        self.assertEqual(second.teacher_score, 1)

    def test_lesson1_submission_before_completion_retry_and_resubmission(self):
        progress = self.progress('lesson-1-gawain-1', activity_completed=False)
        recording = self.recording('lesson-1-gawain-1', index=None)
        progress.state = {'submitted': True, 'submission_id': recording.pk}
        progress.save(update_fields=['state'])
        task = self.task('lesson-1-gawain-1')
        self.assertEqual(self.action(task, action='retry').status_code, 200)
        self.assertEqual(self.queue()['total'], 0)
        self.assertEqual(self.queue(status='retry')['total'], 1)
        self.assertEqual(self.action(self.task('lesson-1-gawain-1'), action='checked').status_code, 409)
        recording.status = 'submitted'
        recording.audio_file = 'disposable/new.webm'
        recording.save()
        progress.state = {'submitted': True, 'submission_id': recording.pk}
        progress.save(update_fields=['state'])
        task = self.task('lesson-1-gawain-1')
        self.assertEqual(self.action(task, action='checked').status_code, 200)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)

    def test_mixed_current_legacy_and_scoped_scores_preserve_totals(self):
        progress = self.progress()
        self.recording(index=0, school_calendar=None, term=None, teacher_score=1, status='checked')
        row = self.recording(index=1)
        old = self.recording(index=2, school_calendar=None, term=None, teacher_score=1, status='checked')
        StudentActivityRecordingSubmission.objects.filter(pk=old.pk).update(submitted_at=progress.created_at - timedelta(days=30))
        task = self.task('session-4-gawain-1')
        self.assertEqual(task['reviewed_items'], 1)
        result = self.action(task, action='item', submission_id=row.pk, score=1)
        self.assertEqual(result.status_code, 200)
        progress.refresh_from_db()
        self.assertEqual(progress.correct_items, 2)

    def test_drawings_remain_pending_until_teacher_verdict(self):
        key = 'aral-s9-a1-family-drawing'
        progress = self.progress(key, activity_completed=False,
            state={'submitted': True, 'awaiting_teacher_verdict': True,
                   'answers': {'item-1': {'text': 'This is my family.', 'strokes': []}}})
        task = self.task(key)
        self.assertEqual(self.action(task, action='complete').status_code, 200)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)
        self.assertTrue(progress.state['checked'])
        self.assertEqual(self.queue()['total'], 0, self.queue())

    def test_trace_requires_final_verdict_after_all_items_scored(self):
        key = 'lesson-29-gawain-3'
        progress = self.progress(key, activity_completed=False,
            total_items=11, state={'submitted': True, 'awaiting_teacher_verdict': True})
        for index in range(11):
            self.recording(key, index, status='checked', teacher_score=1)
        task = self.task(key)
        self.assertEqual(task['pending_items'], 0)
        self.assertTrue(task['final_verdict'])
        self.assertEqual(task['status'], 'partial')
        self.assertEqual(self.action(task, action='checked').status_code, 200)
        self.assertEqual(self.queue()['total'], 0)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)

    def test_fluency_skips_and_superseded_lesson15_attempts(self):
        key = 'lesson-15-gawain-3'
        progress = self.progress(key)
        old = PrescribedReadingAttempt.objects.create(student=self.student, school_calendar=self.calendar,
            term=1, activity_key=key, item_index=0, attempt_number=1, audio_file='disposable/old.webm')
        current = PrescribedReadingAttempt.objects.create(student=self.student, school_calendar=self.calendar,
            term=1, activity_key=key, item_index=0, attempt_number=2, audio_file='disposable/new.webm')
        progress.state = {'item_results': {'0': {'attempt_id': str(current.attempt_id), 'review_version': 0},
                                         '1': {'classification_source': 'skipped'}}}
        progress.save(update_fields=['state'])
        task = self.task(key)
        self.assertEqual(task['pending_items'], 1)
        self.assertEqual(self.action(task, action='item', submission_id=old.pk, classification='GREEN').status_code, 409)
        self.assertEqual(self.action(task, action='item', submission_id=current.pk, classification='GREEN').status_code, 200)
        self.assertEqual(self.queue()['total'], 0)

    def test_stale_versions_and_cross_task_recording_rejected(self):
        self.progress()
        first = self.recording()
        self.progress('lesson-13-gawain-1')
        other = self.recording('lesson-13-gawain-1')
        task = self.task('session-4-gawain-1')
        self.assertEqual(self.action(task, action='item', submission_id=other.pk, score=1).status_code, 409)
        first.audio_file = 'disposable/replaced.webm'
        first.save()
        self.assertEqual(self.action(task, action='item', submission_id=first.pk, score=1).status_code, 409)

    def test_retell_review_is_independent_of_optional_score_and_idempotent(self):
        submission, _ = self.supplementary('retell_story')
        key = f'material-{submission.material_id}'
        task = self.task(key)
        self.assertEqual(self.action(task, action='reviewed').status_code, 200)
        submission.refresh_from_db()
        self.assertIsNone(submission.grade)
        self.assertEqual(submission.status, 'pending')  # existing score semantics preserved
        self.assertEqual(submission.reviewed_by, self.teacher)
        reviewed_at = submission.reviewed_at
        self.assertEqual(self.queue()['total'], 0)
        self.assertEqual(self.action(self.task(key), action='reviewed').status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.reviewed_at, reviewed_at)
        self.assertEqual(self.action(self.task(key), action='grade', grade=4).status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.grade, 4)
        self.assertEqual(self.action(self.task(key), action='grade', grade=5).status_code, 409)

    def test_story_response_requires_grade_and_zero_removes_from_pending(self):
        submission, _ = self.supplementary()
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['reviewed_at'])
        self.assertEqual(self.queue()['total'], 1)
        task = self.task(f'material-{submission.material_id}')
        self.assertEqual(self.action(task, action='reviewed').status_code, 400)
        self.assertEqual(self.action(task, action='grade', grade=0).status_code, 200)
        self.assertEqual(self.queue()['total'], 0)

    def test_selected_assignments_and_publication_scope(self):
        submission, publication = self.supplementary()
        material = submission.material
        material.publication_scope = 'selected_students'
        material.save(update_fields=['publication_scope'])
        self.assertEqual(self.queue()['total'], 0)
        SupplementaryStudentAssignment.objects.create(publication=publication, student=self.student, enrollment=self.enrollment)
        self.assertEqual(self.queue()['total'], 1)
        publication.is_active = False
        publication.save(update_fields=['is_active'])
        self.assertEqual(self.queue()['total'], 0)

    def test_old_terms_calendars_and_legacy_audio_are_not_borrowed(self):
        progress = self.progress()
        row = self.recording()
        StudentActivityRecordingSubmission.objects.filter(pk=row.pk).update(school_calendar=None,
            term=None, submitted_at=progress.created_at - timedelta(days=30))
        self.assertEqual(self.queue()['total'], 0)
        row = self.recording('lesson-13-gawain-1')
        self.progress('lesson-13-gawain-1', term=2)
        self.assertEqual(self.queue()['total'], 0)

    def test_authorization_section_school_and_removed_enrollment(self):
        self.progress(); row = self.recording()
        task = self.task('session-4-gawain-1')
        other_client = self.client_for(self.other)
        self.assertEqual(other_client.get(reverse('teacher_review_queue_api')).json()['total'], 0)
        self.assertEqual(other_client.get(reverse('teacher_review_detail'), {'task': task['id']}).status_code, 404)
        self.assertEqual(other_client.get(reverse('teacher_review_audio'), {'task': task['id'], 'record': row.pk}).status_code, 403)
        self.assertEqual(self.student_client.get(reverse('teacher_review_queue_api')).status_code, 403)
        self.assertEqual(Client().get(reverse('teacher_review_queue')).status_code, 403)
        Enrollment.objects.filter(student=self.student).update(is_active=False)
        self.assertEqual(self.action(task, action='item', submission_id=row.pk, score=1).status_code, 404)

    def test_csrf_required_for_review_writes(self):
        self.progress(); self.recording()
        task = self.task('session-4-gawain-1')
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session.update({'user_id': self.teacher.pk, 'user_role': 'teacher'}); session.save()
        self.assertEqual(client.post(reverse('teacher_review_action'), {'task': task['id']}).status_code, 403)

    def test_grouped_notifications_no_duplicates_read_clear_and_resubmission(self):
        progress = self.progress(); recording = self.recording()
        self.supplementary()
        first = self.queue(summary=1)
        self.assertTrue(first['notification_changed'])
        self.assertEqual(Notification.objects.filter(recipient=self.teacher).count(), 1)
        notification = Notification.objects.get(recipient=self.teacher)
        self.assertIn('2 submissions from 1 student', notification.message)
        self.assertEqual(notification.action_url, reverse('teacher_review_queue'))
        self.assertFalse(self.queue(summary=1)['notification_changed'])
        self.teacher_client.post(reverse('mark_notification_read'),
            {'notification_id': notification.pk}, content_type='application/json')
        self.queue(summary=1)
        notification.refresh_from_db(); self.assertTrue(notification.is_read)
        self.assertEqual(self.queue()['total'], 2)
        self.teacher_client.post(reverse('clear_notifications'), {}, content_type='application/json')
        self.queue(summary=1)
        self.assertFalse(Notification.objects.filter(recipient=self.teacher).exists())
        recording.audio_file = 'disposable/new-notification.webm'; recording.save()
        self.queue(summary=1)
        self.assertEqual(Notification.objects.filter(recipient=self.teacher).count(), 1)
        self.assertEqual(TeacherReviewInbox.objects.filter(teacher=self.teacher).count(), 1)

    def test_notification_preferences_do_not_hide_queue(self):
        self.progress(); self.recording()
        with patch('pabasa_app.views._notification_settings_for_user', return_value={'push_enabled': False}):
            self.queue(summary=1)
        self.assertFalse(Notification.objects.filter(recipient=self.teacher).exists())
        self.assertEqual(self.queue()['total'], 1)

    def test_new_evidence_reopens_grouped_alert_and_completion_resolves_it(self):
        self.progress(); first = self.recording()
        self.queue(summary=1)
        notification = Notification.objects.get(recipient=self.teacher)
        notification.is_read = True; notification.save()
        second = self.recording(index=1)
        self.queue(summary=1)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        self.assertEqual(Notification.objects.filter(recipient=self.teacher).count(), 1)
        StudentActivityRecordingSubmission.objects.filter(pk__in=[first.pk, second.pk]).update(status='checked', teacher_score=1)
        self.queue(summary=1)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(self.queue()['summary']['pending'], 0)
        self.assertFalse(self.queue(summary=1)['notification_changed'])

    def test_missing_active_term_fails_closed(self):
        self.progress(); self.recording()
        self.term_mock.return_value = None
        self.assertEqual(self.queue()['total'], 0)

    def test_school_and_archived_teacher_boundaries(self):
        from .models import School
        self.progress(); self.recording()
        self.teacher.school_record = School.objects.create(name='Other School', code='QUEUE-OTHER')
        self.teacher.save(update_fields=['school_record'])
        self.assertEqual(self.queue()['total'], 0)
        self.teacher.is_archived = True
        self.teacher.save(update_fields=['is_archived'])
        self.assertEqual(self.teacher_client.get(reverse('teacher_review_queue_api')).status_code, 403)

    def test_filters_sort_pagination_and_payload_is_lightweight(self):
        self.progress(); self.recording()
        self.supplementary()
        self.assertEqual(self.queue(category='supplementary')['total'], 1)
        self.assertEqual(self.queue(q='tunog')['total'], 1)
        self.assertEqual(self.queue(section=99999)['total'], 0)
        self.assertEqual(self.queue(term=2)['total'], 0)
        self.assertEqual(self.queue(page='invalid')['page'], 1)
        self.assertNotIn('items', self.queue()['items'][0])
        self.assertNotIn('response_text', self.queue()['items'][0])
        self.assertIn('no-store', self.teacher_client.get(reverse('teacher_review_queue_api')).headers['Cache-Control'])

    def test_inbox_links_to_existing_course_and_drawing_review_screens(self):
        from urllib.parse import urlsplit, parse_qs
        self.progress(); self.recording()
        task = self.task('session-4-gawain-1')
        self.assertEqual(urlsplit(task['review_url']).path, reverse('courses'))
        self.assertEqual(parse_qs(urlsplit(task['review_url']).query)['review_task'], [task['id']])
        detail = self.teacher_client.get(reverse('teacher_review_detail'), {'task': task['id']}).json()['task']
        self.assertEqual(detail['progress_task']['assessmentId'], 'prescribed-session-4-gawain-1')
        self.assertEqual(detail['progress_attempt']['activity_type'], 'session_4_gawain_1')
        self.assertEqual(len(detail['progress_attempt']['session4_recordings']), 1)
        self.progress('aral-s9-a1-family-drawing', activity_completed=False, state={'submitted': True})
        drawing = self.task('aral-s9-a1-family-drawing')
        self.assertEqual(urlsplit(drawing['review_url']).path, reverse('teacher_prescribed_review_page'))
        self.assertEqual(parse_qs(urlsplit(drawing['review_url']).query)['activity'], [drawing['activity_key']])

    def test_inbox_has_no_duplicate_grading_dialog(self):
        response = self.teacher_client.get(reverse('teacher_review_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="nc-review-dialog"')
        self.assertNotContains(response, 'data-confirm-grade')

    def test_twenty_student_queue_uses_batched_queries_and_paginates(self):
        self.setup_scope()
        for index in range(20):
            student = User.objects.create(custom_id=f'QUEUE-{index}', role='student',
                first_name='Reader', last_name=f'{index:02}', email=f'queue-{index}@example.invalid', password_hash='!',
                sex='male', birth_month=1, birth_day=1, birth_year=2018)
            Enrollment.objects.create(student=student, section=self.enrollment.section,
                school=self.enrollment.school, school_calendar=self.calendar, assigned_teacher=self.teacher)
            StudentActivityProgress.objects.create(student=student, school_calendar=self.calendar, term=1,
                activity_key='session-4-gawain-1', activity_completed=True)
            StudentActivityRecordingSubmission.objects.create(student=student, school_calendar=self.calendar,
                term=1, activity_key='session-4-gawain-1', item_index=0, audio_file='disposable/reader.webm')
        # Calendar resolution is mocked; no query per student or activity.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            tasks, _ = inbox.collect(self.teacher)
        self.assertLessEqual(len(queries), 7)
        self.assertEqual(len(tasks), 20)
        self.assertEqual(len(self.queue()['items']), 12)
        self.assertEqual(len(self.queue(page=2)['items']), 8)
