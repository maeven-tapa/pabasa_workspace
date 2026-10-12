"""Students term selection uses disposable calendars and persisted historical records."""
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import views
from .models import Assessment, CalendarEvent, ClassCrlaFinalization, Enrollment, Material, SchoolCalendar, StudentActivityProgress, StoryReadingProgress, SupplementaryMaterialPublication
from .tests_class_management_sync import ManagementSyncFixtures


class StudentsTermFixtures(ManagementSyncFixtures):
    def setUp(self):
        super().setUp()
        self.set_term(3)
        self.materials = {}
        self.results = {}
        for term, key, level in [
            (1, 'bosy_crla_pretest', 'Low Emerging Reader'),
            (2, 'midline_crla_midtest', 'Developing Reader'),
            (3, 'eosy_crla_posttest', 'Transitioning Reader'),
        ]:
            root = Assessment.objects.create(teacher=self.teacher, title=f'Disposable official term {term}',
                code=f'DIR-ROOT-{term}', system_assessment_key=key,
                system_assessment_phase=views.STUDENT_DIRECTORY_TERM_PHASES[term], official_term=term)
            material, _ = Material.objects.update_or_create(system_assessment_key=key, defaults=dict(
                teacher=self.teacher, assessment=root, title=f'Disposable official term {term}',
                code=f'DIR-MAT-{term}', type='assessment', item_type='paragraph',
                status='published', is_official_reading=True, is_system_owned=True, assessment_kind='crla',
                system_assessment_phase=views.STUDENT_DIRECTORY_TERM_PHASES[term], official_term=term))
            self.materials[term] = material
            self.results[term] = Assessment.objects.create(
                teacher=self.teacher, student=self.student, enrollment=self.enrollment,
                section=self.section, material=material, official_term=term,
                system_assessment_key=key, system_assessment_phase=views.STUDENT_DIRECTORY_TERM_PHASES[term],
                attempt_status='completed', completed_at=timezone.now(),
                crla_classification=level, classification=level,
                title=f'Disposable term {term} result', code=f'DIR-RESULT-{term}', total_score=term * 7,
            )
        self.story = Material.objects.create(teacher=self.teacher, section=self.section,
            title='Disposable historical story', code='DIR-STORY', item_type='paragraph',
            type='material', status='published', student_access=True,
            content_json={'activity_type': 'story_reading', 'template_title': 'Story Reading'})
        SupplementaryMaterialPublication.objects.create(section=self.section, school_calendar=self.calendar,
            term=1, material=self.story, is_active=True)
        self.story_progress = StoryReadingProgress.objects.create(student=self.student, material=self.story,
            enrollment=self.enrollment, school_calendar=self.calendar, term=1,
            completed=True, completed_at=timezone.now(), reading_score=4)
        self.progress = StudentActivityProgress.objects.create(student=self.student, school_calendar=self.calendar,
            term=1, activity_key=views._prescribed_activity_order()[0], activity_completed=True, completed_items=1, total_items=1)

    def page(self, **params):
        # Isolate page behavior from unrelated dashboard aggregation.
        with patch('pabasa_app.views._dashboard_context', side_effect=lambda request, role, extra: dict(extra, nav_role=role)):
            return self.client.get(reverse('students'), params)

    def directory(self, **params):
        return self.client.get(reverse('get_teacher_students_api'), {'sync': 'directory', 'section_id': self.section.pk, **params})


