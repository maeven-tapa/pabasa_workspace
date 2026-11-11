"""Opt-in authenticated release check with one disposable synthetic student.

Run in a same-image Cloud Run Job. Never prints cookies or student records.
Exercises real HTTPS against the staged revision or the authorized public site.
No speech calls, existing account changes, or capacity claims.
"""
import argparse
import http.client
import json
import logging
import os
import secrets
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    args = parser.parse_args()
    if not os.environ.get('CLOUD_RUN_EXECUTION'):
        raise RuntimeError('Requires a purpose-created Cloud Run verification job.')
    if args.host != 'tupcpabasa.app' and args.host != 'aralstatus---pabasa-workspace-deployment--trigger-7jqab7xtta-as.a.run.app':
        raise ValueError('Unexpected verification host.')
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.db import connections, transaction
    from django.utils import timezone
    from pabasa_app.models import (ActivityLog, Assessment, LiveAssessmentSession, Material,
        Notification, School, SchoolCalendar, Section, User)
    from pabasa_app.views import _calendar_current_term

    run_id = uuid.uuid4().hex[:10]
    report = {'run_id': run_id, 'host': args.host, 'checks': [], 'passed': False}
    users, keys = [], []
    school = section = material = root = live = None
    connection = http.client.HTTPSConnection(args.host, timeout=60)
    calendar = SchoolCalendar.objects.filter(is_active=True).order_by('-id').first()
    if calendar is None:
        raise RuntimeError('No active school calendar available.')
    term = _calendar_current_term(calendar)
    if term not in (1, 2, 3):
        raise RuntimeError('An active CRLA term is required for this release check.')
    phase = {1: 'pretest', 2: 'midtest', 3: 'posttest'}[term]
    key = {1: 'bosy_crla_pretest', 2: 'midline_crla_midtest', 3: 'eosy_crla_posttest'}[term]
    source = Material.objects.get(system_assessment_key=key)
    csrf = secrets.token_hex(32)
    cookie = None

    def request(path, payload=None):
        headers = {'Cookie': settings.SESSION_COOKIE_NAME + '=' + cookie + '; csrftoken=' + csrf,
            'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://' + args.host, 'Content-Type': 'application/json',
            'User-Agent': 'PABASA-aral-status-release-' + run_id}
        connection.request('POST' if payload is not None else 'GET', path,
            body=json.dumps(payload) if payload is not None else None, headers=headers)
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError('Verification request returned HTTP ' + str(response.status))
        value = json.loads(body)
        if not value.get('success'):
            raise RuntimeError('Verification response was not successful.')
        return value

    try:
        with transaction.atomic():
            school = School.objects.create(name='Synthetic ARAL release ' + run_id, code='AR' + run_id)
            def user(label, role):
                value = User.objects.create(custom_id='AR-' + run_id + '-' + label,
                    role=role, first_name='Synthetic', last_name='Release Check',
                    sex='female', birth_month=1, birth_day=1, birth_year=2012,
                    password_hash='!unusable-release-check', school_record=school)
                users.append(value.pk)
                return value
            teacher, student = user('T', 'teacher'), user('S', 'student')
            section = Section.objects.create(school=school, school_calendar=calendar,
                teacher=teacher, class_code='AR' + run_id, class_name='Synthetic release check',
                subject='Reading', assessment_week_enabled=True)
            section.add_student(student)
            root = Assessment.objects.create(teacher=teacher, section=section,
                title='Synthetic release CRLA', code='ARROOT' + run_id, assessment_type='paragraph',
                is_system_owned=True, system_assessment_phase=phase, official_term=term)
            material = Material.objects.create(assessment=root, teacher=teacher,
                title='Synthetic release CRLA', code='ARMAT' + run_id,
                system_assessment_key='aral_release_' + run_id, is_system_owned=True,
                is_official_reading=True, assessment_kind='crla', assessment_set='crla',
                system_assessment_phase=phase, official_term=term, item_type=source.item_type,
                content_json=source.content_json, content_text=source.content_text,
                prompt_text=source.prompt_text, language=source.language,
                type='assessment', status='published', section=section)
            live = LiveAssessmentSession.objects.create(id='aral-release-' + run_id,
                teacher=teacher, section=section, material=material, student_ids=[student.pk],
                student_count=1, status='started', start_at=timezone.now(),
                batch_assignments={str(student.pk): 1},
                student_states={str(student.pk): {'status': 'reading', 'recovery_state': {'stage': 'words'}}})
            store = SessionStore()
            store.update({'user_id': teacher.pk, 'user_role': 'teacher', 'aral_release_check': run_id})
            store.set_expiry(600)
            store.create()
            cookie = store.session_key
            keys.append(cookie)
        path = f'/dashboard/teacher/students-api/?sync=directory&section_id={section.pk}&term={term}&term_mode=manual'
        for status, state in [
            ('in_progress', {'status': 'reading', 'recovery_state': {'stage': 'words'}}),
            ('saved', {'status': 'reading', 'participation_status': 'saved', 'recovery_state': {'stage': 'words'}}),
            ('in_progress', {'status': 'reading', 'recovery_state': {'stage': 'words'}}),
            ('completed', {'status': 'completed', 'progress': 1, 'elapsed_seconds': 6,
                'recovery_state': {'stage': 'completed', 'temporary_completed': True,
                    'task1_score': 0, 'task2_type': 'Task 2L / Rhymes', 'task2_rhymes_score': 0,
                    'part1_total_score': 0, 'learner_experience_rating': 3}}),
        ]:
            LiveAssessmentSession.objects.filter(pk=live.pk).update(student_states={str(student.pk): state})
            data = request(path)
            rows = data['students']
            assert len(rows) == 1 and rows[0]['id'] == student.pk
            assert rows[0]['crla_progress']['status'] == status
            assert rows[0]['crla_result'] is None and not rows[0]['has_completed_assessment']
            assert not Assessment.objects.filter(student=student).exists()
            report['checks'].append(status)
        request(f'/api/live-assessment/session/{live.pk}/action/', {'action': 'end'})
        row = request(path)['students'][0]
        assert row['crla_progress'] is None and row['crla_result'] is not None
        assert row['reading_level'] == 'Low Emerging Reader'
        assert Assessment.objects.filter(student=student, attempt_status='completed').count() == 1
        report['checks'].append('official_result_after_end')
        report['passed'] = True
    finally:
        connection.close()
        connections.close_all()
        Session.objects.filter(session_key__in=keys).delete()
        Notification.objects.filter(created_by_id__in=users).delete()
        ActivityLog.objects.filter(actor_id__in=users).delete()
        if live:
            LiveAssessmentSession.objects.filter(pk=live.pk).delete()
        Assessment.objects.filter(student_id__in=users).delete()
        if material:
            Material.objects.filter(pk=material.pk).delete()
        if root:
            Assessment.objects.filter(pk=root.pk).delete()
        User.objects.filter(pk__in=users).delete()
        if section:
            Section.objects.filter(pk=section.pk).delete()
        if school:
            School.objects.filter(pk=school.pk).delete()
        report['remaining_synthetic_users'] = User.objects.filter(pk__in=users).count()
        report['remaining_temporary_sessions'] = Session.objects.filter(session_key__in=keys).count()
        print('PABASA_ARAL_RELEASE ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
