"""Bounded, opt-in live CRLA benchmark using 20 or 50 disposable students.

Run only in a purpose-created Cloud Run diagnostic job with the deployed image,
identity and database configuration. Never prints cookies, names or response
bodies. Does not alter service settings, existing accounts or official material.
No audio/provider calls: measures HTTP polling, state writes and finalization.
"""
import concurrent.futures as cf
import datetime as dt
import http.client
import json
import logging
import math
import os
import secrets
import statistics
import sys
import threading
import time
import uuid

CLIENT_COUNT = int(os.environ.get('PABASA_AUTHORIZED_CAPACITY_TEST', '20'))
CLASS_COUNT = CLIENT_COUNT // 10
HOST = 'tupcpabasa.app'
MARKER = 'PABASA_LIVE_CRLA_' + ('FIFTY ' if CLIENT_COUNT == 50 else 'TWENTY ')


def stats(rows):
    values = sorted(row['ms'] for row in rows)
    return {'count': len(rows), 'mean_ms': round(statistics.mean(values), 2),
            'p95_ms': round(values[math.ceil(.95 * len(values)) - 1], 2),
            'max_ms': round(max(values), 2), 'failures': sum(not r['ok'] for r in rows),
            'statuses': {str(s): sum(r['status'] == s for r in rows)
                         for s in sorted({r['status'] for r in rows})}}


