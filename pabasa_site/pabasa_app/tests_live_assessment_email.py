"""Live summary presentation and unchanged end-session delivery contract."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from .live_assessment_email import render_summary_email, send_summary_email, summary_context


def sample_session(count=6, completed=5, *, missing=False):
    """Synthetic fixture: no production student data or database access."""
    stamp = datetime(2026, 11, 10, 6, 30, tzinfo=dt_timezone.utc)
    students = [SimpleNamespace(pk=index + 1, first_name=f'Sample Learner {index + 1}',
        last_name='Example', custom_id=f'SAMPLE-{index + 1:03}') for index in range(count)]
    teacher = SimpleNamespace(first_name='Sample', last_name='Teacher', email='teacher@example.com',
                              school_record=SimpleNamespace(name='Salawag Elementary School'))
    section = SimpleNamespace(grade_level='Grade 2', section='Sample Section', class_name='Sample Class',
                              school=teacher.school_record)
    material = SimpleNamespace(title='End of School Year (EoSY) CRLA Post-Test', assessment_kind='crla',
        system_assessment_phase='posttest', system_assessment_key='eosy_crla_posttest', assessment=None)
    session = SimpleNamespace(teacher=teacher, section=section, course=None, material=material,
        student_ids=[student.pk for student in students], status='ended', total_batches=1,
        start_at=stamp - timedelta(minutes=11), ends_at=stamp)
    if missing:
        session.section = None
        session.teacher = SimpleNamespace(first_name='', last_name='', email='teacher@example.com', school_record=None)
        session.start_at = session.ends_at = None
        session.status = ''
        material.title = ''
        material.system_assessment_phase = material.system_assessment_key = ''
        for student in students:
            student.custom_id = ''
    return session, students[:completed], students[completed:], stamp


class _Text(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.parts = []
        self.feed(html)

    def handle_data(self, value):
        self.parts.append(value)

    @property
    def text(self):
        return ' '.join(' '.join(self.parts).split())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='PABASA <noreply@example.com>', TIME_ZONE='Asia/Manila')
class LiveSummaryPresentationTests(SimpleTestCase):
    def test_one_multiple_missed_maximum_and_empty_sessions(self):
        for selected, completed in [(1, 1), (4, 4), (6, 5), (10, 7), (0, 0), (10, 0)]:
            with self.subTest(selected=selected, completed=completed):
                args = sample_session(selected, completed)
                original = deepcopy(args)
                context = summary_context(*args)
                self.assertEqual(args, original)
                self.assertEqual(context['selected_count'], selected)
                self.assertEqual(context['completed_count'], completed)
                self.assertEqual(context['missed_count'], selected - completed)
                self.assertEqual(context['completion_rate'], f'{round(completed / selected * 100, 1):g}' if selected else '0')
                text = _Text(render_summary_email(*args)).text
                self.assertIn(f'{completed} of {selected} selected students completed the assessment.', text)
                for student in args[1] + args[2]:
                    self.assertIn(student.first_name + ' ' + student.last_name, text)
                    self.assertIn(student.custom_id, text)
                if selected == completed:
                    self.assertIn('No missed students.', text)

    def test_scope_identity_phase_date_and_duration_are_actual_fields(self):
        context = summary_context(*sample_session())
        self.assertEqual(context['school_name'], 'Salawag Elementary School')
        self.assertEqual(context['teacher_name'], 'Sample Teacher')
        self.assertEqual(context['section_name'], 'Sample Section')
        self.assertEqual(context['grade_level'], 'Grade 2')
        self.assertEqual(context['assessment_type'], 'CRLA / EoSY Post-Assessment')
        self.assertEqual(context['assessment_datetime'], 'November 10, 2026 02:30 PM')
        self.assertEqual(context['session_duration'], '11 minutes')
        self.assertEqual(context['session_status'], 'Ended')

    def test_missing_optional_fields_do_not_invent_school_teacher_ids_or_duration(self):
        args = sample_session(1, 1, missing=True)
        html = render_summary_email(*args)
        text = _Text(html).text
        for value in ['Salawag', 'Sample Teacher', 'Sample Section', 'Grade 2', 'Session duration',
                      'Session status', 'PABASA ID:', 'None', 'nan', 'undefined']:
            self.assertNotIn(value, text)
        self.assertIn('Reading Activity', text)
        self.assertIn('PABASA classroom session', text)

    def test_full_participation_does_not_change_actual_session_status(self):
        session, completed, missed, ended = sample_session(1, 1)
        session.status = 'paused'
        context = summary_context(session, completed, missed, ended)
        self.assertEqual(context['completion_rate'], '100')
        self.assertEqual(context['session_status'], 'Paused')
        self.assertIsNone(context['session_duration'])

    def test_unreliable_or_multibatch_duration_is_omitted(self):
        session, completed, missed, ended = sample_session()
        for change in [dict(total_batches=2), dict(current_batch=2),
                       dict(batch_assignments={'1': 1, '2': 2}), dict(start_at=None), dict(ends_at=None),
                       dict(batch_assignments={'1': {}}), dict(batch_assignments={'1': 0}),
                       dict(start_at=ended + timedelta(seconds=1)),
                       dict(start_at=ended.replace(tzinfo=None)), dict(status='waiting')]:
            with self.subTest(change=change):
                modified = deepcopy(session)
                modified.__dict__.update(change)
                self.assertIsNone(summary_context(modified, completed, missed, ended)['session_duration'])

    def test_deleted_student_record_does_not_become_a_missed_or_completed_result(self):
        session, completed, missed, ended = sample_session(6, 5)
        completed.pop()
        context = summary_context(session, completed, missed, ended)
        self.assertEqual(context['selected_count'], 6)
        self.assertEqual(context['completed_count'], 4)
        self.assertEqual(context['missed_count'], 1)
        self.assertEqual(context['unavailable_records'], 1)

    def test_school_comes_from_session_class_before_teacher_or_material(self):
        args = sample_session()
        args[0].section.school = SimpleNamespace(name='Actual Session School')
        args[0].material.section = SimpleNamespace(school=SimpleNamespace(name='Unrelated Material School'))
        self.assertEqual(summary_context(*args)['school_name'], 'Actual Session School')

    def test_untrusted_names_and_titles_are_escaped(self):
        session, completed, missed, ended = sample_session(1, 1)
        session.material.title = '<script>alert(1)</script> & "Reading"'
        completed[0].first_name = '<img src=x onerror=alert(1)>'
        html = render_summary_email(session, completed, missed, ended)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img src=x', html)

    def test_email_has_no_scripts_frameworks_or_unsupported_layout_dependencies(self):
        html = render_summary_email(*sample_session())
        for unsupported in ['<script', '<svg', 'display:flex', 'display:grid', '<link', 'fonts.googleapis']:
            self.assertNotIn(unsupported, html)
        self.assertIn('max-width:660px', html)
        self.assertIn('@media only screen', html)
        self.assertIn('bgcolor="#0866ad"', html)
        self.assertIn('alt="PABASA"', html)
        self.assertIn('width="198" height="66"', html)

    def test_no_individual_academic_scores_are_added(self):
        args = sample_session()
        args[1][0].accuracy = 91.23456
        args[1][0].crla_classification = 'High Emerging Reader'
        html = render_summary_email(*args)
        self.assertNotIn('91.23456', html)
        self.assertNotIn('High Emerging Reader', html)
        self.assertIn('Participation only.', html)

    def test_real_django_send_preserves_plain_body_recipient_and_embeds_logo(self):
        session, completed, missed, ended = sample_session(1, 1)
        self.assertEqual(send_summary_email(session, completed, missed, ended, 'Original plain-text summary'), 1)
        message = mail.outbox[-1]
        self.assertEqual(message.to, ['teacher@example.com'])
        self.assertEqual(message.from_email, 'PABASA <noreply@example.com>')
        self.assertEqual(message.body, 'Original plain-text summary')
        self.assertEqual(message.subject, 'Live Assessment Summary: ' + session.material.title)
        mime = message.message()
        self.assertEqual(mime.get_content_type(), 'multipart/alternative')
        self.assertEqual(mime.get_body(preferencelist=('plain',)).get_content().strip(), message.body)
        images = [part for part in mime.walk() if part.get_content_type() == 'image/png']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['Content-ID'], '<pabasa-live-summary-logo>')
        self.assertEqual(images[0].get_content_disposition(), 'inline')
        self.assertIn('cid:pabasa-live-summary-logo', mime.get_body(preferencelist=('html',)).get_content())

    @patch('pabasa_app.live_assessment_email._logo_bytes', return_value=None)
    def test_missing_logo_asset_uses_existing_first_party_url_and_alt(self, _logo):
        html = render_summary_email(*sample_session())
        self.assertNotIn('cid:', html)
        self.assertIn('alt="PABASA"', html)
        self.assertIn('/pabasa_app/images/pabasa_logo.png', html)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LiveSummaryDeliveryTests(TestCase):
    def test_finalizer_keeps_post_commit_teacher_only_single_delivery_and_plain_summary(self):
        from .models import LiveAssessmentSession, Material, User
        from .views import _end_live_assessment_session
        teacher = User.objects.create(custom_id='EMAIL-TEACHER', role='teacher', first_name='Sample',
            last_name='Teacher', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email='summary-teacher@example.com', password_hash='unused')
        learner = User.objects.create(custom_id='EMAIL-LEARNER', role='student', first_name='Sample',
            last_name='Learner', sex='female', birth_month=1, birth_day=1, birth_year=2015,
            email='summary-learner@example.com', password_hash='unused')
        # This fixture uses the legacy non-CRLA completion branch to isolate
        # delivery; official CRLA finalization is covered by its existing suite.
        material = Material.objects.create(title='Participation Test', item_type='word',
            teacher=teacher, code='EMAIL-SUMMARY-MATERIAL')
        session = LiveAssessmentSession.objects.create(id='EMAIL-SUMMARY-SESSION', teacher=teacher,
            material=material, student_ids=[learner.pk], student_states={str(learner.pk): {'status': 'completed'}},
            status='started')
        callbacks = []

        def capture(callback, *, label):
            self.assertEqual(label, 'live_session_summary')
            callbacks.append(callback)

        with patch('pabasa_app.views.queue_after_commit', side_effect=capture):
            ended = _end_live_assessment_session(session)
            self.assertEqual(len(callbacks), 1)
            self.assertEqual(len(mail.outbox), 0)
            callbacks[0]()
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, [teacher.email])
            self.assertIn('Total selected students: 1', mail.outbox[0].body)
            self.assertIn('Completed: 1', mail.outbox[0].body)
            self.assertIn('Missed: 0', mail.outbox[0].body)
            self.assertIn('- Sample Learner', mail.outbox[0].body)
            self.assertIn('Session Details', mail.outbox[0].alternatives[0].content)
            _end_live_assessment_session(ended)
            self.assertEqual(len(callbacks), 1, 'Repeated End must not queue a duplicate email.')
