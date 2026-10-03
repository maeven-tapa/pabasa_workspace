from datetime import timedelta
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, AssessmentRequest, CalendarEvent, LiveAssessmentSession, Material, School, User
from .prescribed_test_fixtures import PHASES, prescribed_term_fixture
from .system_clock import invalidate_override_cache
from .views import _current_crla_assessment_request


class MissedAssessmentRecoveryTests(TestCase):
    """Small URL-level regression suite for missed CRLA recovery only."""

    def setUp(self):
        self.today = timezone.localdate()
        self.school = School.objects.create(name='Recovery School', code='RECOVERY')
        self.student = User.objects.create(
            custom_id='REC-STUDENT', role='student', first_name='Recovery', last_name='Student',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email='recovery-student@example.test', password_hash='x', school_record=self.school,
        )
        self.student.set_password('test-password')
        self.student.save(update_fields=['password_hash', 'updated_at'])

    def login(self, user):
        response = self.client.post(reverse('login_user'), {
            'custom_id': user.custom_id,
            'password': 'test-password',
        })
        self.assertEqual(response.status_code, 200, response.content.decode())

    def configure_term(self, term, *, window_start=None, window_end=None, school_year=None):
        if not hasattr(self, 'calendar'):
            calendar, section, enrollment, _ = prescribed_term_fixture(
                self.student, today=self.today, term=1, completed=False,
            )
            calendar.school_year = school_year or '2026-2027'
            calendar.save(update_fields=['school_year', 'updated_at'])
            self.calendar, self.section, self.enrollment = calendar, section, enrollment
        calendar, section, enrollment = self.calendar, self.section, self.enrollment
        calendar.current_term = term
        calendar.is_active = True
        calendar.save(update_fields=['current_term', 'is_active', 'updated_at'])
        section.school_calendar = calendar
        section.save(update_fields=['school_calendar'])
        enrollment.school_calendar = calendar
        enrollment.save(update_fields=['school_calendar', 'updated_at'])
        self.student.school_calendar = calendar
        self.student.save(update_fields=['school_calendar', 'updated_at'])
        section.teacher.set_password('test-password')
        section.teacher.save(update_fields=['password_hash', 'updated_at'])
        # Keep all three configured blocks present.  The selected term is the
        # only block containing the test date; the others are unambiguously
        # before/after it so _calendar_current_term() can resolve naturally.
        for block_term in (1, 2, 3):
            if block_term < term:
                opening_date, closing_date = self.today - timedelta(days=60), self.today - timedelta(days=30)
            elif block_term > term:
                opening_date, closing_date = self.today + timedelta(days=30), self.today + timedelta(days=60)
            else:
                opening_date, closing_date = self.today - timedelta(days=7), self.today + timedelta(days=7)
            CalendarEvent.objects.update_or_create(
                school_calendar=calendar, term=block_term, event_type='school_opening',
                defaults={'title': f'Term {block_term} Opening Block', 'start_date': opening_date, 'end_date': opening_date},
            )
            CalendarEvent.objects.update_or_create(
                school_calendar=calendar, term=block_term, event_type='school_closing',
                defaults={'title': f'Term {block_term} Closing Block', 'start_date': closing_date, 'end_date': closing_date},
            )
        phase, key = PHASES[term]
        material = Material.objects.filter(system_assessment_key=key).first()
        if material is None:
            material = Material.objects.create(
                teacher=section.teacher,
                section=section,
                title=f'Official {phase}',
                code=f'REC-{term}-{calendar.id}',
                type='assessment', item_type='word', status='published',
                student_access=True, assessment_kind='crla',
                is_official_reading=True, is_system_owned=True,
                system_assessment_key=key,
                system_assessment_phase=phase,
                official_term=term,
            )
        window_start = window_start or self.today - timedelta(days=7)
        window_end = window_end or self.today - timedelta(days=1)
        event_type = {1: 'pre_assessment', 2: 'midline_assessment', 3: 'post_assessment'}[term]
        CalendarEvent.objects.update_or_create(
            school_calendar=calendar, term=term, event_type=event_type,
            defaults={
                'title': f'{phase} Assessment Week',
                'start_date': window_start, 'end_date': window_end,
            },
        )
        return calendar, section, enrollment, material

    def create_missed_request(self, term):
        calendar, section, enrollment, material = self.configure_term(term)
        self.login(self.student)
        response = self.client.post(reverse('request_assessment_access'), {'section_id': section.id})
        return response, calendar, section, enrollment, material

    def test_term_1_2_and_3_missed_requests_are_scoped_to_official_context(self):
        for term in (1, 2, 3):
            with self.subTest(term=term):
                AssessmentRequest.objects.all().delete()
                response, calendar, section, _, material = self.create_missed_request(term)
                self.assertEqual(response.status_code, 200, response.content.decode())
                request = AssessmentRequest.objects.get(student=self.student, section=section, status='pending')
                self.assertEqual(request.school_calendar_id, calendar.id)
                self.assertEqual(request.term, term)
                self.assertEqual(request.official_phase, PHASES[term][0])
                self.assertEqual(request.official_material_id, material.id)
                self.client.session.flush()

    def test_before_and_during_assessment_week_are_rejected(self):
        for term in (1, 2, 3):
            with self.subTest(term=term):
                AssessmentRequest.objects.all().delete()
                calendar, section, _, _ = self.configure_term(
                    term,
                    window_start=self.today + timedelta(days=1),
                    window_end=self.today + timedelta(days=3),
                )
                self.login(self.student)
                before = self.client.post(reverse('request_assessment_access'), {'section_id': section.id})
                self.assertEqual(before.status_code, 409, before.content.decode())
                event = calendar.events.filter(term=term).latest('id')
                event.start_date = self.today
                event.end_date = self.today + timedelta(days=2)
                event.save(update_fields=['start_date', 'end_date', 'updated_at'])
                during = self.client.post(reverse('request_assessment_access'), {'section_id': section.id})
                self.assertEqual(during.status_code, 409, during.content.decode())
                self.client.session.flush()

    def test_approval_preserves_scope_and_creates_no_session_or_result(self):
        response, calendar, section, _, material = self.create_missed_request(1)
        request = AssessmentRequest.objects.get(student=self.student, section=section, status='pending')
        teacher = section.teacher
        self.client.session.flush()
        self.login(teacher)
        approved = self.client.post(reverse('approve_assessment_request', args=[request.id]))
        self.assertEqual(approved.status_code, 200, approved.content.decode())
        request.refresh_from_db()
        self.assertEqual(request.status, 'approved')
        self.assertEqual(request.school_calendar_id, calendar.id)
        self.assertEqual(request.term, 1)
        self.assertEqual(request.official_phase, PHASES[1][0])
        self.assertEqual(request.official_material_id, material.id)
        session = LiveAssessmentSession.objects.get(section=section)
        self.assertEqual(session.status, 'waiting')
        self.assertIn(self.student.id, session.student_ids)
        self.assertIsNone(session.start_at)
        self.assertFalse(Assessment.objects.filter(student=self.student, official_term=1).exists())
        current_request = _current_crla_assessment_request(self.student, section, {'approved'})
        self.assertIsNotNone(current_request)
        self.assertEqual(current_request.id, request.id)

    def test_approved_student_sees_waiting_card_without_self_start(self):
        _, _, section, _, _ = self.create_missed_request(1)
        request = AssessmentRequest.objects.get(student=self.student, section=section, status='pending')
        self.client.session.flush()
        self.login(section.teacher)
        self.assertEqual(self.client.post(reverse('approve_assessment_request', args=[request.id])).status_code, 200)
        self.client.session.flush()
        self.login(self.student)
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stage'], 'assessment_week_locked')
        self.assertContains(response, 'Please wait while your teacher prepares the assessment.')
        # The shared page JavaScript contains the request label as a client
        # string; the rendered recovery branch must not expose its button.
        self.assertNotContains(response, 'id="requestAssessmentButton"')
        self.assertNotContains(response, 'Start Assessment')
        session = LiveAssessmentSession.objects.get(section=section)
        self.assertEqual(session.status, 'waiting')
        self.assertIn(self.student.id, session.student_ids)
        self.assertIsNone(session.start_at)

    def test_legacy_null_request_does_not_suppress_scoped_request(self):
        calendar, section, _, material = self.configure_term(1)
        AssessmentRequest.objects.create(
            student=self.student, section=section, status='approved',
            school_calendar=None, term=None, official_phase=None, official_material=None,
        )
        self.login(self.student)
        response = self.client.post(reverse('request_assessment_access'), {'section_id': section.id})
        self.assertEqual(response.status_code, 200, response.content.decode())
        scoped = AssessmentRequest.objects.get(
            student=self.student, section=section, status='pending', school_calendar=calendar,
        )
        self.assertEqual(scoped.official_material_id, material.id)
        self.assertTrue(AssessmentRequest.objects.filter(pk=scoped.pk).exists())
        self.assertTrue(AssessmentRequest.objects.filter(student=self.student, school_calendar__isnull=True).exists())

    def test_approved_session_uses_normal_teacher_start_action(self):
        _, _, section, _, material = self.create_missed_request(1)
        request = AssessmentRequest.objects.get(student=self.student, section=section, status='pending')
        self.client.session.flush()
        self.login(section.teacher)
        approved = self.client.post(reverse('approve_assessment_request', args=[request.id]))
        self.assertEqual(approved.status_code, 200, approved.content.decode())
        session = LiveAssessmentSession.objects.get(section=section, material=material)
        self.assertEqual(session.status, 'waiting')
        self.assertIsNone(session.start_at)

        started = self.client.post(
            reverse('live_assessment_session_action', args=[session.id]),
            data=json.dumps({'action': 'start', 'selected_student_ids': [self.student.id], 'countdown_seconds': 0}),
            content_type='application/json',
        )
        self.assertEqual(started.status_code, 200, started.content.decode())
        session.refresh_from_db()
        self.assertIn(session.status, {'started', 'countdown'})
        self.assertIsNotNone(session.start_at)
        self.assertIn(self.student.id, session.student_ids)

        self.client.session.flush()
        self.login(self.student)
        state = self.client.get(reverse('live_assessment_session_state', args=[session.id]))
        self.assertEqual(state.status_code, 200, state.content.decode())
        self.assertNotEqual(state.json().get('session', {}).get('status'), 'ended')

    def test_approved_recovery_completes_through_normal_end_session_pipeline(self):
        _, calendar, section, enrollment, material = self.create_missed_request(1)
        request = AssessmentRequest.objects.get(student=self.student, section=section, status='pending')
        self.client.session.flush()
        self.login(section.teacher)
        approved = self.client.post(reverse('approve_assessment_request', args=[request.id]))
        self.assertEqual(approved.status_code, 200, approved.content.decode())

        session = LiveAssessmentSession.objects.get(section=section, material=material)
        started = self.client.post(
            reverse('live_assessment_session_action', args=[session.id]),
            data=json.dumps({'action': 'start', 'selected_student_ids': [self.student.id], 'countdown_seconds': 0}),
            content_type='application/json',
        )
        self.assertEqual(started.status_code, 200, started.content.decode())

        recovery_state = {
            'stage': 'completed', 'branch': 'rhymes', 'temporary_completed': True,
            'task1_score': 6, 'task2_type': 'Task 2L / Rhymes', 'task2_score': 4,
            'task2_rhymes_score': 4, 'part1_total_score': 10,
            'crla_classification': 'Low Emerging Reader',
            'classification': 'Low Emerging Reader',
            'completion_evidence': {'part1_total_score': 10, 'task2_rhymes_score': 4},
            # Part 2 evidence is required by the normal CRLA finalizer before
            # it will persist the official Reading Profile.
            'story_number': 1, 'story_total_words': 100, 'words_read': 80,
            'miscues': 5, 'correct_answers': 3, 'duration_seconds': 60,
            'learner_experience_rating': 4, 'learner_experience': 4,
        }
        from .views import _update_live_student_state
        _update_live_student_state(session, self.student.id, {
            'status': 'completed', 'progress': 1, 'items_completed': 10,
            'items_total': 10, 'elapsed_seconds': 42,
            'recovery_state': recovery_state,
            'completion_payload': {
                'assessment_type': 'word', 'material_id': f'material-{material.id}',
                'scores': {'correct_words': 6, 'duration_seconds': 42},
            },
        })
        session.save(update_fields=['student_states'])

        from .views import _build_live_session_completion_payload, _student_can_complete_assessment
        payload = _build_live_session_completion_payload(
            session, self.student, session.student_states[str(self.student.id)],
        )
        self.assertTrue(payload.get('crla_score_data'))
        self.assertTrue(_student_can_complete_assessment(self.student, material=material))

        ended = self.client.post(
            reverse('live_assessment_session_action', args=[session.id]),
            data=json.dumps({'action': 'end'}), content_type='application/json',
        )
        self.assertEqual(ended.status_code, 200, ended.content.decode())

        result_qs = Assessment.objects.filter(
            student=self.student, material=material, attempt_status='completed',
        )
        self.assertEqual(result_qs.count(), 1)
        result = result_qs.get()
        self.assertEqual(result.enrollment_id, enrollment.id)
        self.assertEqual(result.system_assessment_key, PHASES[1][1])
        self.assertEqual(result.system_assessment_phase, PHASES[1][0])
        self.assertIsNotNone(result.completed_at)
        self.assertTrue(result.crla_classification or result.classification)
        self.assertEqual(
            Assessment.objects.filter(student=self.student, material=material).count(), 1,
        )

    def tearDown(self):
        invalidate_override_cache()
        super().tearDown()