def run():
    if not os.environ.get('CLOUD_RUN_EXECUTION') or (CLIENT_COUNT not in (20, 50) or os.environ.get('PABASA_AUTHORIZED_CAPACITY_TEST') != str(CLIENT_COUNT)):
        raise RuntimeError('Requires an explicitly authorized disposable 20- or 50-client diagnostic job.')
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.core.management import call_command
    from django.db import connection, connections, transaction
    from django.utils import timezone
    from pabasa_app.models import (ActivityLog, Assessment, CalendarEvent, Enrollment, Notification,
        LiveAssessmentSession, Material, School, SchoolCalendar, Section, User)
    call_command('check_migration_readiness', require_recorded=True, verbosity=0)
    call_command('migrate', check=True, verbosity=0)
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise RuntimeError('Live probe requires the verified PostgreSQL configuration.')
    run_id = uuid.uuid4().hex[:12]
    report = {'test_id': run_id, 'clients': CLIENT_COUNT, 'teacher_clients': CLASS_COUNT,
        'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': f'{CLIENT_COUNT} distinct synthetic enrolled students in {CLASS_COUNT} 10-student live CRLA sessions; real public HTTPS; polling, state updates, completed synthetic snapshots, teacher End Session and post-end authentication. No speech recognition or browser microphone.',
        'user_agent': f'PABASA-authorized-live-crla-{CLIENT_COUNT}-' + run_id,
        'aborted': False, 'waves': []}
    keys, users, sections, live_ids, clients, rows = [], [], [], [], [], []
    school_id = None
    csrf = secrets.token_hex(32)
    source_material = Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
    material = None
    calendar = SchoolCalendar.objects.filter(is_active=True).order_by('-id').first()
    if source_material is None or calendar is None:
        raise RuntimeError('Required official CRLA material/current calendar unavailable.')

    def make_user(label, role):
        user = User.objects.create(custom_id=f'CAP-{run_id}-{label}', role=role,
            first_name='Synthetic', last_name='Capacity Test', middle_initial='', suffix='',
            sex='female', birth_month=1, birth_day=1, birth_year=2012,
            email=None, password_hash='!unusable-capacity-test', school_record_id=school_id)
        users.append(user.pk)
        return user

    def login(user, live_id):
        store = SessionStore()
        store.update({'user_id': user.pk, 'user_role': user.role, 'pabasa_benchmark':run_id})
        store.set_expiry(600)
        store.create()
        keys.append(store.session_key)
        client = {'user_id': user.pk, 'key': store.session_key, 'live_id':live_id,
                  'connection':http.client.HTTPSConnection(HOST, timeout=25)}
        clients.append(client)
        return client

    def request(client, operation, payload=None, barrier=None):
        if barrier: barrier.wait(timeout=30)
        start = time.perf_counter()
        status, ok, error = 0, False, None
        route = f'/api/live-assessment/session/{client["live_id"]}/'
        if operation in ('update', 'complete'): route += 'student-update/'
        if operation == 'end': route += 'action/'
        headers = {'Cookie': settings.SESSION_COOKIE_NAME + '=' + client['key'] + '; csrftoken=' + csrf,
            'User-Agent':report['user_agent'], 'X-Requested-With':'XMLHttpRequest',
            'Origin':'https://' + HOST, 'Referer':'https://' + HOST + '/',
            'X-CSRFToken':csrf, 'Content-Type':'application/json'}
        try:
            client['connection'].request('POST' if payload is not None else 'GET', route,
                body=json.dumps(payload) if payload is not None else None, headers=headers)
            response=client['connection'].getresponse()
            status=response.status
            data=json.loads(response.read())
            ok=status==200 and data.get('success') is True
            if operation=='post_end': ok=ok and data.get('session',{}).get('status')=='ended'
            if not ok: error='UnexpectedStatusOrContent'
        except Exception as exc:
            error=type(exc).__name__
            client['connection'].close()
            client['connection']=http.client.HTTPSConnection(HOST,timeout=25)
        return {'operation':operation,'ms':(time.perf_counter()-start)*1000,
                'status':status,'ok':ok,'error_type':error}

    def wave(pool, members, operation, payload=None):
        barrier=threading.Barrier(len(members))
        start=dt.datetime.now(dt.timezone.utc).isoformat()
        result=list(pool.map(lambda c:request(c,operation,payload,barrier),members))
        rows.extend(result)
        report['waves'].append({'operation':operation,'started_utc':start,**stats(result)})
        if any(not r['ok'] for r in result):
            report['aborted']=True
            raise RuntimeError('Benchmark wave failed; stopping before further load.')

    try:
        with transaction.atomic():
            school=School.objects.create(name='Synthetic capacity test '+run_id,code='CAP'+run_id)
            school_id=school.pk
            today=timezone.localdate()
            for event_type, first, last in (
                ('school_opening',today-dt.timedelta(days=2),today-dt.timedelta(days=2)),
                ('pre_assessment',today-dt.timedelta(days=1),today+dt.timedelta(days=1)),
                ('school_closing',today+dt.timedelta(days=20),today+dt.timedelta(days=20))):
                CalendarEvent.objects.create(school_calendar=calendar,school=school,
                    scope=CalendarEvent.SCOPE_SCHOOL,term=1,title='Synthetic '+event_type,
                    event_type=event_type,start_date=first,end_date=last)
            teachers=[]
            students=[]
            for group in range(CLASS_COUNT):
                teacher=make_user(f'T{group}','teacher')
                section=Section.objects.create(school=school,school_calendar=calendar,teacher=teacher,
                    class_code=f'CAP{run_id}{group}',class_name='Synthetic Capacity Class',
                    subject='Reading',assessment_week_enabled=True)
                sections.append(section.pk)
                if material is None:
                    root=Assessment.objects.create(teacher=teacher,title='Synthetic CRLA Capacity '+run_id,
                        code='CAPROOT'+run_id,assessment_type=source_material.item_type,status='published',
                        is_system_owned=True,system_assessment_key='bosy_crla_pretest',
                        system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1)
                    material=Material.objects.create(assessment=root,teacher=teacher,
                        title='Synthetic CRLA Capacity '+run_id,code='CAPMAT'+run_id,
                        system_assessment_key='capacity_'+run_id,is_system_owned=True,
                        is_official_reading=True,assessment_kind='crla',assessment_set='crla',
                        system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1,
                        item_type=source_material.item_type,language=source_material.language,
                        content_json=source_material.content_json,content_text=source_material.content_text,
                        prompt_text=source_material.prompt_text,type='assessment',is_active=True,status='published')
                material.assigned_sections.add(section)
                members=[]
                for index in range(10):
                    student=make_user(f'S{group*10+index}','student')
                    section.add_student(student)
                    members.append(student)
                live_id=f'capacity-{run_id}-{group}'
                LiveAssessmentSession.objects.create(id=live_id,teacher=teacher,section=section,
                    material=material,status='started',start_at=timezone.now(),
                    student_ids=[s.pk for s in members],student_count=10,batch_size=10,
                    current_batch=1,total_batches=1,batch_assignments={str(s.pk):1 for s in members},
                    student_states={str(s.pk):{'status':'reading','progress':0,'connection_status':'connected'} for s in members})
                live_ids.append(live_id)
                teachers.append(login(teacher,live_id))
                students.extend(login(s,live_id) for s in members)
        report['enrolled_students']=Enrollment.objects.filter(student_id__in=users, status='active',is_active=True).count()
        assert len(students)==report['enrolled_students']==CLIENT_COUNT
        with connection.cursor() as cursor:
            cursor.execute('SHOW max_connections')
            report['database_max_connections']=int(cursor.fetchone()[0])
        connections.close_all()
        report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        # Every independent student participates in each synchronized wave.
        with cf.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
            wave(pool,students,'poll')
            for round_index in range(3):
                wave(pool,students,'update',{'status':'reading','progress':(round_index+1)/10,
                    'elapsed_seconds':round_index*2,'recovery_state':{'stage':'words','task1_score':0}})
                wave(pool,students,'poll')
                time.sleep(2)
            evidence={'stage':'completed','temporary_completed':True,'task1_score':0,
                'task2_type':'Task 2L / Rhymes','task2_rhymes_score':0,
                'part1_total_score':0,'learner_experience_rating':3}
            wave(pool,students,'complete',{'status':'completed','progress':1,'elapsed_seconds':6,'recovery_state':evidence})
            # Student polls remain active while all class teachers finalize.
            with cf.ThreadPoolExecutor(max_workers=CLASS_COUNT) as teacher_pool:
                teacher_barrier=threading.Barrier(CLASS_COUNT)
                pending=[teacher_pool.submit(request,t,'end',{'action':'end'},teacher_barrier) for t in teachers]
                wave(pool,students,'poll')
                end_rows=[f.result() for f in pending]
                rows.extend(end_rows)
                report['end_session']=stats(end_rows)
                if any(not r['ok'] for r in end_rows):
                    report['aborted']=True
                    raise RuntimeError('Teacher End Session failed.')
            wave(pool,students,'post_end')
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        report['completed_results']=Assessment.objects.filter(student_id__in=users,material=material,attempt_status='completed').count()
        report['ended_sessions']=LiveAssessmentSession.objects.filter(pk__in=live_ids,status='ended').count()
        report['student_logins_preserved']=Session.objects.filter(session_key__in=[c['key'] for c in students]).count()
        assert report['completed_results']==report['student_logins_preserved']==CLIENT_COUNT
        assert report['ended_sessions']==CLASS_COUNT
    except Exception as exc:
        report['aborted']=True
        report['error_type']=type(exc).__name__
    finally:
        report.setdefault('http_finished_utc',dt.datetime.now(dt.timezone.utc).isoformat())
        for client in clients: client['connection'].close()
        connections.close_all()
        report['temporary_sessions_created']=len(keys)
        report['temporary_sessions_deleted']=Session.objects.filter(session_key__in=keys).delete()[0]
        # Exact ids belong exclusively to this run, never a broad prefix deletion.
        report['temporary_notifications_deleted']=Notification.objects.filter(created_by_id__in=users).delete()[0]
        report['temporary_activity_logs_deleted']=ActivityLog.objects.filter(actor_id__in=users).delete()[0]
        User.objects.filter(pk__in=users).delete()
        Section.objects.filter(pk__in=sections).delete()
        if school_id is not None:
            CalendarEvent.objects.filter(school_id=school_id).delete()
            School.objects.filter(pk=school_id).delete()
        report['cleanup_remaining_users']=User.objects.filter(pk__in=users).count()
        report['cleanup_remaining_live_sessions']=LiveAssessmentSession.objects.filter(pk__in=live_ids).count()
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        report['operations']={name:stats([r for r in rows if r['operation']==name]) for name in sorted({r['operation'] for r in rows})}
        report['total_requests']=len(rows)
        report['failures']=sum(not r['ok'] for r in rows)
        print(MARKER+json.dumps(report),flush=True)
    if report['aborted']: raise SystemExit(1)


if __name__=='__main__':
    run()
