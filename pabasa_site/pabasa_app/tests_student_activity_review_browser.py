"""Seven scoped course review layouts using disposable records and real APIs."""
import io
import json
import os
import subprocess
import uuid
import wave
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import StudentActivityProgress, StudentActivityRecordingSubmission
from .prescribed_activity_catalog import prescribed_activity
from . import tests_lesson15_reading as fixtures


class StudentActivityReviewBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for
    current = fixtures.Lesson15ReadingTests.current
    skip = fixtures.Lesson15ReadingTests.skip

    def test_lesson1_pending_recording_review_and_full_credit(self):
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as recording:
            recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            recording.writeframes(b'\0\0' * 32000)
        submitted = self.student_client.post(reverse('lesson_1_gawain_1_submit'), {
            'audio': SimpleUploadedFile('lesson1.wav', audio.getvalue(), 'audio/wav'),
            'duration_seconds': '2', 'video_completed': 'true',
        })
        self.assertEqual(submitted.status_code, 200)
        progress = StudentActivityProgress.objects.get(student=self.student,
            activity_key='lesson-1-gawain-1', school_calendar=self.calendar, term=1)
        self.assertFalse(progress.activity_completed)
        row = self.teacher_client.get(reverse('teacher_lesson_1_gawain_1_recordings')).json()['submissions'][0]
        attempts = {'prescribed-lesson-1-gawain-1': {'attempts': [{
            'student_id': self.student.pk, 'activity_type': 'lesson_1_recording',
            'status': row['status'], 'submission_id': row['id'],
            'recording_available': True, 'recording_url': row['recording_url'],
            'recording_duration_seconds': row['duration_seconds'],
            'can_retry': row['can_retry'], 'can_check': row['can_check'],
        }]}}
        names = ['teacher_prescribed_review_availability', 'teacher_lesson_1_gawain_1_review_action']
        environment = dict(os.environ, PABASA_REVIEW_SERVER=self.live_server_url,
            PABASA_REVIEW_TEACHER_COOKIE=self.teacher_client.cookies['sessionid'].value,
            PABASA_REVIEW_STUDENT_ID=str(self.student.pk), PABASA_REVIEW_LESSON1_ONLY='1',
            PABASA_REVIEW_ATTEMPTS=json.dumps(attempts),
            PABASA_REVIEW_URLS=json.dumps({name: reverse(name) for name in names}))
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_student_activity_review.cjs'
        result = subprocess.run(['node', str(script)], env=environment,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)
        self.assertEqual((progress.correct_items, progress.total_items), (1, 1))
        fresh = self.teacher_client.get(reverse('teacher_lesson_1_gawain_1_recordings')).json()['submissions'][0]
        self.assertEqual(fresh['status'], 'checked')
        self.assertFalse(fresh['can_check'])
        self.assertFalse(fresh['can_retry'])
        print(result.stdout.strip())

    def test_completion_gate_with_real_status_refresh_and_direct_events(self):
        # Not started L1 has a reviewed submission; that must NOT unlock review.
        StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key='lesson-1-gawain-1', status='checked')
        StudentActivityProgress.objects.create(student=self.student,
            activity_key='lesson-13-gawain-1', school_calendar=self.calendar, term=1,
            current_index=4, activity_completed=True)
        # Leave L15 at the last item so the browser can complete it via the
        # actual student API, then observe a fresh server completion response.
        for _ in range(21):
            self.assertEqual(self.skip().status_code, 200)
        urls = {'teacher_prescribed_review_availability': reverse('teacher_prescribed_review_availability'),
                'lesson15_reading_skip': reverse('lesson15_reading_skip'),
                'lesson15_progress': reverse('prescribed_activity_progress', args=['lesson-15-gawain-3'])}
        environment = dict(os.environ, PABASA_REVIEW_SERVER=self.live_server_url,
            PABASA_REVIEW_TEACHER_COOKIE=self.teacher_client.cookies['sessionid'].value,
            PABASA_REVIEW_STUDENT_COOKIE=self.student_client.cookies['sessionid'].value,
            PABASA_REVIEW_STUDENT_ID=str(self.student.pk), PABASA_REVIEW_URLS=json.dumps(urls),
            PABASA_REVIEW_GATE_ONLY='1',
            PABASA_REVIEW_STATE_VERSION=str(self.current().state['state_version']))
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_student_activity_review.cjs'
        result = subprocess.run(['node', str(script)], env=environment,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.current().activity_completed, 'Only the disposable L15 activity was restarted for the stale-cache test')
        self.assertTrue(StudentActivityProgress.objects.get(student=self.student,
            activity_key='lesson-13-gawain-1', school_calendar=self.calendar, term=1).activity_completed)
        self.assertEqual(StudentActivityRecordingSubmission.objects.get(student=self.student,
            activity_key='lesson-1-gawain-1').status, 'checked')
        print(result.stdout.strip())

    def test_seven_course_review_layouts_and_real_saves(self):
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as recording:
            recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            recording.writeframes(b'\0\0' * 32000)
        # Each activity has one valid pending recording; fluency reviews also
        # have a skipped item. All other inventory rows remain unattempted.
        self.assertEqual(self.skip().status_code, 200)
        with patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('sawa', 'chirp_3', '')):
            evidence = self.student_client.post(reverse('reading_transcribe_api'), {
                'target_text': 'sawa', 'language': 'Filipino', 'mode': 'word',
                'prescribed_activity_key': 'lesson-15-gawain-3', 'item_index': 1,
                'state_version': self.current().state['state_version'], 'attempt_id': str(uuid.uuid4()),
                'audio': SimpleUploadedFile('reading.wav', audio.getvalue(), content_type='audio/wav'),
            })
        self.assertEqual(evidence.status_code, 200, evidence.content)
        keys = ['lesson-13-gawain-1', 'session-4-gawain-2', 'session-5-lesson-14-gawain-4',
                'session-4-gawain-1', 'lesson-29-gawain-3']
        for key in keys:
            index = 1 if key == keys[2] else 0
            StudentActivityRecordingSubmission.objects.create(
                student=self.student, activity_key=key, item_index=index,
                substep=0 if key == keys[1] else None,
                audio_file=SimpleUploadedFile('review.wav', audio.getvalue(), content_type='audio/wav'),
                expected_text=(prescribed_activity(key)['items'][index].get('text', '')),
                recognized_transcript='test reading', review_status='pending',
            )
        StudentActivityProgress.objects.create(student=self.student, activity_key=keys[2],
            school_calendar=self.calendar, term=1, current_index=2, state={
                'classification_sources': {'0': 'skipped'}, 'fluency_classifications': {'0': 'RED'},
            })
        lesson1 = StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key='lesson-1-gawain-1', duration_seconds=2,
            audio_file=SimpleUploadedFile('lesson1.wav', audio.getvalue(), content_type='audio/wav'))
        # Review opening now requires actual current-term completion, not pending
        # recording/review status. These are disposable completed activity fixtures.
        for key in keys + ['lesson-1-gawain-1', 'lesson-15-gawain-3']:
            StudentActivityProgress.objects.update_or_create(student=self.student, activity_key=key,
                school_calendar=self.calendar, term=1, defaults={'activity_completed': True})
        # Lesson 1 is pending teacher approval. Its submitted recording must
        # already open for review, without inventing completion to unlock it.
        StudentActivityProgress.objects.filter(student=self.student, activity_key='lesson-1-gawain-1',
            school_calendar=self.calendar, term=1).update(activity_completed=False,
                state={'submitted': True, 'submission_id': lesson1.pk})
        urls = {name: reverse(name) for name in [
            'teacher_lesson_13_gawain_1_score', 'teacher_session_4_gawain_2_score',
            'teacher_session_5_lesson_14_gawain_4_classify', 'lesson15_reading_classify',
            'teacher_session_5_lesson_14_gawain_4_recordings', 'lesson15_reading_reviews',
            'teacher_session_4_gawain_1_score', 'teacher_lesson29_trace_say_score',
            'teacher_lesson_1_gawain_1_review_action',
            'teacher_prescribed_review_availability',
        ]}
        attempts = {}
        review_names = ['teacher_lesson_13_gawain_1_recordings', 'teacher_session_4_gawain_2_recordings',
                       'teacher_session_5_lesson_14_gawain_4_recordings', 'teacher_session_4_gawain_1_recordings',
                       'teacher_lesson29_trace_say_recordings', 'lesson15_reading_reviews']
        activity_keys = keys + ['lesson-15-gawain-3']
        for key, name in zip(activity_keys, review_names):
            response = self.teacher_client.get(reverse(name), {'student_id': self.student.pk})
            self.assertEqual(response.status_code, 200, response.content)
            rows = response.json()['items']
            self.assertEqual(len(rows), {'lesson-13-gawain-1': 4, 'session-4-gawain-2': 8,
                                        'session-5-lesson-14-gawain-4': 22, 'lesson-15-gawain-3': 22,
                                        'session-4-gawain-1': 4, 'lesson-29-gawain-3': 11}[key])
            fluency = key in {'session-5-lesson-14-gawain-4', 'lesson-15-gawain-3'}
            attempts['prescribed-' + key] = {'attempts': [{
                'student_id': self.student.pk, 'status': 'in_progress',
                'activity_type': 'session_5_fluency' if fluency else 'lesson_29_trace_say' if key == 'lesson-29-gawain-3' else key.replace('-', '_'),
                'lesson15_review': key == 'lesson-15-gawain-3',
                'session5_recordings' if fluency else 'session4_recordings': rows,
                'can_retry': key == 'lesson-29-gawain-3', 'can_check': False,
            }]}
        response = self.teacher_client.get(reverse('teacher_lesson_1_gawain_1_recordings'))
        self.assertEqual(response.status_code, 200)
        row = response.json()['submissions'][0]
        self.assertEqual(row['id'], lesson1.pk)
        attempts['prescribed-lesson-1-gawain-1'] = {'attempts': [{
            'student_id': self.student.pk, 'activity_type': 'lesson_1_recording',
            'status': row['status'], 'submission_id': row['id'],
            'recording_available': bool(row['recording_url']), 'recording_url': row['recording_url'],
            'recording_duration_seconds': row['duration_seconds'],
            'can_retry': row['can_retry'], 'can_check': row['can_check'],
        }]}
        environment = dict(os.environ,
            PABASA_REVIEW_SERVER=self.live_server_url,
            PABASA_REVIEW_TEACHER_COOKIE=self.teacher_client.cookies['sessionid'].value,
            PABASA_REVIEW_STUDENT_ID=str(self.student.pk),
            PABASA_REVIEW_ATTEMPTS=json.dumps(attempts), PABASA_REVIEW_URLS=json.dumps(urls),
        )
        # The configured runtime is supplied by the caller, not installed here.
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_student_activity_review.cjs'
        result = subprocess.run(['node', str(script)], env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for key in keys:
            row = StudentActivityRecordingSubmission.objects.get(student=self.student, activity_key=key)
            if key == keys[2]:
                self.assertEqual((row.fluency_classification, row.classification_source, row.review_status),
                                 ('RED', 'teacher', 'reviewed'))
            else:
                self.assertEqual(row.teacher_score, 1)
        # Fresh endpoint responses retain the grades, without counting skips
        # as teacher reviews or adding controls to unattempted rows.
        for key, name in zip(activity_keys, review_names):
            rows = self.teacher_client.get(reverse(name), {'student_id': self.student.pk}).json()['items']
            if key in {'session-5-lesson-14-gawain-4', 'lesson-15-gawain-3'}:
                self.assertEqual(rows[0]['classification_source'], 'skipped')
                self.assertEqual(rows[1]['classification'], 'RED')
                self.assertEqual(sum(row['review_status'] == 'reviewed' for row in rows), 1)
            else:
                self.assertEqual(rows[0]['teacher_score'], 1)
                self.assertEqual(sum(row['teacher_score'] is not None for row in rows), 1)
        lesson1.refresh_from_db()
        self.assertEqual(lesson1.status, 'checked')
        self.assertIsNone(lesson1.teacher_score, 'Lesson 1 remains a check/retry review, not binary or fluency scoring')
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-1-gawain-1',
            school_calendar=self.calendar, term=1)
        self.assertTrue(progress.activity_completed)
        self.assertEqual((progress.correct_items, progress.total_items), (1, 1))
        fresh = self.teacher_client.get(reverse('teacher_lesson_1_gawain_1_recordings')).json()['submissions'][0]
        self.assertEqual(fresh['status'], 'checked')
        self.assertFalse(fresh['can_check'])
        self.assertFalse(fresh['can_retry'])
        print(result.stdout.strip())
