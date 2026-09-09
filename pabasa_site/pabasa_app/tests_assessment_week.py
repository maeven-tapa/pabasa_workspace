import json
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, AssessmentRequest, CalendarEvent, LiveAssessmentSession, Material, School, SchoolCalendar, Section, User


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

    def _make_completed_aral_student(self):
        official_root = Assessment.objects.create(
            teacher=self.teacher_a, title='Official CRLA', code='AWS-CRLA-ARAL',
            assessment_type='paragraph', system_assessment_key='bosy_crla_pretest',
        )
        official_material = Material.objects.create(
            teacher=self.teacher_a, section=self.section_a, assessment=official_root,
            title='Official CRLA', code='AWS-CRLA-ARAL-MATERIAL', item_type='paragraph',
            type='assessment', status='published', assessment_kind='crla',
            is_official_reading=True, is_system_owned=True,
        )
        Assessment.objects.create(
            teacher=self.teacher_a, student=self.student_a, material=official_material,
            source_assessment=official_root, title='Completed CRLA', code='AWS-CRLA-ARAL-RESULT',
            assessment_type='paragraph', attempt_status='completed',
            completed_at=timezone.now(), crla_classification='Transitioning Reader',
        )
        self.student_a.preference = {
            'reading_assessment_state': {
                'reader_classification': 'Transitioning Reader',
                'aral_eligible': True,
                'aral_status': 'active',
                'current_phase': 'materials',
            },
        }
        self.student_a.save(update_fields=['preference', 'updated_at'])

    def _aral_materials(self, week, count):
        materials = []
        for index in range(count):
            materials.append(self._material(self.section_a, f'Week {week} Activity {index + 1}', 'assessment'))
            materials[-1].assigned_week = week
            materials[-1].save(update_fields=['assigned_week', 'updated_at'])
        return materials

    def _class_payload(self):
        self._login(self.student_a)
        response = self.client.get(reverse('get_student_joined_classes'))
        self.assertEqual(response.status_code, 200)
        return next(item for item in response.json()['classes'] if item['section_id'] == self.section_a.id)

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

    def test_completed_official_crla_prioritizes_teacher_materials_during_assessment_week(self):
        """The class-card API must use a persisted official result, not reading level."""
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        official_root = Assessment.objects.create(
            teacher=self.teacher_a, title='Official CRLA', code='AWS-CRLA-ROOT',
            assessment_type='paragraph', system_assessment_key='bosy_crla_pretest',
        )
        official_material = Material.objects.create(
            teacher=self.teacher_a, section=self.section_a, assessment=official_root,
            title='Official CRLA', code='AWS-CRLA-MATERIAL', item_type='paragraph',
            type='assessment', status='published', assessment_kind='crla',
            is_official_reading=True, is_system_owned=True,
        )
        Assessment.objects.create(
            teacher=self.teacher_a, student=self.student_a, material=official_material,
            source_assessment=official_root, title='Completed CRLA', code='AWS-CRLA-RESULT',
            assessment_type='paragraph', attempt_status='completed',
            completed_at=timezone.now(), crla_classification='Transitioning Reader',
        )
        self.student_a.preference = {
            'reading_assessment_state': {
                'reader_classification': 'Transitioning Reader',
                'aral_eligible': True,
                'current_week': 1,
            },
        }
        self.student_a.save(update_fields=['preference', 'updated_at'])
        self.normal_a.assigned_week = 1
        self.normal_a.save(update_fields=['assigned_week'])
        self.assessment_a.assigned_week = 1
        self.assessment_a.save(update_fields=['assigned_week'])

        self._login(self.student_a)
        classes_response = self.client.get(reverse('get_student_joined_classes'))
        self.assertEqual(classes_response.status_code, 200)
        class_payload = next(item for item in classes_response.json()['classes'] if item['section_id'] == self.section_a.id)
        self.assertTrue(class_payload['official_crla_completed'])
        self.assertTrue(class_payload['aral_eligible'])
        self.assertEqual(class_payload['current_aral_week'], 1)

        materials_response = self.client.get(reverse('get_class_materials'), {'section_id': self.section_a.id})
        self.assertEqual(materials_response.status_code, 200)
        materials_payload = materials_response.json()
        self.assertTrue(materials_payload['official_crla_completed'])
        returned_ids = {item['id'] for item in materials_payload['all_materials']}
        self.assertIn(f'material-{self.normal_a.id}', returned_ids)
        self.assertNotIn(f'material-{official_material.id}', returned_ids)
        material_payload = next(item for item in materials_payload['all_materials'] if item['id'] == f'material-{self.normal_a.id}')
        self.assertEqual(material_payload['assigned_weeks'], [1])

        launch_response = self.client.get(
            reverse('reading_word_page'), {'id': f'material-{self.normal_a.id}'}
        )
        self.assertEqual(launch_response.status_code, 200)

    def test_student_class_payload_reports_live_weekly_aral_progress(self):
        official_root = Assessment.objects.create(
            teacher=self.teacher_a, title='Official CRLA', code='AWS-CRLA-PROGRESS',
            assessment_type='paragraph', system_assessment_key='bosy_crla_pretest',
        )
        official_material = Material.objects.create(
            teacher=self.teacher_a, section=self.section_a, assessment=official_root,
            title='Official CRLA', code='AWS-CRLA-PROGRESS-MATERIAL', item_type='paragraph',
            type='assessment', status='published', assessment_kind='crla',
            is_official_reading=True, is_system_owned=True,
        )
        Assessment.objects.create(
            teacher=self.teacher_a, student=self.student_a, material=official_material,
            source_assessment=official_root, title='Completed CRLA', code='AWS-CRLA-PROGRESS-RESULT',
            assessment_type='paragraph', attempt_status='completed',
            completed_at=timezone.now(), crla_classification='Transitioning Reader',
        )
        self.student_a.preference = {
            'reading_assessment_state': {
                'reader_classification': 'Transitioning Reader',
                'aral_eligible': True,
                'current_week': 1,
            },
        }
        self.student_a.save(update_fields=['preference', 'updated_at'])
        aral_materials = [self.assessment_a]
        for index in range(2):
            aral_materials.append(self._material(self.section_a, f'ARAL {index + 2}', 'assessment'))
        for material in aral_materials:
            material.assigned_week = 1
            material.student_access = True
            material.save(update_fields=['assigned_week', 'student_access', 'updated_at'])

        aral_materials[0].record_assessment_result(self.student_a, status='completed')
        self._login(self.student_a)

        response = self.client.get(reverse('get_student_joined_classes'))
        self.assertEqual(response.status_code, 200)
        payload = next(item for item in response.json()['classes'] if item['section_id'] == self.section_a.id)
        self.assertEqual(payload['aral_week_total'], 3)
        self.assertEqual(payload['aral_week_completed'], 1)

        added_material = self._material(self.section_a, 'ARAL 4', 'assessment')
        added_material.assigned_week = 1
        added_material.student_access = True
        added_material.save(update_fields=['assigned_week', 'student_access', 'updated_at'])

        response = self.client.get(reverse('get_student_joined_classes'))
        payload = next(item for item in response.json()['classes'] if item['section_id'] == self.section_a.id)
        self.assertEqual(payload['aral_week_total'], 4)
        self.assertEqual(payload['aral_week_completed'], 1)

    def test_current_week_is_earliest_assigned_week_not_fully_completed(self):
        self._make_completed_aral_student()
        week_one = self._aral_materials(1, 3)
        self._aral_materials(2, 4)
        for material in week_one:
            material.record_assessment_result(self.student_a, status='completed')

        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 2)
        self.assertEqual(payload['aral_week_completed'], 0)
        self.assertEqual(payload['aral_week_total'], 4)

    def test_current_week_moves_to_week_three_after_weeks_one_and_two_complete(self):
        self._make_completed_aral_student()
        week_one = self._aral_materials(1, 3)
        week_two = self._aral_materials(2, 4)
        self._aral_materials(3, 2)
        for material in week_one + week_two:
            material.record_assessment_result(self.student_a, status='completed')

        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 3)
        self.assertEqual(payload['aral_week_completed'], 0)
        self.assertEqual(payload['aral_week_total'], 2)

    def test_completing_week_one_automatically_moves_to_week_two(self):
        self._make_completed_aral_student()
        week_one = self._aral_materials(1, 2)
        self._aral_materials(2, 4)
        week_one[0].record_assessment_result(self.student_a, status='completed')

        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 1)
        self.assertEqual(payload['aral_week_completed'], 1)

        week_one[1].record_assessment_result(self.student_a, status='completed')
        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 2)
        self.assertEqual(payload['aral_week_completed'], 0)
        self.assertEqual(payload['aral_week_total'], 4)

    def test_new_activity_in_completed_week_resurfaces_that_earlier_week(self):
        self._make_completed_aral_student()
        week_one = self._aral_materials(1, 2)
        week_two = self._aral_materials(2, 2)
        for material in week_one + week_two:
            material.record_assessment_result(self.student_a, status='completed')

        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 2)
        self.assertEqual(payload['aral_week_completed'], 2)

        new_activity = self._aral_materials(1, 1)[0]
        payload = self._class_payload()
        self.assertEqual(payload['current_aral_week'], 1)
        self.assertEqual(payload['aral_week_completed'], 2)
        self.assertEqual(payload['aral_week_total'], 3)
        self.assertFalse(new_activity.has_student_completed(self.student_a))

    def test_aral_week_route_selects_week_folder_without_official_crla(self):
        self._make_completed_aral_student()
        week_one = self._aral_materials(1, 2)
        self._aral_materials(2, 1)
        response = self.client.get(
            reverse('assessment'),
            {'section_id': self.section_a.id, 'week': 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/assessment.html')
        self.assertTrue(response.context['aral_week_mode'])
        self.assertTrue(response.context['aral_week_launch'])
        self.assertEqual(response.context['requested_aral_week'], 1)
        self.assertEqual(
            {item['id'] for item in response.context['student_assessment_materials']},
            {material.id for material in week_one},
        )
        self.assertNotContains(response, 'Official CRLA')
        self.assertContains(response, 'aralWeekMode')

    def test_aral_week_route_does_not_expose_unassigned_week_materials(self):
        self._make_completed_aral_student()
        self._aral_materials(1, 2)
        response = self.client.get(
            reverse('assessment'),
            {'section_id': self.section_a.id, 'week': 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['aral_week_mode'])
        self.assertTrue(response.context['aral_week_launch'])
        self.assertEqual(response.context['student_assessment_materials'], [])

    def test_invalid_aral_week_does_not_expose_activities(self):
        self._make_completed_aral_student()
        self._aral_materials(1, 2)
        response = self.client.get(
            reverse('assessment'),
            {'section_id': self.section_a.id, 'week': 'not-a-week'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['aral_week_mode'])
        self.assertFalse(response.context['aral_week_launch'])
        self.assertEqual(response.context['student_assessment_materials'], [])

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

    def _current_week_crla_material(self, suffix):
        root = Assessment.objects.create(
            teacher=self.teacher_a, section=self.section_a, title='Current CRLA',
            code=f'AWS-CRLA-ROOT-{suffix}', assessment_type='paragraph',
            system_assessment_key='bosy_crla_pretest', system_assessment_phase='pretest',
            official_term=1,
        )
        material = Material.objects.create(
            teacher=self.teacher_a, section=self.section_a, assessment=root,
            title='Current CRLA', code=f'AWS-CRLA-MATERIAL-{suffix}', item_type='paragraph',
            type='assessment', status='published', assessment_kind='crla',
            is_official_reading=True, is_system_owned=True,
            system_assessment_phase='pretest',
        )
        return root, material

    def _record_current_week_crla_result(self, student, suffix):
        root, material = self._current_week_crla_material(suffix)
        return Assessment.objects.create(
            teacher=self.teacher_a, student=student, enrollment=student.enrollments.get(section=self.section_a),
            section=self.section_a, material=material, source_assessment=root,
            title='Completed CRLA', code=f'AWS-CRLA-RESULT-{suffix}', assessment_type='paragraph',
            system_assessment_key='bosy_crla_pretest', system_assessment_phase='pretest', official_term=1,
            attempt_status='completed', completed_at=timezone.now(),
            crla_classification='Transitioning Readers',
        )

    def test_direct_off_request_is_rejected_after_one_current_week_crla_result(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        self._record_current_week_crla_result(self.student_a, 'ONE')

        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, False)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'assessment_week_results_recorded')
        self.assertTrue(response.json()['assessment_week_enabled'])
        self.section_a.refresh_from_db()
        self.assertTrue(self.section_a.assessment_week_enabled)

    def test_direct_off_request_is_rejected_after_multiple_current_week_crla_results(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        self._record_current_week_crla_result(self.student_a, 'FIRST')
        self._record_current_week_crla_result(self.student_b, 'SECOND')

        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, False)

        self.assertEqual(response.status_code, 409)
        self.section_a.refresh_from_db()
        self.assertTrue(self.section_a.assessment_week_enabled)

    def test_recorded_unfinalized_crla_score_blocks_turning_off(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        root, material = self._current_week_crla_material('UNFINALIZED')
        Assessment.objects.create(
            teacher=self.teacher_a, student=self.student_a, section=self.section_a,
            enrollment=self.student_a.enrollments.get(section=self.section_a), material=material,
            source_assessment=root, title='Saved CRLA score', code='AWS-CRLA-UNFINALIZED-RESULT',
            assessment_type='paragraph', system_assessment_key='bosy_crla_pretest',
            system_assessment_phase='pretest', official_term=1, attempt_status='started',
            total_score=0, crla_score_data={'task1_score': 0},
        )

        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, False)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'assessment_week_results_recorded')
        self.section_a.refresh_from_db()
        self.assertTrue(self.section_a.assessment_week_enabled)

    def test_selected_or_batched_student_without_crla_result_can_turn_off(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        _root, material = self._current_week_crla_material('BATCH-ONLY')
        LiveAssessmentSession.objects.create(
            id='assessment-week-batch-only', teacher=self.teacher_a, section=self.section_a,
            material=material, student_ids=[self.student_a.id], student_count=1,
            batch_assignments={'1': [self.student_a.id]}, status='batch_loaded',
        )

        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, False)

        self.assertEqual(response.status_code, 200)
        self.section_a.refresh_from_db()
        self.assertFalse(self.section_a.assessment_week_enabled)

    def test_result_from_another_assessment_week_does_not_block_turning_off(self):
        self.section_a.assessment_week_enabled = True
        self.section_a.save(update_fields=['assessment_week_enabled'])
        root = Assessment.objects.create(
            teacher=self.teacher_a, section=self.section_a, title='Post CRLA',
            code='AWS-POST-ROOT', assessment_type='paragraph',
            system_assessment_key='eosy_crla_posttest', system_assessment_phase='posttest', official_term=3,
        )
        material = Material.objects.create(
            teacher=self.teacher_a, section=self.section_a, assessment=root,
            title='Post CRLA', code='AWS-POST-MATERIAL', item_type='paragraph', type='assessment',
            status='published', assessment_kind='crla', is_official_reading=True,
            is_system_owned=True, system_assessment_phase='posttest',
        )
        Assessment.objects.create(
            teacher=self.teacher_a, student=self.student_a, section=self.section_a,
            enrollment=self.student_a.enrollments.get(section=self.section_a), material=material,
            source_assessment=root, title='Completed Post CRLA', code='AWS-POST-RESULT',
            assessment_type='paragraph', system_assessment_key='eosy_crla_posttest',
            system_assessment_phase='posttest', official_term=3, attempt_status='completed',
            completed_at=timezone.now(), crla_classification='Transitioning Readers',
        )

        self._login(self.teacher_a)
        response = self._toggle(self.section_a.id, False)

        self.assertEqual(response.status_code, 200)
        self.section_a.refresh_from_db()
        self.assertFalse(self.section_a.assessment_week_enabled)
