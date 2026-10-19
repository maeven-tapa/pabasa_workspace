"""Regression checks for overlapping saves and interrupted ARAL requests."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import School, StudentActivityProgress, User
from .prescribed_test_fixtures import prescribed_term_fixture
from .prescribed_workbook import apply_event, initial_s9_a1_state


class AralSaveRecoveryTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='ARAL recovery', code='ARAL-REC')
        self.student = User.objects.create(custom_id='ARAL-REC-S', role='student',
            first_name='Synthetic', last_name='Student', password_hash='x',
            sex='female', birth_month=1, birth_day=1, birth_year=2015, school_record=school)
        self.calendar, _, _, _ = prescribed_term_fixture(self.student)
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student'})
        session.save()
        self.key = 'aral-s9-a1-family-drawing'
        self.url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})
        gate = patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True)
        gate.start()
        self.addCleanup(gate.stop)

    def row(self, state=None):
        return StudentActivityProgress.objects.create(student=self.student,
            school_calendar=self.calendar, term=1, activity_key=self.key,
            state=state or initial_s9_a1_state())

    def save(self, revision=0):
        return self.client.post(self.url, json.dumps({'action':'draft', 'revision':revision,
            'draft':{'text':'This is my family.', 'strokes':[]}}), content_type='application/json')

    def test_save_and_reload_keep_draft_and_reject_old_revision(self):
        self.row()
        saved = self.save()
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['state']['revision'], 1)
        self.assertEqual(self.save().status_code, 409)
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual(row.state['draft']['text'], 'This is my family.')

    def test_competing_save_after_read_cannot_be_overwritten(self):
        row = self.row()
        def competing(activity, state, event, verified):
            replacement = initial_s9_a1_state()
            replacement.update(revision=1, draft={'text':'Newer tab draft', 'strokes':[]})
            StudentActivityProgress.objects.filter(pk=row.pk).update(state=replacement)
            # QuerySet.update deliberately leaves updated_at unchanged. A real
            # competing save uses Model.save and updates its database version.
            current = StudentActivityProgress.objects.get(pk=row.pk)
            current.save(update_fields=['state', 'updated_at'])
            return apply_event(activity, state, event, verified)
        with patch('pabasa_app.prescribed_workbook.apply_event', side_effect=competing):
            response = self.save()
        self.assertEqual(response.status_code, 409)
        row.refresh_from_db()
        self.assertEqual(row.state['draft']['text'], 'Newer tab draft')

    def test_competing_first_save_cannot_be_overwritten(self):
        def competing(activity, state, event, verified):
            replacement = initial_s9_a1_state()
            replacement.update(revision=1, draft={'text':'Other first save', 'strokes':[]})
            self.row(replacement)
            return apply_event(activity, state, event, verified)
        with patch('pabasa_app.prescribed_workbook.apply_event', side_effect=competing):
            response = self.save()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(StudentActivityProgress.objects.filter(student=self.student,activity_key=self.key).count(),1)

    def test_teacher_verdict_during_save_is_preserved(self):
        row = self.row()
        def review(activity, state, event, verified):
            reviewed = initial_s9_a1_state()
            reviewed.update(completed=True, teacher_verdict='correct')
            current = StudentActivityProgress.objects.get(pk=row.pk)
            current.state = reviewed
            current.activity_completed = True
            current.save()
            return apply_event(activity, state, event, verified)
        with patch('pabasa_app.prescribed_workbook.apply_event', side_effect=review):
            self.assertEqual(self.save().status_code,409)
        row.refresh_from_db()
        self.assertTrue(row.activity_completed)
        self.assertEqual(row.state['teacher_verdict'],'correct')

    def test_legacy_non_object_payloads_return_400(self):
        for body in ('[]','null','1','"invalid"'):
            with self.subTest(body=body):
                response = self.client.post(reverse('lesson_3_activity_progress'),body,content_type='application/json')
                self.assertEqual(response.status_code,400)

    def test_draft_backup_uses_resolved_calendar_for_an_unassigned_student(self):
        # Old accounts may resolve their calendar through the active calendar
        # rather than through the nullable student.school_calendar field.
        self.student.school_calendar = None
        self.student.save(update_fields=['school_calendar', 'updated_at'])
        response = self.client.get(reverse('prescribed_activity_page',kwargs={'activity_key':self.key}))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,f'data-scope="{self.student.pk}:{self.calendar.pk}:1"')

    def test_legacy_older_checkpoint_cannot_undo_completion(self):
        url = reverse('lesson_3_activity_progress')
        data = {'activity_key':'lesson-2-gawain-1','total_items':3,'current_index':3,
                'completed_items':3,'correct_items':3,'activity_completed':True}
        self.assertEqual(self.client.post(url,json.dumps(data),content_type='application/json').status_code,200)
        data.update(current_index=1,completed_items=1,correct_items=1,activity_completed=False)
        response = self.client.post(url,json.dumps(data),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['progress']['activity_completed'])
