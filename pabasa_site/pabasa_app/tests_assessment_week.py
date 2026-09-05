import json
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AssessmentRequest, CalendarEvent, Material, School, SchoolCalendar, Section, User


class AssessmentWeekTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Assessment Week School', code='AWS')
        self.calendar = SchoolCalendar.objects.create(
            school_year='Assessment Week Test Year', current_term=1, is_active=True,
        )
        CalendarEvent.objects.create(
            school_calendar=self.calendar, scope=CalendarEvent.SCOPE_SCHOOL,
            school=self.school, term=1, title='Assessment Week',
            event_type='pre_assessment', start_date=date.today(), end_date=date.today(),
        )
        self.teacher_a = self._user('teacher-a', 'teacher')
        self.teacher_b = self._user('teacher-b', 'teacher')
        self.student_a = self._user('student-a', 'student')
        self.student_b = self._user('student-b', 'student')
        self.section_a = self._section('AWS-A', self.teacher_a)
        self.section_b = self._section('AWS-B', self.teacher_b)
        self.section_a.add_student(self.student_a)
        self.section_b.add_student(self.student_b)
        self.normal_a = self._material(self.section_a, 'Normal A', 'practice')
        self.assessment_a = self._material(self.section_a, 'Assessment A', 'assessment')
        self.normal_b = self._material(self.section_b, 'Normal B', 'practice')

    def _user(self, custom_id, role):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name=custom_id, last_name='User',
            middle_initial='', suffix='', sex='N/A', birth_month=1, birth_day=1,
            birth_year=1990, email=f'{custom_id}@example.com',
            password_hash=make_password('password'), school_record=self.school,
        )

    def _section(self, code, teacher):
        return Section.objects.create(
            school=self.school, class_code=code, class_name=code,
            subject='Reading', teacher=teacher, school_calendar=self.calendar,
        )

    def _material(self, section, title, usage_type):
        return Material.objects.create(
            section=section, teacher=section.teacher, title=title,
            item_type='word', type=usage_type, status='published',
            content_text='sample content', student_access=True,
        )

    def _login(self, user):
        session = self.client.session
        session.update({'user_id': user.id, 'user_role': user.role, 'email': user.email})
        session.save()
        if user.role == 'student':
            User.objects.filter(pk=user.pk).update(
                active_session_key=session.session_key,
                last_activity=timezone.now(),
            )

    def _toggle(self, section_id, enabled):
        return self.client.post(
            reverse('update_section_assessment_week'),
            data=json.dumps({'section_id': section_id, 'assessment_week_enabled': enabled}),
            content_type='application/json',
        )

    def test_teacher_toggles_only_assigned_section(self):
        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['assessment_week_enabled'])
        self.section_a.refresh_from_db()
        self.section_b.refresh_from_db()
        self.assertTrue(self.section_a.assessment_week_enabled)
        self.assertFalse(self.section_b.assessment_week_enabled)

    def test_teacher_cannot_toggle_another_teachers_section(self):
        self._login(self.teacher_a)
        response = self._toggle(self.section_b.id, True)
        self.assertEqual(response.status_code, 403)
        self.section_b.refresh_from_db()
        self.assertFalse(self.section_b.assessment_week_enabled)

    def test_toggle_is_hidden_and_endpoint_rejects_outside_calendar_assessment_week(self):
        CalendarEvent.objects.filter(school_calendar=self.calendar).delete()
        self._login(self.teacher_a)
        page_response = self.client.get(reverse('class_management'), {'section_id': self.section_a.id})
        self.assertNotContains(page_response, 'id="assessmentWeekToggle"')
        response = self._toggle(self.section_a.id, True)
        self.assertEqual(response.status_code, 403)
        self.section_a.refresh_from_db()
        self.assertFalse(self.section_a.assessment_week_enabled)

    def test_assessment_week_filters_normal_materials_per_section(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])

        self._login(self.student_a)
        response_a = self.client.get(reverse('get_class_materials'), {'section_id': self.section_a.id})
        self.assertEqual(response_a.status_code, 200)
        returned_ids = {item['id'] for item in response_a.json()['all_materials']}
        self.assertIn(f'material-{self.assessment_a.id}', returned_ids)
        self.assertNotIn(f'material-{self.normal_a.id}', returned_ids)

        self._login(self.student_b)
        response_b = self.client.get(reverse('get_class_materials'), {'section_id': self.section_b.id})
        self.assertEqual(response_b.status_code, 200)
        returned_ids = {item['id'] for item in response_b.json()['all_materials']}
        self.assertIn(f'material-{self.normal_b.id}', returned_ids)

    def test_direct_normal_material_request_is_denied_during_assessment_week(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        self._login(self.student_a)
        response = self.client.get(reverse('reading_word_page'), {'id': f'material-{self.normal_a.id}'})
        self.assertEqual(response.status_code, 403)

    def test_assessment_is_locked_when_assessment_week_is_off(self):
        self._login(self.student_a)
        hub_response = self.client.get(reverse('assessment'), {'section_id': self.section_a.id})
        self.assertContains(hub_response, 'Waiting for Assessment Week')
        direct_response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.assessment_a.id}'}
        )
        self.assertEqual(direct_response.status_code, 403)

    def test_assessment_is_allowed_when_assessment_week_is_on(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        self._login(self.student_a)
        response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.assessment_a.id}'}
        )
        self.assertEqual(response.status_code, 200)

    def test_official_assessment_launch_is_locked_when_assessment_week_is_off(self):
        self.assessment_a.is_official_reading = True
        self.assessment_a.assessment_kind = 'crla'
        self.assessment_a.save(update_fields=['is_official_reading', 'assessment_kind'])
        self._login(self.student_a)
        response = self.client.get(
            reverse('reading_word_page'), {'official_assessment_id': self.assessment_a.id}
        )
        self.assertEqual(response.status_code, 403)

    def test_approved_overdue_request_bypasses_stale_assessment_week_switch_for_official_crla(self):
        """Teacher approval remains usable after the calendar assessment window."""
        CalendarEvent.objects.filter(school_calendar=self.calendar).update(
            end_date=date.today() - timedelta(days=1)
        )
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        official_material = Material.objects.filter(
            is_official_reading=True,
            assessment_kind='crla',
            system_assessment_phase='pretest',
        ).first()
        self.assertIsNotNone(official_material)
        official_material.student_access = True
        official_material.is_active = True
        official_material.status = 'published'
        official_material.save(update_fields=['student_access', 'is_active', 'status'])
        assessment_request = AssessmentRequest.objects.create(
            student=self.student_a,
            section=self.section_a,
            status='approved',
            reviewed_by=self.teacher_a,
            reviewed_at=timezone.now(),
        )
        assessment_request.refresh_from_db()
        self.assertEqual(assessment_request.status, 'approved')

        self._login(self.student_a)
        hub_response = self.client.get(reverse('assessment'), {'section_id': self.section_a.id})
        self.assertEqual(hub_response.status_code, 200)
        self.assertContains(hub_response, f'official_assessment_id={official_material.id}')
        self.assertNotContains(hub_response, 'Assessment Week is enabled for this section')

        launch_response = self.client.get(
            reverse('reading_word_page'), {'official_assessment_id': official_material.id}
        )
        self.assertEqual(launch_response.status_code, 200)

    def test_completed_official_assessment_unblocks_teacher_materials_after_assessment_week(self):
        """A stale switch cannot strand a student after completing the official CRLA."""
        CalendarEvent.objects.filter(school_calendar=self.calendar).update(
            end_date=date.today() - timedelta(days=1)
        )
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        official_material = Material.objects.filter(
            is_official_reading=True,
            assessment_kind='crla',
            system_assessment_phase='pretest',
        ).first()
        self.assertIsNotNone(official_material)
        official_material.record_assessment_result(
            self.student_a,
            status='completed',
            completed_at=timezone.now(),
        )

        self._login(self.student_a)
        response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.normal_a.id}'}
        )
        self.assertEqual(response.status_code, 200)

    def test_stale_assessment_week_switch_does_not_block_teacher_materials_after_window(self):
        """An expired calendar window releases materials and turns its switch off."""
        CalendarEvent.objects.filter(school_calendar=self.calendar).update(
            end_date=date.today() - timedelta(days=1)
        )
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])

        self._login(self.student_a)
        response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.normal_a.id}'}
        )
        self.assertEqual(response.status_code, 200)
        self.section_a.refresh_from_db()
        self.assertFalse(self.section_a.assessment_week_enabled)

    def test_expired_window_allows_teacher_assessment_materials(self):
        """Teacher activities marked as assessments are not official CRLA gates."""
        CalendarEvent.objects.filter(school_calendar=self.calendar).update(
            end_date=date.today() - timedelta(days=1)
        )
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])

        self._login(self.student_a)
        response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.assessment_a.id}'}
        )
        self.assertEqual(response.status_code, 200)
        self.section_a.refresh_from_db()
        self.assertFalse(self.section_a.assessment_week_enabled)

    def test_multiple_enabled_sections_are_independently_restricted(self):
        Section.objects.filter(id__in=[self.section_a.id, self.section_b.id]).update(
            assessment_week_enabled=True
        )

        self._login(self.student_b)
        response = self.client.get(reverse('get_class_materials'), {'section_id': self.section_b.id})
        self.assertEqual(response.status_code, 200)
        returned_ids = {item['id'] for item in response.json()['all_materials']}
        self.assertNotIn(f'material-{self.normal_b.id}', returned_ids)

    def test_disabling_restores_normal_materials(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        self._login(self.teacher_a)
        self.assertEqual(self._toggle(self.section_a.id, False).status_code, 200)
        self._login(self.student_a)
        response = self.client.get(reverse('get_class_materials'), {'section_id': self.section_a.id})
        returned_ids = {item['id'] for item in response.json()['all_materials']}
        self.assertIn(f'material-{self.normal_a.id}', returned_ids)