class StudentsTermSelectionTests(StudentsTermFixtures, TestCase):
    def test_both_defaults_use_dated_term_three_despite_stale_term_one(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_crla_term'], 3)
        self.assertEqual(response.context['selected_crla_phase'], 'posttest')
        self.assertEqual(response.context['selected_aral_term'], 3)
        self.assertFalse(response.context['crla_term_manual'])
        self.assertFalse(response.context['aral_term_manual'])
        self.assertContains(response, 'id="assessmentPeriodFilterWrap" data-default="3" data-assessment="posttest"')
        self.assertContains(response, 'id="aralTermSelect" data-default="3"')
        self.calendar.refresh_from_db()
        self.assertEqual(self.calendar.current_term, 1)

    def test_explicit_selections_remain_independent(self):
        context = self.page(term='1', aral_term='2').context
        self.assertEqual((context['selected_crla_term'], context['selected_aral_term']), (1, 2))
        self.assertTrue(context['crla_term_manual'])
        self.assertTrue(context['aral_term_manual'])

    def test_invalid_selection_and_fresh_load_ignore_old_session_selection(self):
        self.page(term='1', aral_term='1')
        self.assertEqual(self.client.session['teacher_aral_selected_term'], 1)
        response = self.page(term='invalid', aral_term='9')
        self.assertEqual((response.context['selected_crla_term'], response.context['selected_aral_term']), (3, 3))

    def test_auto_feed_follows_calendar_instead_of_the_previous_dropdown_value(self):
        for term in [3, 1, 2]:
            self.set_term(term)
            data = self.directory(term='1', assessment='pretest', term_mode='auto').json()
            self.assertEqual(data['directory_terms']['term'], term)
            self.assertEqual(data['directory_terms']['assessment'], views.STUDENT_DIRECTORY_TERM_PHASES[term])
            self.assertEqual(data['students'][0]['total_score'], term * 7)
            self.assertEqual(data['crla']['material_id'], self.materials[term].pk)

    def test_manual_feed_returns_historical_term_and_matching_export_material(self):
        for term, level in [(1, 'Low Emerging Reader'), (2, 'Developing Reader')]:
            data = self.directory(term=str(term), assessment='posttest', term_mode='manual').json()
            self.assertEqual(data['directory_terms']['calendar']['term'], 3)
            self.assertEqual(data['directory_terms']['term'], term)
            self.assertFalse(data['directory_terms']['actions_available'])
            self.assertEqual(data['students'][0]['reading_level'], level)
            self.assertEqual(data['students'][0]['total_score'], term * 7)
            self.assertEqual(data['crla']['material_id'], self.materials[term].pk)

    def test_pending_active_result_does_not_fall_back_to_historical_classification(self):
        self.results[3].attempt_status = 'started'
        self.results[3].completed_at = None
        self.results[3].save()
        self.assertEqual(self.directory(term_mode='auto').json()['students'][0]['reading_level'], 'Pending')
        self.assertEqual(self.directory(term='1', term_mode='manual').json()['students'][0]['reading_level'], 'Low Emerging Reader')

    def test_no_active_term_has_no_hardcoded_or_unfiltered_fallback(self):
        self.calendar.events.all().delete()
        response = self.page()
        self.assertIsNone(response.context['selected_crla_term'])
        self.assertIsNone(response.context['selected_aral_term'])
        self.assertContains(response, 'No Active Term')
        data = self.directory(term='1', term_mode='auto').json()
        self.assertIsNone(data['directory_terms']['term'])
        self.assertEqual(data['students'], [])
        self.assertFalse(data['crla']['finalize_ready'])
        self.assertEqual(self.directory(term='1', term_mode='manual').json()['students'][0]['reading_level'], 'Low Emerging Reader')

    def test_historical_aral_progress_is_visible_without_current_exit_candidates(self):
        response = self.page(aral_term='1', partial='aral')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['aral_story_performance_data'][0]['students'][0]['score'], 4)
        self.assertGreater(response.context['aral_prescribed_activity_data']['percentage'], 0)
        self.assertFalse(response.context['aral_actions_available'])
        self.assertEqual(response.context['aral_review_students'], [])
        self.assertContains(response, 'disabled title="Exit actions are available only for the active term."')
        self.assertNotContains(response, 'id="assessmentPeriodFilterWrap"')
        self.assertEqual(views._collect_supplementary_student_results(self.section, 1), [])
        self.assertEqual(response['Cache-Control'], 'no-store, private')

    def test_term_views_do_not_modify_results_enrollments_progress_or_finalizations(self):
        finalization = ClassCrlaFinalization.objects.create(section=self.section, material=self.materials[1], finalized_by=self.teacher)
        models = [Assessment, Enrollment, StudentActivityProgress, StoryReadingProgress, ClassCrlaFinalization]
        before = [list(model.objects.order_by('pk').values()) for model in models]
        for term in [1, 2, 3]:
            self.page(aral_term=str(term), term=str(term))
            self.directory(term=str(term), term_mode='manual')
        self.assertEqual([list(model.objects.order_by('pk').values()) for model in models], before)
        self.assertEqual(self.directory(term='1', term_mode='manual').json()['crla']['finalized_at'], finalization.finalized_at.isoformat())

    def test_other_teachers_and_cross_school_sections_are_not_exposed(self):
        self.assertEqual(self.directory(section_id=self.other_section.pk).status_code, 403)
        self.other_section.teacher = self.teacher
        from .models import School
        self.other_section.school = School.objects.create(name='Foreign Directory School')
        self.other_section.save()
        self.assertEqual(self.directory(section_id=self.other_section.pk).status_code, 403)

    def test_school_year_transition_uses_matching_section_without_transferring_records(self):
        successor = SchoolCalendar.objects.create(school_year='2027-2028', current_term=1)
        self.calendar.is_active = False
        self.calendar.save()
        next_section = self.new_section('SYNC-NEXT', self.teacher)
        next_section.school_calendar = successor
        next_section.save()
        for kind, day in [('school_opening', date(2026, 10, 1)), ('school_closing', date(2026, 12, 1))]:
            CalendarEvent.objects.create(school_calendar=successor, term=2, event_type=kind, title=kind, start_date=day, end_date=day)
        response = self.page()
        self.assertEqual(response.context['assessment_week_section'], next_section)
        self.assertEqual(response.context['selected_crla_term'], 2)
        data = self.directory(term_mode='auto').json()
        self.assertEqual(data['directory_terms']['section_id'], next_section.pk)
        self.assertEqual(data['directory_terms']['calendar']['id'], successor.pk)
        self.assertEqual(data['students'], [])
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.school_calendar_id, self.calendar.pk)

    def test_page_and_partial_require_teacher_authorization(self):
        self.client.logout()
        self.assertEqual(self.page(partial='aral').status_code, 302)

    def test_unassigned_teacher_still_defaults_to_the_school_calendar_without_roster_leak(self):
        self.teacher.school_calendar = self.calendar
        self.teacher.save()
        self.section.teacher = self.other_teacher
        self.section.save()
        response = self.page()
        self.assertEqual(response.context['selected_crla_term'], 3)
        self.assertEqual(response.context['selected_aral_term'], 3)
        data = self.directory(section_id='', term_mode='auto').json()
        self.assertEqual(data['directory_terms']['calendar']['term'], 3)
        self.assertEqual(data['students'], [])
        self.assertFalse(data['directory_terms']['actions_available'])

    def test_historical_export_keeps_existing_finalization_scoped_to_selected_assessment(self):
        data = self.directory(term='1', term_mode='manual').json()
        self.assertTrue(data['crla']['finalize_ready'])
        workbook = BytesIO(b'disposable export')
        workbook.name = 'crla.xlsx'
        before = list(Assessment.objects.order_by('pk').values())
        with patch('pabasa_app.views.export_crla_excel', return_value=workbook) as export:
            response = self.client.get(reverse('export_crla_assessment', args=[self.materials[1].assessment_id]), {
                'source': 'student-directory', 'section_id': self.section.pk, 'material_id': self.materials[1].pk,
            })
        self.assertEqual(response.status_code, 200)
        export.assert_called_once_with(self.materials[1].assessment_id, section_id=self.section.pk, crla_term=1, crla_phase='pretest')
        self.assertTrue(ClassCrlaFinalization.objects.filter(section=self.section, material=self.materials[1]).exists())
        self.assertFalse(ClassCrlaFinalization.objects.filter(section=self.section, material=self.materials[3]).exists())
        self.assertEqual(list(Assessment.objects.order_by('pk').values()), before)
