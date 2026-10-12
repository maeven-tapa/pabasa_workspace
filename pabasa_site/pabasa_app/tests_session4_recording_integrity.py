"""Recording-only Session 4 letter review regressions."""
import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from . import tests_lesson15_reading as fixtures
from .models import StudentActivityProgress, StudentActivityRecordingSubmission


class Session4RecordingIntegrityTests(TestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def upload(self, activity, *, item_index=0, substep=None, content=b'first recording'):
        fields = {
            'item_index': str(item_index),
            'audio': SimpleUploadedFile('letter.webm', content, content_type='audio/webm'),
        }
        if substep is not None:
            fields['substep'] = str(substep)
        return self.student_client.post(reverse(f'{activity}_recording'), fields)

    def score(self, activity, submission_id, value):
        return self.teacher_client.post(
            reverse(f'teacher_{activity}_score'),
            data=json.dumps({'submission_id': submission_id, 'score': value}),
            content_type='application/json',
        )

    def test_gawain2_replacement_requires_new_teacher_score(self):
        activity = 'session_4_gawain_2'
        key = 'session-4-gawain-2'
        progress = StudentActivityProgress.objects.create(
            student=self.student, activity_key=key, school_calendar=self.calendar,
            term=1, completed_items=1, correct_items=1,
        )
        first = self.upload(activity, item_index=0, substep=0)
        self.assertEqual(first.status_code, 200, first.content)
        row = StudentActivityRecordingSubmission.objects.get(pk=first.json()['recording_id'])
        self.assertEqual((row.student_id, row.activity_key, row.item_index, row.substep),
                         (self.student.pk, key, 0, 0))
        self.assertEqual((row.status, row.teacher_score, row.checked_by_id, row.checked_at),
                         ('submitted', None, None, None))

        for value in (0, 1):
            reviewed = self.score(activity, row.pk, value)
            self.assertEqual(reviewed.status_code, 200, reviewed.content)
            row.refresh_from_db()
            self.assertEqual((row.status, row.teacher_score, row.checked_by_id),
                             ('checked', value, self.teacher.pk))
            self.assertIsNotNone(row.checked_at)

            failed = self.student_client.post(reverse(f'{activity}_recording'),
                {'item_index': '0', 'substep': '0'})
            self.assertEqual(failed.status_code, 400)
            row.refresh_from_db()
            self.assertEqual((row.status, row.teacher_score), ('checked', value))

            replaced = self.upload(activity, item_index=0, substep=0,
                                   content=f'replacement {value}'.encode())
            self.assertEqual(replaced.status_code, 200, replaced.content)
            self.assertEqual(replaced.json()['recording_id'], row.pk)
            row.refresh_from_db()
            self.assertEqual((row.student_id, row.activity_key, row.item_index, row.substep),
                             (self.student.pk, key, 0, 0))
            self.assertEqual((row.status, row.teacher_score, row.checked_by_id, row.checked_at),
                             ('submitted', None, None, None))
            self.assertTrue(row.audio_file)
            review = self.teacher_client.get(reverse('teacher_session_4_gawain_2_recordings'),
                                             {'student_id': self.student.pk})
            self.assertEqual(review.status_code, 200)
            letter = review.json()['items'][0]
            self.assertEqual((letter['item_label'], letter['status'], letter['teacher_score']),
                             ('b', 'submitted', None))
            self.assertTrue(letter['recording_available'])
            self.assertTrue(letter['audio_url'])
            self.assertEqual(review.json()['automatic_subtotal'], progress.completed_items)

    def test_gawain1_page_restores_uploaded_audio_without_progress(self):
        activity = 'session_4_gawain_1'
        first = self.upload(activity, item_index=1)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertFalse(StudentActivityProgress.objects.filter(
            student=self.student, activity_key='session-4-gawain-1').exists())
        with patch('pabasa_app.views._enforce_prescribed_activity_sequence', return_value=None):
            page = self.student_client.get(reverse('session_4_gawain_1_page'))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['lesson13_data']['recorded_items'], [1])
        self.assertTrue(page.context['lesson13_data']['has_incomplete_progress'])
        self.assertEqual(page.context['lesson13_data']['progress']['current_index'], 0)
        self.assertIn('data.recorded_items', page.content.decode())

        row = StudentActivityRecordingSubmission.objects.get(pk=first.json()['recording_id'])
        self.assertEqual((row.status, row.teacher_score), ('submitted', None))
        review = self.teacher_client.get(reverse('teacher_session_4_gawain_1_recordings'),
                                         {'student_id': self.student.pk})
        self.assertEqual(review.status_code, 200)
        self.assertEqual((review.json()['items'][1]['item_label'],
                          review.json()['items'][1]['teacher_score']), ('b', None))
        self.assertTrue(review.json()['items'][1]['audio_url'])
        scored = self.score(activity, row.pk, 1)
        self.assertEqual(scored.status_code, 200, scored.content)
        row.refresh_from_db()
        self.assertEqual((row.status, row.teacher_score), ('checked', 1))

    def test_failed_gawain1_upload_does_not_create_recording_or_progress(self):
        response = self.student_client.post(reverse('session_4_gawain_1_recording'),
                                            {'item_index': '0'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentActivityRecordingSubmission.objects.filter(
            student=self.student, activity_key='session-4-gawain-1').exists())
        self.assertFalse(StudentActivityProgress.objects.filter(
            student=self.student, activity_key='session-4-gawain-1').exists())
