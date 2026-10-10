"""Listing parity, ownership, compact payloads, and query growth on synthetic data."""

import json

from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import views
from .class_materials import ClassMaterialsProgress
from .models import (
    Assessment, Enrollment, Material, Practice, School, SchoolCalendar, Section,
    StoryResponseSubmission, SupplementaryMaterialPublication, User,
)
from .prescribed_test_fixtures import prescribed_term_fixture


class ClassMaterialsEfficiencyTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Listing Fixture School', code='LISTING')
        self.student = self.make_user('listing-student')
        self.calendar, self.section, self.enrollment, _ = prescribed_term_fixture(self.student)
        self.teacher = self.section.teacher
        self.factory = RequestFactory()

    def make_user(self, custom_id, role='student'):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name='Synthetic', last_name='User',
            sex='N/A', birth_month=1, birth_day=1, birth_year=2018,
            email=f'{custom_id}@example.test', password_hash='x', school_record=self.school,
        )

    def make_material(self, number, **overrides):
        values = dict(
            teacher=self.teacher, section=self.section, title=f'Fixture Material {number}',
            code=f'LIST-M-{number}', item_type='word', type='assessment', status='published',
            student_access=True, content_text='Synthetic reading text. ' * 150,
            content_json={'items': ['synthetic word'] * 30, 'language': 'English'},
        )
        values.update(overrides)
        material = Material.objects.create(**values)
        material.assigned_sections.add(self.section)
        SupplementaryMaterialPublication.objects.create(
            material=material, section=self.section, school_calendar=self.calendar, term=1,
        )
        return material

    def make_assessment(self, number, material=None):
        group = Assessment.objects.create(
            teacher=self.teacher, section=self.section, title=f'Assessment {number}',
            code=f'LIST-A-{number}', assessment_type='word',
        )
        if material is not None:
            material.assessment = group
            material.save(update_fields=['assessment'])
        return group

    def attempt(self, group, number, **overrides):
        values = dict(
            teacher=self.teacher, section=self.section, source_assessment=group,
            student=self.student, enrollment=self.enrollment, title='Synthetic attempt',
            code=f'{group.code}-TRY-{number}', assessment_type='word', attempt_number=number,
            attempt_status='completed', completed_at=timezone.now(), time_score=80 + number,
        )
        values.update(overrides)
        return Assessment.objects.create(**values)

    def direct_result(self, material, number, **overrides):
        values = dict(
            teacher=self.teacher, section=self.section, student=self.student,
            enrollment=self.enrollment, material=material, title='Synthetic result',
            code=f'LIST-R-{number}', assessment_type='paragraph', attempt_status='completed',
            completed_at=timezone.now(), supplementary_school_calendar=self.calendar,
            supplementary_term=1, total_score=92,
        )
        values.update(overrides)
        return Assessment.objects.create(**values)

    def request(self, *, user=None, summary=False, section=None, view=None):
        params = {'section_id': (section or self.section).id}
        if summary:
            params['view'] = 'summary'
        request = self.factory.get('/api/class/materials/', params)
        request.session = {'user_id': (user or self.student).id}
        response = (view or views.get_class_materials)(request)
        return response

    def payload(self, **kwargs):
        response = self.request(**kwargs)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def by_id(self, payload, item_id):
        return next(item for bucket in payload['materials'].values() for item in bucket if item['id'] == item_id)

    def test_summary_keeps_cards_and_removes_duplicate_exercise_payload(self):
        material = self.make_material(1, content_json={
            'template_title': 'Story Reading', 'activity_type': 'story_reading',
            'language': 'English', 'sourceMaterialId': 123, 'items': ['word'] * 30,
            'storyText': 'Synthetic story. ' * 100,
        }, item_type='paragraph')
        full_response = self.request()
        summary_response = self.request(summary=True)
        full = json.loads(full_response.content)
        summary = json.loads(summary_response.content)
        self.assertIn('all_materials', full)
        self.assertNotIn('all_materials', summary)
        full_item = self.by_id(full, f'material-{material.id}')
        item = self.by_id(summary, f'material-{material.id}')
        self.assertNotIn('content', item)
        self.assertNotIn('content_text', item)
        self.assertEqual(item['content_json'], {
            'template_title': 'Story Reading', 'activity_type': 'story_reading',
            'language': 'English', 'sourceMaterialId': 123,
        })
        for key in ('id', 'items', 'title', 'assigned_sections', 'student_has_completed', 'student_access'):
            self.assertEqual(item[key], full_item[key])
        self.assertLess(len(summary_response.content), len(full_response.content) / 2)
        self.assertEqual(summary_response['Cache-Control'], 'private, no-store')
        self.assertEqual(summary['materials']['story_reading'][0], item)

    def test_batched_attempts_match_existing_model_methods_and_ignore_other_calendars(self):
        material = self.make_material(1)
        group = self.make_assessment(1, material)
        self.attempt(group, 1, attempt_status='started', completed_at=None)
        self.attempt(group, 2, time_score=94)
        old_calendar = SchoolCalendar.objects.create(school_year='2020-2021', current_term=1, is_active=False)
        old_section = Section.objects.create(
            school=self.school, school_calendar=old_calendar, teacher=self.teacher,
            class_name='Historical fixture', class_code='LIST-OLD',
        )
        old_enrollment = Enrollment.objects.create(
            student=self.student, section=old_section, school=self.school,
            school_calendar=old_calendar, status='inactive', is_active=False,
        )
        self.attempt(group, 3, enrollment=old_enrollment, time_score=5)
        rows = group.get_attempts(self.student)
        item = self.by_id(self.payload(summary=True), f'material-{material.id}')
        self.assertEqual(item['attempt_count'], len(rows))
        self.assertEqual(item['completed_attempt_count'], 1)
        self.assertTrue(item['student_has_completed'])
        self.assertEqual(item['latest_attempt_summary'], group.get_latest_attempt_summary(self.student))
        self.assertEqual(item['latest_time_score'], 94)

    def test_special_completion_rules_remain_distinct_and_term_scoped(self):
        story = self.make_material(1, item_type='paragraph', content_json={'activity_type': 'story_reading'})
        response = self.make_material(2, item_type='paragraph', content_json={'activity_type': 'story_response'})
        retell = self.make_material(3, item_type='paragraph', content_json={'activity_type': 'retell_story'})
        fluency = self.make_material(4, content_json={'activity_key': 'fluency_reading'})
        self.direct_result(story, 1, supplementary_term=2)
        StoryResponseSubmission.objects.create(
            student=self.student, material=response, school_calendar=self.calendar, term=1,
            status='pending',
        )
        StoryResponseSubmission.objects.create(
            student=self.student, material=retell, school_calendar=self.calendar, term=1,
            status='pending',
        )
        self.direct_result(retell, 2)
        self.direct_result(fluency, 3)  # A generic result cannot complete Fluency.
        payload = self.payload(summary=True)
        self.assertFalse(self.by_id(payload, f'material-{story.id}')['student_has_completed'])
        self.assertFalse(self.by_id(payload, f'material-{response.id}')['student_has_completed'])
        self.assertTrue(self.by_id(payload, f'material-{response.id}')['story_response_submitted'])
        self.assertTrue(self.by_id(payload, f'material-{retell.id}')['student_has_completed'])
        self.assertFalse(self.by_id(payload, f'material-{fluency.id}')['student_has_completed'])
        self.direct_result(story, 4)
        self.direct_result(fluency, 5, remarks=views.ARAL_RESULT_PREFIXES['fluency-reading'] + '{}')
        payload = self.payload(summary=True)
        self.assertTrue(self.by_id(payload, f'material-{story.id}')['student_has_completed'])
        self.assertTrue(self.by_id(payload, f'material-{fluency.id}')['student_has_completed'])

    def test_legacy_direct_result_still_completes_linked_material(self):
        material = self.make_material(1)
        group = self.make_assessment(1, material)
        self.attempt(group, 1, attempt_status='started', completed_at=None)
        self.direct_result(material, 1, enrollment=None, supplementary_school_calendar=None, supplementary_term=None)
        item = self.by_id(self.payload(summary=True), f'material-{material.id}')
        self.assertTrue(item['student_has_completed'])
        self.assertEqual(item['completed_attempt_count'], 1)
        self.assertEqual(item['latest_attempt_summary']['total_score'], 92)

    def test_summary_does_not_bypass_authorization_or_reuse_another_students_progress(self):
        material = self.make_material(1)
        self.direct_result(material, 1)
        self.make_assessment(1, material)
        other = self.make_user('listing-other')
        outsider = self.make_user('listing-outsider')
        prescribed_term_fixture(other, section=self.section, calendar=self.calendar, teacher=self.teacher)
        self.assertEqual(self.request(user=outsider, summary=True).status_code, 403)
        self.assertFalse(self.by_id(self.payload(user=other, summary=True), f'material-{material.id}')['student_has_completed'])
        self.assertTrue(self.by_id(self.payload(summary=True), f'material-{material.id}')['student_has_completed'])
        foreign_teacher = self.make_user('listing-foreign-teacher', role='teacher')
        self.assertEqual(self.request(user=foreign_teacher, summary=True).status_code, 403)

    def test_query_count_does_not_grow_per_material(self):
        def add(number):
            material = self.make_material(number)
            group = self.make_assessment(number, material)
            self.attempt(group, 1)
        add(1)
        self.payload(summary=True)  # Warm request-independent clock caches.
        with CaptureQueriesContext(connection) as small:
            self.payload(summary=True)
        for number in range(2, 21):
            add(number)
        with CaptureQueriesContext(connection) as large:
            payload = self.payload(summary=True)
        self.assertEqual(len(payload['materials']['word']), 20)
        self.assertLessEqual(len(large), len(small) + 3)

    def test_practice_attempt_counts_keep_current_enrollment_filter(self):
        practice = Practice.objects.create(
            teacher=self.teacher, section=self.section, title='Practice fixture', code='LIST-P',
            practice_type='word', status='published',
            attempts=[
                {'student_id': self.student.id, 'enrollment_id': str(self.enrollment.id)},
                {'student_id': self.student.id, 'enrollment_id': '999999'},
            ],
        )
        progress = ClassMaterialsProgress(self.student, [], [], [practice])
        self.assertEqual(progress.practice_attempt_count(practice), len(practice.get_attempts(self.student)))

    def test_material_reader_loads_content_by_id_after_summary_launch(self):
        material = self.make_material(1)
        request = self.factory.get('/dashboard/assessment/reading_ui/word/', {'id': f'material-{material.id}'})
        context = views._custom_material_reading_context(request)
        self.assertEqual(context['custom_material_launch_data']['content'], material.content_text)
        self.assertEqual(context['custom_material_launch_data']['content_json'], material.content_json)

    def test_summary_updates_scores_on_every_new_request(self):
        material = self.make_material(1)
        group = self.make_assessment(1, material)
        row = self.attempt(group, 1, attempt_status='started', completed_at=None)
        first = self.by_id(self.payload(summary=True), f'material-{material.id}')
        self.assertFalse(first['student_has_completed'])
        row.attempt_status = 'completed'
        row.completed_at = timezone.now()
        row.time_score = 95
        row.save(update_fields=['attempt_status', 'completed_at', 'time_score'])
        updated = self.by_id(self.payload(summary=True), f'material-{material.id}')
        self.assertTrue(updated['student_has_completed'])
        self.assertEqual(updated['latest_time_score'], 95)

    def test_summary_preserves_teacher_visibility_and_archived_filter(self):
        visible = self.make_material(1)
        archived = self.make_material(2, is_active=False, status='archived')
        for summary in (False, True):
            payload = self.payload(user=self.teacher, summary=summary)
            ids = {item['id'] for bucket in payload['materials'].values() for item in bucket}
            self.assertIn(f'material-{visible.id}', ids)
            self.assertNotIn(f'material-{archived.id}', ids)

    def test_summary_preserves_selected_student_publication_filter(self):
        material = self.make_material(1, publication_scope='selected_students')
        payload = self.payload(summary=True)
        self.assertNotIn(f'material-{material.id}', {item['id'] for bucket in payload['materials'].values() for item in bucket})
