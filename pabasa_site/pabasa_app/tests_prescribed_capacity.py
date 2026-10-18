import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import PrescribedReadingAttempt, School, StudentActivityRecordingSubmission, User
from .prescribed_test_fixtures import prescribed_term_fixture


class PrescribedFailureRecoveryTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory(prefix='pabasa-recording-test-')
        self.addCleanup(self.media.cleanup)
        self.settings_override=self.settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        school=School.objects.create(name='Capacity Fixture',code='PRESCRIBED-CAPACITY')
        self.student=User.objects.create(custom_id='PRESCRIBED-CAPACITY-STUDENT',role='student',
            first_name='Synthetic',last_name='Student',sex='female',birth_month=1,birth_day=1,
            birth_year=2012,password_hash='unused',school_record=school)
        _calendar,section,_enrollment,_result=prescribed_term_fixture(self.student)
        self.teacher=section.teacher
        session=self.client.session
        session.update({'user_id':self.student.pk,'user_role':'student'})
        session.save()
        self.client.raise_request_exception=False

    def recording(self,**fields):
        data={'audio':SimpleUploadedFile('synthetic.webm',b'synthetic recording','audio/webm'),
              'item_index':'0','duration_seconds':'2',**fields}
        return self.client.post(reverse('session_5_lesson_14_gawain_4_recording'),data)

    def test_invalid_recording_duration_is_rejected_before_a_file_or_row_is_saved(self):
        for duration in ('not-a-number','NaN','Infinity','-2'):
            with self.subTest(duration=duration):
                self.assertEqual(self.recording(duration_seconds=duration).status_code,400)
        self.assertFalse(StudentActivityRecordingSubmission.objects.filter(student=self.student).exists())
        self.assertEqual(list(Path(self.media.name).rglob('*.webm')),[])

    def test_non_object_json_is_a_client_error_for_progress_and_completion(self):
        for route in ('prescribed_activity_progress','prescribed_activity_complete'):
            for payload in ([],None,'invalid',1):
                with self.subTest(route=route,payload=payload), \
                     patch('pabasa_app.views._student_can_open_prescribed_activity',return_value=True):
                    response=self.client.post(reverse(route,kwargs={'activity_key':'lesson-27-gawain-1'}),
                        data=json.dumps(payload),content_type='application/json')
                    self.assertEqual(response.status_code,400)

    def test_missing_teacher_recording_returns_not_found_after_authorization(self):
        row=StudentActivityRecordingSubmission.objects.create(student=self.student,
            activity_key='lesson-13-gawain-1',item_index=0,audio_file='activity_recordings/missing.webm')
        session=self.client.session
        session.update({'user_id':self.teacher.pk,'user_role':'teacher'})
        session.save()
        self.assertEqual(self.client.get(reverse('teacher_lesson_13_gawain_1_audio',args=[row.pk])).status_code,404)
        session=self.client.session
        session.update({'user_id':self.student.pk,'user_role':'student'})
        session.save()
        self.assertIn(self.client.get(reverse('teacher_lesson_13_gawain_1_audio',args=[row.pk])).status_code,(302,403))

    def test_attempt_retry_is_idempotent_and_analysis_is_queued_after_commit(self):
        identifier=str(uuid.uuid4())
        with self.captureOnCommitCallbacks(execute=False) as callbacks, \
             patch('pabasa_app.views.analyze_reading_attempt') as analyze:
            first=self.recording(attempt_id=identifier)
            self.assertEqual(first.status_code,200)
            self.assertEqual(len(callbacks),0)  # populated when the capture exits
            analyze.assert_not_called()
        self.assertEqual(len(callbacks),1)
        attempt=PrescribedReadingAttempt.objects.get(attempt_id=identifier)
        self.assertEqual(attempt.audio_analysis_status,'pending')
        name=attempt.audio_file.name
        replay=self.recording(attempt_id=identifier)
        self.assertEqual(replay.status_code,200)
        self.assertTrue(replay.json()['already_saved'])
        self.assertEqual(PrescribedReadingAttempt.objects.filter(student=self.student).count(),1)
        self.assertEqual(StudentActivityRecordingSubmission.objects.get(student=self.student).audio_file.name,name)

    def test_foreign_attempt_cannot_replace_the_students_existing_audio(self):
        own=self.recording(attempt_id=str(uuid.uuid4()))
        self.assertEqual(own.status_code,200)
        row=StudentActivityRecordingSubmission.objects.get(student=self.student)
        name=row.audio_file.name
        stranger=User.objects.create(custom_id='PRESCRIBED-CAPACITY-OTHER',role='student',
            first_name='Synthetic',last_name='Other',sex='female',birth_month=1,birth_day=1,
            birth_year=2012,password_hash='unused',school_record=self.student.school_record)
        foreign=PrescribedReadingAttempt.objects.create(student=stranger,
            activity_key='session-5-lesson-14-gawain-4',item_index=0,audio_file='activity_recordings/foreign.webm')
        self.assertEqual(self.recording(attempt_id=str(foreign.attempt_id)).status_code,403)
        row.refresh_from_db()
        self.assertEqual(row.audio_file.name,name)
        self.assertTrue(Path(self.media.name,name).exists())

    def test_replacement_retains_the_prior_attempt_recording(self):
        self.assertEqual(self.recording(attempt_id=str(uuid.uuid4())).status_code,200)
        previous=PrescribedReadingAttempt.objects.get(student=self.student)
        self.assertEqual(self.recording(attempt_id=str(uuid.uuid4())).status_code,200)
        previous.refresh_from_db()
        self.assertTrue(Path(self.media.name,previous.audio_file.name).exists())
        self.assertEqual(list(PrescribedReadingAttempt.objects.filter(student=self.student).values_list('attempt_number',flat=True)),[1,2])
