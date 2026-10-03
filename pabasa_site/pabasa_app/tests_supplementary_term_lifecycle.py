"""Focused Phase 2.5 validation for current-term Supplementary ownership."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Assessment, CalendarEvent, Material, SchoolCalendar, Section, StoryReadingProgress, StoryResponseSubmission, SupplementaryMaterialPublication, SystemTimeOverride, User
from .prescribed_test_fixtures import prescribed_term_fixture
from .system_clock import invalidate_override_cache, now as system_now
from .views import _current_learning_context, _current_supplementary_scope, _supplementary_material_currently_published


class SupplementaryTermLifecycleTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        from .models import School
        self.school = School.objects.create(name='Supplementary Lifecycle School', code='SUP-LIFE')
        self.student = User.objects.create(
            custom_id='SUP-STUDENT', role='student', first_name='Sup', last_name='Student',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email='supplementary@example.test', password_hash='x', school_record=self.school,
        )
        self.calendar, self.section, self.enrollment, self.crla = prescribed_term_fixture(
            self.student, today=self.today, classification='Developing Reader',
        )
        self.story = Material.objects.create(
            teacher=self.section.teacher, section=self.section, title='Story A',
            code='SUP-STORY', item_type='paragraph', type='material', status='published',
            student_access=True, content_json={
                'template_title': 'Story Reading', 'activity_type': 'story_reading',
                'storyTitle': 'Story A', 'storyText': 'A story.',
            },
        )
        self.response = Material.objects.create(
            teacher=self.section.teacher, section=self.section, title='Tell the story',
            code='SUP-RESPONSE', item_type='paragraph', type='material', status='published',
            student_access=True, content_json={
                'activity_type': 'story_response',
                'source_story_reading_material_id': self.story.id,
                'response_prompt': 'What happened?',
            },
        )
        self.retell = Material.objects.create(
            teacher=self.section.teacher, section=self.section, title='Retell Story A',
            code='SUP-RETELL', item_type='paragraph', type='material', status='published',
            student_access=True, content_json={
                'activity_type': 'retell_story',
                'source_story_reading_material_id': self.story.id,
                'response_prompt': 'Retell the story.',
            },
        )
        self.story_questions = Material.objects.create(
            teacher=self.section.teacher, section=self.section, title='Story Questions A',
            code='SUP-QUESTIONS', item_type='paragraph', type='assessment', status='published',
            student_access=True, content_json={
                'template_title': "5W's Story Questions",
                'activity_type': 'five_w_story_questions',
                'source_story_reading_material_id': self.story.id,
                'questions': [{'question': 'Who?', 'answer': 'Ana'}],
            },
        )
        for material in (self.story, self.response, self.retell, self.story_questions):
            SupplementaryMaterialPublication.objects.create(
                material=material, school_calendar=self.calendar, term=1, section=self.section,
            )
        self.student.set_password('test-password')
        self.student.save(update_fields=['password_hash', 'updated_at'])
        login_response = self.client.post(reverse('login_user'), {
            'custom_id': self.student.custom_id,
            'password': 'test-password',
        })
        self.assertEqual(login_response.status_code, 200)

    def activate_term(self, term, school_year=None, completed=True, classification='Developing Reader'):
        self.enrollment.status = 'active'
        self.enrollment.is_active = True
        self.enrollment.save(update_fields=['status', 'is_active', 'updated_at'])
        self.calendar.current_term = term
        if school_year:
            self.calendar.is_active = False
            self.calendar.save(update_fields=['is_active', 'current_term', 'updated_at'])
            self.calendar = SchoolCalendar.objects.create(
                school_year=school_year, current_term=term, is_active=True,
            )
            self.section.school_calendar = self.calendar
            self.section.save(update_fields=['school_calendar'])
            self.enrollment.school_calendar = self.calendar
            self.enrollment.save(update_fields=['school_calendar', 'updated_at'])
            self.student.school_calendar = self.calendar
            self.student.save(update_fields=['school_calendar', 'updated_at'])
        else:
            if term != 1:
                self.calendar.events.filter(term__lt=term, event_type='school_closing').update(
                    start_date=self.today - timedelta(days=1),
                    end_date=self.today - timedelta(days=1),
                )
            self.calendar.events.filter(term=term, event_type='school_opening').update(
                start_date=self.today - timedelta(days=2), end_date=self.today - timedelta(days=2),
            )
            self.calendar.events.filter(term=term, event_type='school_closing').update(
                start_date=self.today + timedelta(days=20), end_date=self.today + timedelta(days=20),
            )
            self.calendar.save(update_fields=['current_term', 'is_active', 'updated_at'])
        Assessment.objects.filter(
            student=self.student, enrollment=self.enrollment, official_term=term,
            system_assessment_key={1: 'bosy_crla_pretest', 2: 'midline_crla_midtest', 3: 'eosy_crla_posttest'}[term],
        ).delete()
        return prescribed_term_fixture(
            self.student, teacher=self.section.teacher, section=self.section,
            calendar=self.calendar, term=term, today=self.today,
            completed=completed, classification=classification,
        )

    def test_aral_active_story_page_and_scoped_rows(self):
        self.assertEqual(_current_learning_context(self.student)['state'], 'ARAL_ACTIVE')
        response = self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}, follow=True)
        self.assertEqual(response.status_code, 200)
        scope = _current_supplementary_scope(self.student, self.story)
        first = StoryReadingProgress.objects.create(**scope, completed=True, current_scene=6)
        self.assertTrue(StoryReadingProgress.objects.filter(pk=first.pk, school_calendar=self.calendar, term=1).exists())

    def test_pending_and_grade_level_are_denied(self):
        self.activate_term(1, completed=False)
        self.assertNotEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        self.activate_term(1, completed=True, classification='Reading At Grade Level')
        self.assertNotEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)

    def test_term_and_school_year_story_rows_are_isolated(self):
        scope_one = _current_supplementary_scope(self.student, self.story)
        old = StoryReadingProgress.objects.create(**scope_one, completed=True, current_scene=6)
        self.activate_term(2)
        scope_two = _current_supplementary_scope(self.student, self.story)
        fresh = StoryReadingProgress.objects.create(**scope_two, completed=False, current_scene=1)
        self.assertEqual(old.school_calendar_id, fresh.school_calendar_id)
        self.assertNotEqual(old.term, fresh.term)
        self.assertEqual(StoryReadingProgress.objects.filter(student=self.student, material=self.story).count(), 2)
        self.assertTrue(StoryReadingProgress.objects.get(pk=old.pk).completed)

    def test_publication_visibility_is_term_and_school_year_scoped(self):
        old_publication = SupplementaryMaterialPublication.objects.get(
            material=self.story, school_calendar=self.calendar, term=1, section=self.section,
        )
        self.assertEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        self.activate_term(2)
        self.assertTrue(SupplementaryMaterialPublication.objects.filter(pk=old_publication.pk).exists())
        self.assertNotEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        SupplementaryMaterialPublication.objects.create(material=self.story, school_calendar=self.calendar, term=2, section=self.section)
        self.assertEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        self.activate_term(3)
        self.assertFalse(_supplementary_material_currently_published(self.student, self.story))
        self.assertNotEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        new_calendar, _, _, _ = self.activate_term(1, school_year='2027-2028')
        self.assertIsNotNone(new_calendar)
        self.assertNotEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)
        SupplementaryMaterialPublication.objects.create(material=self.story, school_calendar=self.calendar, term=1, section=self.section)
        self.assertEqual(self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200)

    def test_publication_is_section_scoped_for_listing_and_direct_access(self):
        other = User.objects.create(
            custom_id='SUP-OTHER', role='student', first_name='Other', last_name='Student',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email='other@example.test', password_hash='x', school_record=self.school,
        )
        other.set_password('test-password')
        other.save(update_fields=['password_hash', 'updated_at'])
        section_b = Section.objects.create(
            school=self.school, class_code='SUP-B', class_name='SUP-B', subject='Reading',
            teacher=self.section.teacher, school_calendar=self.calendar,
        )
        section_b.add_student(other)
        prescribed_term_fixture(
            other, teacher=self.section.teacher, section=section_b, calendar=self.calendar,
            term=1, today=self.today, classification='Developing Reader',
        )
        self.client.post(reverse('login_user'), {'custom_id': other.custom_id, 'password': 'test-password'})
        self.assertNotEqual(
            self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200,
        )
        self.story.assigned_sections.add(section_b)
        SupplementaryMaterialPublication.objects.create(
            material=self.story, school_calendar=self.calendar, term=1, section=section_b,
        )
        self.assertEqual(
            self.client.get(reverse('story_reading_page'), {'id': f'material-{self.story.id}'}).status_code, 200,
        )

    def test_story_response_rows_are_term_scoped_and_legacy_is_preserved(self):
        legacy = StoryResponseSubmission.objects.create(student=self.student, material=self.response)
        scope_one = _current_supplementary_scope(self.student, self.response)
        first = StoryResponseSubmission.objects.create(**scope_one, story_material=self.story)
        self.activate_term(2)
        scope_two = _current_supplementary_scope(self.student, self.response)
        second = StoryResponseSubmission.objects.create(**scope_two, story_material=self.story)
        self.assertEqual(StoryResponseSubmission.objects.filter(student=self.student, material=self.response).count(), 3)
        self.assertIsNone(legacy.school_calendar)
        self.assertNotEqual(first.term, second.term)

    def test_assessment_supplementary_scope_does_not_overlap_crla(self):
        supplementary = Assessment.objects.create(
            student=self.student, enrollment=self.enrollment, material=self.story,
            teacher=self.section.teacher, title='Supplementary result', code='SUP-ASSESS',
            assessment_type='paragraph', attempt_status='completed',
            completed_at=timezone.now(), supplementary_school_calendar=self.calendar,
            supplementary_term=1,
        )
        self.assertIsNone(supplementary.official_term)
        self.assertFalse(Assessment.objects.filter(
            student=self.student, material=self.story,
            supplementary_school_calendar=self.calendar, supplementary_term=2,
        ).exists())
        self.assertTrue(Assessment.objects.filter(pk=supplementary.pk).exists())

    def test_end_date_is_inclusive_and_next_day_is_closed(self):
        closing = self.calendar.events.filter(term=1, event_type='school_closing').first()
        closing.start_date = self.today
        closing.end_date = self.today
        closing.save(update_fields=['start_date', 'end_date', 'updated_at'])
        with patch('pabasa_app.views.system_today', return_value=self.today):
            self.assertEqual(_current_learning_context(self.student)['state'], 'ARAL_ACTIVE')
        with patch('pabasa_app.views.system_today', return_value=self.today + timedelta(days=1)):
            self.assertIn(_current_learning_context(self.student)['state'], {'TERM_CLOSED', 'BETWEEN_TERMS'})

    def test_retell_submission_is_allowed_and_term_scoped(self):
        response = self.client.post(
            reverse('story_response_submit'),
            {
                'material_id': f'material-{self.retell.id}',
                'audio': SimpleUploadedFile('term-one.webm', b'audio'),
                'duration_seconds': '3',
            },
        )
        self.assertEqual(response.status_code, 200)
        first = StoryResponseSubmission.objects.get(student=self.student, material=self.retell)
        self.assertEqual(first.school_calendar_id, self.calendar.id)
        self.assertEqual(first.term, 1)
        self.assertTrue(first.audio_file)

    def test_retell_routes_are_denied_before_completion_and_after_close(self):
        self.activate_term(1, completed=False)
        page = self.client.get(reverse('story_response_page'), {'id': f'material-{self.retell.id}'})
        self.assertEqual(page.status_code, 403)
        submit = self.client.post(
            reverse('story_response_submit'),
            {'material_id': f'material-{self.retell.id}', 'audio': SimpleUploadedFile('blocked.webm', b'audio')},
        )
        self.assertEqual(submit.status_code, 403)
        self.activate_term(1, completed=True)
        closing = self.calendar.events.filter(term=1, event_type='school_closing').first()
        closing.start_date = self.today - timedelta(days=1)
        closing.end_date = self.today - timedelta(days=1)
        closing.save(update_fields=['start_date', 'end_date', 'updated_at'])
        self.assertEqual(
            self.client.get(reverse('story_response_page'), {'id': f'material-{self.retell.id}'}).status_code,
            403,
        )

    def test_retell_term_two_submission_does_not_reuse_term_one(self):
        first_response = self.client.post(
            reverse('story_response_submit'),
            {'material_id': f'material-{self.retell.id}', 'audio': SimpleUploadedFile('term-one.webm', b'audio')},
        )
        self.assertEqual(first_response.status_code, 200)
        self.activate_term(2)
        second_response = self.client.post(
            reverse('story_response_submit'),
            {'material_id': f'material-{self.retell.id}', 'audio': SimpleUploadedFile('term-two.webm', b'audio')},
        )
        self.assertEqual(second_response.status_code, 200)
        rows = StoryResponseSubmission.objects.filter(student=self.student, material=self.retell).order_by('term')
        self.assertEqual(rows.count(), 2)
        self.assertEqual([row.term for row in rows], [1, 2])
        self.assertTrue(all(row.audio_file for row in rows))

    def test_generic_completion_endpoint_requires_aral_for_supplementary(self):
        payload = {
            'material_id': f'material-{self.story.id}',
            'activity_type': 'story_reading',
            'status': 'completed',
            'items_completed': 1,
        }
        pending = self.activate_term(1, completed=False)
        response = self.client.post(
            reverse('record_assessment_completion'), data=payload, content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.activate_term(1, completed=True)
        response = self.client.post(
            reverse('record_assessment_completion'), data=payload, content_type='application/json',
        )
        self.assertLess(response.status_code, 400)
        # This generic endpoint authorizes the activity completion request;
        # Story Reading state itself is persisted by story_reading_complete.
        self.assertTrue(response.json().get('success'))

    def test_assessment_backed_supplementary_endpoint_is_scoped_and_isolated(self):
        endpoint = reverse('record_assessment_completion')
        payload = {
            'material_id': f'material-{self.story_questions.id}',
            'activity_type': 'five_w_story_questions',
            'status': 'completed',
            'items_completed': 1,
            'correct_items': 1,
            'total_items': 1,
            'scores': {'correct_items': 1, 'total_items': 1},
        }

        first = self.client.post(endpoint, data=payload, content_type='application/json')
        self.assertEqual(first.status_code, 200)
        first_row = Assessment.objects.get(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
            attempt_status='completed',
        )
        self.assertEqual(first_row.enrollment_id, self.enrollment.id)

        self.activate_term(2)
        self.assertFalse(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=2,
        ).exists())
        second = self.client.post(endpoint, data=payload, content_type='application/json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            attempt_status='completed',
        ).count(), 2)
        self.assertTrue(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
        ).exists())
        self.assertTrue(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=2,
        ).exists())

    def test_assessment_backed_supplementary_endpoint_denies_pending_grade_level_and_closed(self):
        endpoint = reverse('record_assessment_completion')
        payload = {
            'material_id': f'material-{self.story_questions.id}',
            'activity_type': 'five_w_story_questions',
            'status': 'completed',
            'items_completed': 1,
        }
        self.activate_term(1, completed=False)
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 403)
        self.activate_term(1, completed=True, classification='Reading At Grade Level')
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 403)
        self.activate_term(1, completed=True)
        closing = self.calendar.events.filter(term=1, event_type='school_closing').first()
        closing.start_date = self.today - timedelta(days=1)
        closing.end_date = self.today - timedelta(days=1)
        closing.save(update_fields=['start_date', 'end_date', 'updated_at'])
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 403)

    def test_assessment_backed_supplementary_legacy_row_is_ignored_and_crla_is_separate(self):
        legacy = Assessment.objects.create(
            student=self.student, enrollment=self.enrollment, material=self.story_questions,
            teacher=self.section.teacher, title='Legacy Supplementary', code='SUP-LEGACY',
            assessment_type='paragraph', attempt_status='completed', completed_at=timezone.now(),
        )
        self.assertIsNone(legacy.supplementary_school_calendar)
        self.assertIsNone(legacy.supplementary_term)
        self.assertFalse(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
        ).exists())
        response = self.client.post(
            reverse('record_assessment_completion'),
            data={
                'material_id': f'material-{self.story_questions.id}',
                'activity_type': 'five_w_story_questions',
                'status': 'completed', 'items_completed': 1,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
        ).exists())
        self.assertTrue(Assessment.objects.filter(
            student=self.student, system_assessment_key='bosy_crla_pretest',
            official_term=1, supplementary_school_calendar__isnull=True,
        ).exists())

    def test_assessment_backed_supplementary_isolated_across_school_years_and_between_terms(self):
        endpoint = reverse('record_assessment_completion')
        payload = {
            'material_id': f'material-{self.story_questions.id}',
            'activity_type': 'five_w_story_questions',
            'status': 'completed', 'items_completed': 1,
        }
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 200)
        old_calendar = self.calendar

        # Close the current term and leave the student between configured blocks.
        closing = old_calendar.events.filter(term=1, event_type='school_closing').first()
        closing.start_date = self.today - timedelta(days=1)
        closing.end_date = self.today - timedelta(days=1)
        closing.save(update_fields=['start_date', 'end_date', 'updated_at'])
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 403)

        self.activate_term(1, school_year='2027-2028')
        self.assertFalse(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
        ).exists())
        self.assertEqual(self.client.post(endpoint, data=payload, content_type='application/json').status_code, 200)
        self.assertTrue(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=old_calendar, supplementary_term=1,
        ).exists())
        self.assertTrue(Assessment.objects.filter(
            student=self.student, material=self.story_questions,
            supplementary_school_calendar=self.calendar, supplementary_term=1,
        ).exists())

    def test_dashboard_and_assessment_hide_intervention_during_crla_pending(self):
        self.student.reading_level = 'Low Emerging Reader'
        self.student.save(update_fields=['reading_level', 'updated_at'])
        self.activate_term(1, completed=False)
        dashboard = self.client.get(reverse('dashboard'))
        assessment = self.client.get(reverse('assessment'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(assessment.status_code, 200)
        self.assertEqual(dashboard.context['student_learning_state'], 'CRLA_PENDING')
        self.assertEqual(dashboard.context['student_reading_level'], 'Pending')
        self.assertFalse(dashboard.context['student_prescribed_visible'])
        self.assertFalse(dashboard.context['student_supplementary_visible'])
        self.assertEqual(dashboard.context['student_session_progress'], [])
        self.assertNotEqual(assessment.context.get('stage'), 'original')
        self.assertNotContains(assessment, 'Dagdag Pagsasanay')

    def test_dashboard_and_assessment_show_intervention_after_current_crla(self):
        self.activate_term(1, completed=True, classification='Developing Reader')
        dashboard = self.client.get(reverse('dashboard'))
        assessment = self.client.get(reverse('assessment'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(assessment.status_code, 200)
        self.assertEqual(dashboard.context['student_learning_state'], 'ARAL_ACTIVE')
        self.assertTrue(dashboard.context['student_prescribed_visible'])
        self.assertTrue(dashboard.context['student_supplementary_visible'])
        self.assertEqual(assessment.context.get('stage'), 'original')
        self.assertContains(assessment, 'Dagdag Pagsasanay')

    def test_dashboard_and_assessment_show_grade_level_state_only(self):
        self.activate_term(1, completed=True, classification='Reading At Grade Level')
        dashboard = self.client.get(reverse('dashboard'))
        assessment = self.client.get(reverse('assessment'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(assessment.status_code, 200)
        self.assertEqual(dashboard.context['student_learning_state'], 'GRADE_LEVEL')
        self.assertFalse(dashboard.context['student_prescribed_visible'])
        self.assertFalse(dashboard.context['student_supplementary_visible'])
        self.assertEqual(assessment.context.get('stage'), 'grade_level_complete')
        self.assertNotContains(assessment, 'Dagdag Pagsasanay')

    def test_missed_current_term_crla_uses_existing_request_flow(self):
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=1, title='Pre-Assessment Week',
            event_type='pre_assessment', start_date=self.today - timedelta(days=7),
            end_date=self.today - timedelta(days=1),
        )
        self.activate_term(1, completed=False)
        official_material = self.crla.material
        official_material.is_official_reading = True
        official_material.is_system_owned = True
        official_material.assessment_kind = 'crla'
        official_material.system_assessment_key = 'bosy_crla_pretest'
        official_material.system_assessment_phase = 'pretest'
        official_material.official_term = 1
        official_material.status = 'published'
        official_material.is_active = True
        official_material.student_access = True
        official_material.save(update_fields=[
            'is_official_reading', 'is_system_owned', 'assessment_kind',
            'system_assessment_key', 'system_assessment_phase', 'official_term',
            'status', 'is_active', 'student_access', 'updated_at',
        ])
        # A historical completed attempt must not suppress the current-term
        # missed-assessment request.
        Assessment.objects.create(
            student=self.student, enrollment=self.enrollment, teacher=self.section.teacher,
            title='Historical CRLA attempt', code='HISTORICAL-CRLA', assessment_type='word',
            attempt_status='completed', completed_at=timezone.now(), official_term=3,
        )
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stage'], 'assessment_not_taken')
        self.assertFalse(response.context['assessment_request_pending'])
        self.assertContains(response, 'Request to Take Assessment')
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')

        request_response = self.client.post(
            reverse('request_assessment_access'), {'section_id': self.section.id},
        )
        self.assertEqual(request_response.status_code, 200, request_response.content.decode())
        self.assertTrue(request_response.json()['pending'])
        pending = self.client.get(reverse('assessment'))
        self.assertEqual(pending.context['stage'], 'assessment_not_taken')
        self.assertTrue(pending.context['assessment_request_pending'])
        self.assertContains(pending, 'Request to Take Assessment<br>is Pending', html=True)

    def test_crla_request_state_is_not_shown_before_or_during_assessment_week(self):
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=1, title='Future Pre-Assessment Week',
            event_type='pre_assessment', start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=3),
        )
        self.activate_term(1, completed=False)
        before = self.client.get(reverse('assessment'))
        self.assertNotEqual(before.context['stage'], 'assessment_not_taken')

        event = CalendarEvent.objects.filter(
            school_calendar=self.calendar, event_type='pre_assessment',
        ).latest('id')
        event.start_date = self.today
        event.end_date = self.today + timedelta(days=2)
        event.save(update_fields=['start_date', 'end_date', 'updated_at'])
        during = self.client.get(reverse('assessment'))
        self.assertNotEqual(during.context['stage'], 'assessment_not_taken')

    def test_advancing_to_term_two_clears_term_one_missed_request_state(self):
        """A prior term's closed CRLA window must not mark the new term missed."""
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=1, title='Term 1 Pre-Assessment Week',
            event_type='pre_assessment', start_date=self.today - timedelta(days=7),
            end_date=self.today - timedelta(days=1),
        )
        self.activate_term(2, completed=False)
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=2, title='Term 2 Midline Assessment Week',
            event_type='midline_assessment', start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=3),
        )
        Material.objects.create(
            teacher=self.section.teacher, title='Official Midline CRLA', code='SUP-MIDLINE',
            type='assessment', item_type='word', status='published', assessment_kind='crla',
            is_official_reading=True, is_system_owned=True, student_access=True,
            system_assessment_key='midline_crla_midtest', system_assessment_phase='midtest',
            official_term=2,
        )

        response = self.client.get(reverse('assessment'))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.context['stage'], 'assessment_not_taken')
        self.assertEqual(response.context['stage'], 'unavailable')
        self.assertContains(response, 'CRLA Assessment is not available yet.')
        self.assertEqual(_current_learning_context(self.student)['term'], 2)
        self.assertEqual(_current_learning_context(self.student)['state'], 'CRLA_PENDING')

    def test_assessment_week_toggle_off_hides_active_crla_launch_card(self):
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=1, title='Current Pre-Assessment Week',
            event_type='pre_assessment', start_date=self.today, end_date=self.today + timedelta(days=2),
        )
        self.activate_term(1, completed=False)
        self.section.assessment_week_enabled = False
        self.section.save(update_fields=['assessment_week_enabled', 'updated_at'])
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stage'], 'unavailable')
        self.assertContains(response, 'CRLA Assessment is not available yet.')
        self.assertNotContains(response, 'Start Assessment')

    def test_assessment_week_on_uses_teacher_waiting_card_for_official_crla(self):
        CalendarEvent.objects.create(
            school_calendar=self.calendar, term=1, title='Current Pre-Assessment Week',
            event_type='pre_assessment', start_date=self.today, end_date=self.today + timedelta(days=2),
        )
        self.activate_term(1, completed=False)
        self.section.assessment_week_enabled = True
        self.section.save(update_fields=['assessment_week_enabled', 'updated_at'])

        response = self.client.get(reverse('assessment'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stage'], 'assessment_week_locked')
        self.assertContains(response, 'Your teacher has turned on Assessment Week')
        self.assertContains(response, 'Please wait while your teacher prepares the assessment.')
        self.assertNotContains(response, 'Start Assessment')
        self.assertNotContains(response, 'What to do')

    def test_student_calendar_receives_the_advancing_debug_system_date(self):
        real_now = timezone.now()
        simulated_now = real_now + timedelta(days=1)
        SystemTimeOverride.objects.create(
            enabled=True, reference_time=simulated_now, configured_at=real_now,
        )
        invalidate_override_cache()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student_calendar_today'], simulated_now.astimezone(timezone.get_current_timezone()).date().isoformat())

        SystemTimeOverride.objects.filter(pk=1).update(enabled=False)
        invalidate_override_cache()
        real_response = self.client.get(reverse('dashboard'))
        self.assertEqual(real_response.context['student_calendar_today'], timezone.localdate().isoformat())
