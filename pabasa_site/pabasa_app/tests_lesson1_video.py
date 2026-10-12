"""Lesson 1 video recording contracts, using disposable records and media."""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from . import tests_lesson15_reading as fixtures
from .models import StudentActivityProgress, StudentActivityRecordingSubmission


class Lesson1VideoSubmissionTests(TestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def submit(self, **overrides):
        fields = dict(audio=SimpleUploadedFile('song.webm', b'disposable-recording', 'audio/webm'),
                      duration_seconds='88', video_completed='true')
        fields.update(overrides)
        return self.student_client.post(reverse('lesson_1_gawain_1_submit'), fields)

    def test_video_submission_is_stored_once_and_pending_on_reload(self):
        first = self.submit()
        self.assertEqual(first.status_code, 200)
        second = self.submit()
        self.assertTrue(second.json()['already_submitted'])
        self.assertEqual(first.json()['submission_id'], second.json()['submission_id'])
        self.assertEqual(StudentActivityRecordingSubmission.objects.count(), 1)
        submission = StudentActivityRecordingSubmission.objects.get()
        self.assertEqual(submission.status, 'submitted')
        self.assertTrue(Path(submission.audio_file.path).exists())
        with patch('pabasa_app.views._dashboard_context', return_value={}):
            response = self.student_client.get(reverse('lesson_1_gawain_1_page'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StudentActivityProgress.objects.get().activity_completed)
        self.assertEqual(response.context['lesson_1_data']['submission_status'], 'submitted')
        self.assertContains(response, 'session1_lesson1_gawain1.mp4')

    def test_empty_unfinished_and_invalid_duration_cannot_submit(self):
        for fields in (
            {'audio': SimpleUploadedFile('empty.webm', b'', 'audio/webm')},
            {'video_completed': 'false'}, {'video_completed': ''},
            {'duration_seconds': '0'}, {'duration_seconds': 'invalid'},
        ):
            with self.subTest(fields=list(fields)):
                self.assertEqual(self.submit(**fields).status_code, 400)
        self.assertFalse(StudentActivityRecordingSubmission.objects.exists())
        self.assertFalse(StudentActivityProgress.objects.exists())

    def test_legacy_progress_cannot_bypass_recording_or_teacher_review(self):
        url = reverse('lesson_3_activity_progress')
        payload = dict(activity_key='lesson-1-gawain-1', current_index=1,
                       completed_items=1, correct_items=0, total_items=1, activity_completed=True)
        self.assertEqual(self.student_client.post(url, payload, content_type='application/json').status_code, 400)
        self.submit()
        payload['reset'] = True
        self.assertEqual(self.student_client.post(url, payload, content_type='application/json').status_code, 400)
        self.assertFalse(StudentActivityProgress.objects.get().activity_completed)
        self.assertEqual(StudentActivityRecordingSubmission.objects.get().status, 'submitted')

    def test_activity_issues_csrf_cookie_for_automatic_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.student_client.cookies
        with patch('pabasa_app.views._dashboard_context', return_value={}):
            self.assertEqual(client.get(reverse('lesson_1_gawain_1_page')).status_code, 200)
        self.assertIn('csrftoken', client.cookies)
        fields = dict(audio=SimpleUploadedFile('song.webm', b'disposable-recording', 'audio/webm'),
                      duration_seconds='88', video_completed='true')
        response = client.post(reverse('lesson_1_gawain_1_submit'), fields,
                               HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_list_play_review_and_request_rerecording(self):
        submission_id = self.submit().json()['submission_id']
        progress = StudentActivityProgress.objects.get()
        self.assertEqual((progress.school_calendar_id, progress.term), (self.calendar.pk, 1))
        availability_url = reverse('teacher_prescribed_review_availability')
        activity_id = 'prescribed-lesson-1-gawain-1'
        params = {'student_id': self.student.pk, 'activity_id': activity_id}
        availability = self.teacher_client.get(availability_url, params).json()
        self.assertFalse(availability['completed'][activity_id])
        self.assertTrue(availability['reviewable'][activity_id], 'Teacher must be able to review before approval')
        listing = self.teacher_client.get(reverse('teacher_lesson_1_gawain_1_recordings')).json()
        self.assertEqual(listing['submissions'][0]['id'], submission_id)
        audio_url = listing['submissions'][0]['recording_url']
        response = self.teacher_client.get(audio_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'disposable-recording')
        self.assertEqual(self.client_for(self.other).get(audio_url).status_code, 403)
        review_url = reverse('teacher_lesson_1_gawain_1_review_action')
        payload = {'submission_id': submission_id, 'action': 'retry'}
        self.assertEqual(self.teacher_client.post(review_url, payload, content_type='application/json').status_code, 200)
        progress.refresh_from_db()
        self.assertFalse(progress.activity_completed)
        self.assertEqual((progress.current_index, progress.completed_items, progress.correct_items), (0, 0, 0))
        self.assertTrue(progress.state['retry_requested'])
        self.assertFalse(self.teacher_client.get(availability_url, params).json()['reviewable'][activity_id])
        with patch('pabasa_app.views._dashboard_context', return_value={}):
            page = self.student_client.get(reverse('lesson_1_gawain_1_page'))
        self.assertEqual(page.context['lesson_1_data']['submission_status'], 'retry')
        payload['action'] = 'checked'
        self.assertEqual(self.teacher_client.post(review_url, payload, content_type='application/json').status_code, 409)
        self.assertEqual(self.submit().json()['submission_id'], submission_id)
        self.assertEqual(StudentActivityRecordingSubmission.objects.count(), 1)
        self.assertTrue(self.teacher_client.get(availability_url, params).json()['reviewable'][activity_id])
        payload['action'] = 'checked'
        self.assertEqual(self.teacher_client.post(review_url, payload, content_type='application/json').status_code, 200)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)
        self.assertEqual((progress.correct_items, progress.total_items), (1, 1))
        self.assertTrue(self.teacher_client.get(availability_url, params).json()['completed'][activity_id])
        self.assertEqual(self.teacher_client.post(review_url, payload, content_type='application/json').status_code, 200)
        self.assertEqual(self.submit().json()['status'], 'checked')
        with patch('pabasa_app.views._dashboard_context', return_value={}):
            response = self.student_client.get(reverse('lesson_1_gawain_1_page'))
        self.assertEqual(response.context['lesson_1_data']['submission_status'], 'checked')

    def test_old_term_recording_cannot_unlock_or_complete_current_term(self):
        submission_id = self.submit().json()['submission_id']
        StudentActivityProgress.objects.update(term=2)
        activity_id = 'prescribed-lesson-1-gawain-1'
        data = self.teacher_client.get(reverse('teacher_prescribed_review_availability'),
            {'student_id': self.student.pk, 'activity_id': activity_id}).json()
        self.assertFalse(data['reviewable'][activity_id])
        response = self.teacher_client.post(reverse('teacher_lesson_1_gawain_1_review_action'),
            {'submission_id': submission_id, 'action': 'checked'}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(StudentActivityRecordingSubmission.objects.get().status, 'submitted')
        self.assertFalse(StudentActivityProgress.objects.get().activity_completed)

    def test_invalid_or_unauthorized_reviews_cannot_change_submission(self):
        submission_id = self.submit().json()['submission_id']
        url = reverse('teacher_lesson_1_gawain_1_review_action')
        for body in ('{', '[]', '{}', '{"submission_id":"invalid"}'):
            self.assertEqual(self.teacher_client.post(url, body, content_type='application/json').status_code, 400)
        response = self.client_for(self.other).post(url,
            {'submission_id': submission_id, 'action': 'checked'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(StudentActivityRecordingSubmission.objects.get().status, 'submitted')


class Lesson1VideoBrowserTests(SimpleTestCase):
    def test_playback_recording_and_failure_lifecycle(self):
        self.run_browser()

    def test_start_modal_narration_sequence(self):
        self.run_browser(narration=True)

    def run_browser(self, narration=False):
        script = Path(__file__).resolve().parents[2] / 'tools/test_lesson1_video.cjs'
        environment = dict(os.environ, PABASA_PYTHON=sys.executable)
        environment.pop('PABASA_VIDEO_QUICK', None)
        environment.pop('PABASA_VIDEO_MODES', None)
        environment.pop('PABASA_VIDEO_LAYOUT_ONLY', None)
        environment.pop('PABASA_VIDEO_INDICATOR_ONLY', None)
        environment.pop('PABASA_VIDEO_NARRATION_ONLY', None)
        if narration:
            environment['PABASA_VIDEO_NARRATION_ONLY'] = '1'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True,
                                env=environment, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
