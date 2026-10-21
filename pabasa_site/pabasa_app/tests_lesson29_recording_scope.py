from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction, IntegrityError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from . import tests_lesson15_reading as fixtures
from .models import StudentActivityRecordingSubmission as Recording, StudentActivityProgress, SchoolCalendar, Section, Enrollment


class Lesson29RecordingScopeTests(TestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def upload(self):
        return self.student_client.post(reverse('lesson29_trace_say_recording'), {
            'item_index':0, 'duration_seconds':2,
            'audio':SimpleUploadedFile('scope.webm', b'local-test-recording', content_type='audio/webm')})

    def review(self):
        return self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
                                       {'student_id':self.student.pk}).json()

    def test_new_term_upload_preserves_old_recording_and_rejects_old_review(self):
        old_id = self.upload().json()['recording_id']
        old = Recording.objects.get(pk=old_id)
        old.teacher_score = 1
        old.save(update_fields=['teacher_score'])
        original_name = old.audio_file.name
        self.scope['term'] = 2
        self.assertFalse(self.review()['items'][0]['recording_available'])
        self.assertFalse(self.review()['started'])
        for name in ('teacher_lesson29_trace_say_score',):
            result = self.teacher_client.post(reverse(name), {'submission_id':old_id,'score':0},content_type='application/json')
            self.assertEqual(result.status_code,403)
        self.assertEqual(self.teacher_client.get(reverse('teacher_lesson29_trace_say_audio',args=[old_id])).status_code,403)
        new_id = self.upload().json()['recording_id']
        self.assertNotEqual(old_id,new_id)
        old.refresh_from_db()
        self.assertEqual(old.teacher_score,1)
        self.assertEqual(old.audio_file.name,original_name)
        self.assertTrue(old.audio_file.storage.exists(original_name))
        self.assertEqual(Recording.objects.get(pk=new_id).term,2)
        self.assertEqual(self.review()['items'][0]['submission_id'],new_id)
        self.assertEqual(self.teacher_client.post(reverse('teacher_lesson29_trace_say_score'),
            {'submission_id':new_id,'score':1},content_type='application/json').status_code,200)
        repeated = self.upload().json()['recording_id']
        self.assertEqual(repeated,new_id)
        self.assertIsNone(Recording.objects.get(pk=new_id).teacher_score)

    def test_old_recordings_cannot_submit_approve_or_be_reset_by_current_term(self):
        old_rows = [Recording.objects.create(student=self.student,activity_key='lesson-29-gawain-3',
            school_calendar=self.calendar,term=1,item_index=i,teacher_score=1,status='checked',audio_file=f'old-{i}.webm') for i in range(11)]
        self.scope['term']=2
        progress=StudentActivityProgress.objects.create(student=self.student,school_calendar=self.calendar,
            term=2,activity_key='lesson-29-gawain-3',state={'submitted':True},total_items=11)
        self.assertEqual(self.student_client.post(reverse('lesson29_trace_say_submit'),{},content_type='application/json').status_code,400)
        response=self.teacher_client.post(reverse('teacher_lesson29_trace_say_review_action'),
            {'student_id':self.student.pk,'action':'checked'},content_type='application/json')
        self.assertEqual(response.status_code,409)
        response=self.teacher_client.post(reverse('teacher_lesson29_trace_say_review_action'),
            {'student_id':self.student.pk,'action':'retry'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(Recording.objects.filter(pk__in=[r.pk for r in old_rows],status='checked',teacher_score=1).count(),11)
        progress.refresh_from_db()
        self.assertFalse(progress.activity_completed)

    def test_school_years_and_same_term_uniqueness(self):
        first=self.upload().json()['recording_id']
        self.scope['school_calendar']=SchoolCalendar.objects.create(school_year='2027-2028',current_term=1)
        original = Section.objects.get(teacher=self.teacher)
        section = Section.objects.create(school=original.school, school_calendar=self.scope['school_calendar'],
            teacher=self.teacher, class_code='SCOPE-NEXT', class_name='Next year', subject='Reading')
        Enrollment.objects.create(student=self.student, section=section, school=original.school,
            school_calendar=self.scope['school_calendar'], assigned_teacher=self.teacher)

        self.assertFalse(self.review()['items'][0]['recording_available'])
        second=self.upload().json()['recording_id']
        self.assertNotEqual(first,second)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recording.objects.create(student=self.student,activity_key='lesson-29-gawain-3',
                school_calendar=self.scope['school_calendar'],term=1,item_index=0)

    def test_previous_year_teacher_cannot_list_score_play_or_review_current_recordings(self):
        old = Section.objects.get(teacher=self.teacher)
        calendar = SchoolCalendar.objects.create(school_year='2027-2028', current_term=1, is_active=True)
        self.calendar.is_active = False
        self.calendar.save(update_fields=['is_active'])
        section = Section.objects.create(school=old.school, school_calendar=calendar, teacher=self.other,
            class_code='NEW-OWNER', class_name='New teacher', subject='Reading')
        Enrollment.objects.create(student=self.student, section=section, school=old.school,
            school_calendar=calendar, assigned_teacher=self.other)
        self.scope['school_calendar'] = calendar
        recording_id = self.upload().json()['recording_id']
        progress = StudentActivityProgress.objects.create(student=self.student, school_calendar=calendar,
            term=1, activity_key='lesson-29-gawain-3', state={'submitted':True})
        record_before = Recording.objects.filter(pk=recording_id).values().get()
        progress_before = StudentActivityProgress.objects.filter(pk=progress.pk).values().get()
        self.assertEqual(self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings'),
            {'student_id':self.student.pk}).status_code,403)
        self.assertEqual(self.teacher_client.get(reverse('teacher_lesson29_trace_say_recordings')).json()['submissions'],[])
        self.assertEqual(self.teacher_client.post(reverse('teacher_lesson29_trace_say_score'),
            {'submission_id':recording_id,'score':1},content_type='application/json').status_code,403)
        self.assertEqual(self.teacher_client.get(reverse('teacher_lesson29_trace_say_audio',args=[recording_id])).status_code,403)
        self.assertEqual(self.teacher_client.post(reverse('teacher_lesson29_trace_say_review_action'),
            {'student_id':self.student.pk,'action':'retry'},content_type='application/json').status_code,403)
        self.assertEqual(Recording.objects.filter(pk=recording_id).values().get(),record_before)
        self.assertEqual(StudentActivityProgress.objects.filter(pk=progress.pk).values().get(),progress_before)
        current_teacher = self.client_for(self.other)
        self.assertEqual(current_teacher.get(reverse('teacher_lesson29_trace_say_recordings'),
            {'student_id':self.student.pk}).status_code,200)
        self.assertEqual(len(current_teacher.get(reverse('teacher_lesson29_trace_say_recordings')).json()['submissions']),1)
        audio = current_teacher.get(reverse('teacher_lesson29_trace_say_audio',args=[recording_id]))
        self.assertEqual(audio.status_code,200)
        audio.close()
        self.assertEqual(current_teacher.post(reverse('teacher_lesson29_trace_say_score'),
            {'submission_id':recording_id,'score':1},content_type='application/json').status_code,200)


class Lesson29LegacyMigrationTests(TransactionTestCase):
    def test_migration_preserves_old_recordings_without_guessing_a_scope(self):
        from datetime import timedelta
        from django.db.migrations.executor import MigrationExecutor
        from django.utils import timezone
        before = [('pabasa_app', '0034_assessmentrequest_live_session_and_more')]
        after = [('pabasa_app', '0035_lesson29_recording_scope')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            User = old_apps.get_model('pabasa_app', 'User')
            Calendar = old_apps.get_model('pabasa_app', 'SchoolCalendar')
            Progress = old_apps.get_model('pabasa_app', 'StudentActivityProgress')
            OldRecording = old_apps.get_model('pabasa_app', 'StudentActivityRecordingSubmission')
            calendar = Calendar.objects.create(school_year='2026-2027', current_term=1)
            student = User.objects.create(custom_id='MIGRATION-LOCAL', role='student', first_name='Test',
                last_name='Migration', sex='female', birth_month=1, birth_day=1, birth_year=2018, password_hash='!')
            recording = OldRecording.objects.create(student=student, activity_key='lesson-29-gawain-3',
                item_index=0, audio_file='preserve-historical.webm', teacher_score=1, status='checked')
            old_date = timezone.now() - timedelta(days=365)
            OldRecording.objects.filter(pk=recording.pk).update(submitted_at=old_date)
            Progress.objects.create(student=student, school_calendar=calendar, term=1, activity_key='lesson-29-gawain-3')
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new_apps = executor.loader.project_state(after).apps
            migrated = new_apps.get_model('pabasa_app', 'StudentActivityRecordingSubmission').objects.get(pk=recording.pk)
            self.assertIsNone(migrated.school_calendar_id)
            self.assertIsNone(migrated.term)
            self.assertEqual(migrated.audio_file.name, 'preserve-historical.webm')
            self.assertEqual(migrated.teacher_score, 1)
            self.assertEqual(migrated.status, 'checked')
            self.assertEqual(migrated.submitted_at, old_date)
        finally:
            MigrationExecutor(connection).migrate(after)
