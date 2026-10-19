"""Opt-in 30-account prescribed-material probe for an isolated Cloud Run Job.

Uses generated speech and disposable records. Never prints identities, cookies,
audio, transcripts, request bodies or private response bodies. The job must mount
the same private media storage as the target revision for exact-file cleanup.
"""
import asyncio
import base64
import concurrent.futures as cf
import datetime as dt
import hashlib
import http.client
import io
import json
import logging
import math
import os
import re
import secrets
import statistics
import sys
import threading
import time
import uuid

COUNT=30
HOST=os.environ.get('PABASA_BENCHMARK_HOST','tupcpabasa.app')
KEY='lesson-27-gawain-1'


def stats(rows):
    values=sorted(r['ms'] for r in rows)
    return {'count':len(rows),'mean_ms':round(statistics.mean(values),2),
        'p95_ms':round(values[math.ceil(.95*len(values))-1],2),'max_ms':round(max(values),2),
        'failures':sum(not r['ok'] for r in rows),
        'statuses':{str(s):sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})}}


def run():
    if not os.environ.get('CLOUD_RUN_EXECUTION') or os.environ.get('PABASA_AUTHORIZED_ARAL_TEST')!='30':
        raise RuntimeError('Requires an explicitly authorized 30-client diagnostic job.')
    if os.environ.get('DJANGO_MEDIA_ROOT')!='/app/media':
        raise RuntimeError('Require the revision shared-media mount for exact test file cleanup.')
    sys.path.insert(0,'/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.db import connection,connections,transaction
    from django.core.management import call_command
    from django.contrib.auth.hashers import make_password
    from django.urls import reverse
    from pabasa_app.models import (ActivityLog,Assessment,CalendarEvent,Enrollment,Notification,
        PrescribedReadingAttempt,School,SchoolCalendar,Section,StudentActivityProgress,
        StudentActivityRecordingSubmission,User)
    from pabasa_app.views import _current_learning_context,_prescribed_activity_order,prescribed_activity
    call_command('check_migration_readiness',require_recorded=True,verbosity=0)
    call_command('migrate',check=True,verbosity=0)
    rid=uuid.uuid4().hex[:12]
    report={'test_id':rid,'clients':COUNT,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'user_agent':'PABASA-authorized-aral-thirty-'+rid,'waves':[],'aborted':False,
        'scope':'30 isolated synthetic students, overlapping workbook revisions and legacy completion/stale saves from two tabs. Synthetic prerequisite states; no speech or recordings.'}
    print('PABASA_ARAL_START '+json.dumps({'test_id':rid,'clients':COUNT}),flush=True)
    users,keys,clients,rows=[],[],[],[]
    school=calendar=section=None
    csrf=secrets.token_hex(32)
    password=secrets.token_urlsafe(24)
    hashed=make_password(password)
    def client(user):
        session=SessionStore();session.update({'user_id':user.pk,'user_role':user.role,'pabasa_aral_benchmark':rid})
        session.set_expiry(1200);session.create();keys.append(session.session_key)
        c={'user_id':user.pk,'custom_id':user.custom_id,'cookie':session.session_key,'connection':http.client.HTTPSConnection(HOST,timeout=120)}
        clients.append(c);return c

    def request(c,operation,route,payload=None,expected=200,content_type='application/json',barrier=None):
        if barrier:barrier.wait(timeout=60)
        start=time.perf_counter();status=0;data={};ok=False;error=None
        try:
            headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+c['cookie']+'; csrftoken='+csrf,
                'X-CSRFToken':csrf,'Origin':'https://'+HOST,'Referer':'https://'+HOST+'/',
                'User-Agent':report['user_agent'],'Content-Type':content_type,
                'X-Pabasa-STT-Provider':'google','X-Pabasa-STT-Model':'chirp_3'}
            c['connection'].request('POST' if payload is not None else 'GET',route,
                body=payload if isinstance(payload,bytes) else json.dumps(payload) if payload is not None else None,headers=headers)
            response=c['connection'].getresponse();status=response.status;raw=response.read()
            if 'json' in response.getheader('Content-Type',''):data=json.loads(raw)
            ok=status==expected and (expected!=200 or data.get('success',True) is True)
            if operation=='playback':ok=ok and hashlib.sha256(raw).hexdigest()==expected_audio_hash
            if not ok:error='UnexpectedStatusOrContent'
        except Exception as exc:
            error=type(exc).__name__;c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=120)
        row={'operation':operation,'status':status,'ok':ok,'ms':(time.perf_counter()-start)*1000,'error_type':error}
        rows.append(row)
        return row,data

    def wave(pool,members,operation,route,payload=None,expected=200,content_type='application/json'):
        barrier=threading.Barrier(len(members))
        def one(c):
            target=route(c) if callable(route) else route
            body=payload(c) if callable(payload) else payload
            mime=content_type
            if isinstance(body,tuple):body,mime=body
            return request(c,operation,target,body,expected,mime,barrier)
        result=list(pool.map(one,members));summary={'operation':operation,**stats([r for r,d in result])}
        report['waves'].append(summary);print('PABASA_ARAL_WAVE '+json.dumps(summary),flush=True)
        assert all(r['ok'] for r,d in result),'A benchmark wave failed; stop before further load'
        return [data for row,data in result]

    def make_user(label,role):
        u=User.objects.create(custom_id='P30-'+rid+'-'+label,role=role,first_name='Synthetic',last_name='Capacity',
            middle_initial='',suffix='',sex='female',birth_month=1,birth_day=1,birth_year=2012,
            email=None,password_hash=hashed,school_record=school,school_calendar=calendar)
        users.append(u.pk);return u

    try:
        with transaction.atomic():
            school=School.objects.create(name='Synthetic prescribed '+rid,code='P30'+rid)
            # Admin calendar pages parse every school_year as YYYY-YYYY.
            # Keep disposable calendars valid and older than real school years.
            existing_years=set(SchoolCalendar.objects.values_list('school_year',flat=True))
            available_years=[year for year in range(1000,1900) if f'{year}-{year+1}' not in existing_years]
            assert available_years,'No isolated historical school year is available'
            year=secrets.choice(available_years)
            calendar=SchoolCalendar.objects.create(school_year=f'{year}-{year+1}',current_term=1,is_active=False)
            from pabasa_app.system_clock import today
            day=today()
            for kind,when in [('school_opening',day-dt.timedelta(days=2)),('school_closing',day+dt.timedelta(days=2))]:
                CalendarEvent.objects.create(school_calendar=calendar,school=school,scope=CalendarEvent.SCOPE_SCHOOL,
                    term=1,title='Synthetic '+kind,event_type=kind,start_date=when,end_date=when)
            teacher=make_user('t','teacher')
            section=Section.objects.create(school=school,school_calendar=calendar,teacher=teacher,
                class_code='P30'+rid,class_name='Synthetic thirty-student class',subject='English',grade_level='Grade 2')
            material=__import__('pabasa_app.models',fromlist=['Material']).Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
            assert material,'Official material unavailable'
            students=[]
            order=_prescribed_activity_order()
            for index in range(COUNT):
                student=make_user(str(index),'student');section.add_student(student)
                enrollment=Enrollment.objects.get(student=student,section=section)
                Assessment.objects.create(teacher=teacher,student=student,enrollment=enrollment,material=material,
                    title='Synthetic prerequisite '+rid,code='P30R'+rid+str(index),assessment_type='word',
                    system_assessment_phase='pretest',system_assessment_key='bosy_crla_pretest',official_term=1,
                    attempt_status='completed',completed_at=__import__('django.utils.timezone',fromlist=['make_aware']).make_aware(dt.datetime.combine(day,dt.time(12))),
                    crla_classification='Developing Reader',classification='Developing Reader')
                # Seed prerequisite fixtures only for these disposable students.
                # Never change the real calendar or global unlock setting.
                StudentActivityProgress.objects.bulk_create([StudentActivityProgress(student=student,school_calendar=calendar,
                    term=1,activity_key=key,activity_completed=True,current_index=1,completed_items=1,correct_items=0,total_items=1,
                    state={'fluency_classifications':{str(i):'GREEN' for i in range(22)},'classification_sources':{str(i):'teacher' for i in range(22)}})
                    for key in order])
                context=_current_learning_context(student)
                report['fixture_state']=context['state']
                assert context['state']=='ARAL_ACTIVE','Fixture did not satisfy normal lifecycle'
                students.append(client(student))
            teacher_clients=[client(teacher) for _ in range(COUNT)]
        connections.close_all()
        report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        from pabasa_app.prescribed_workbook import initial_s9_a1_state
        race_key='aral-s9-a1-family-drawing'
        route=reverse('prescribed_activity_progress',kwargs={'activity_key':race_key})
        report['races']=[]
        for round_index in range(3):
            StudentActivityProgress.objects.filter(student_id__in=users,activity_key=race_key).update(
                state=initial_s9_a1_state(),activity_completed=False,current_index=0,completed_items=0)
            connections.close_all()
            twins=[client(User.objects.get(pk=c['user_id'])) for c in students]
            connections.close_all()
            pairs=[c for pair in zip(students,twins) for c in pair]
            barrier=threading.Barrier(len(pairs))
            with cf.ThreadPoolExecutor(max_workers=60) as pool:
                outcomes=list(pool.map(lambda c:request(c,'overlapping_save',route,
                    {'action':'draft','revision':0,'draft':{'text':'Synthetic draft '+str(round_index),'strokes':[]}},
                    expected=200,barrier=barrier),pairs))
            counts=[sorted([outcomes[i*2][0]['status'],outcomes[i*2+1][0]['status']]) for i in range(COUNT)]
            for index,pair in enumerate(counts):
                for offset in (0,1):
                    outcomes[index*2+offset][0]['ok']=pair==[200,409]
                    outcomes[index*2+offset][0]['error_type']=None if pair==[200,409] else 'DuplicateRevisionAccepted'
            report['races'].append({'round':round_index,'correctly_conflicted':counts.count([200,409]),
                'both_accepted_same_revision':counts.count([200,200]),'statuses':dict(__import__('collections').Counter(str(o[0]['status']) for o in outcomes))})
            print('PABASA_ARAL_RACE '+json.dumps(report['races'][-1]),flush=True)
        report['legacy_races']=[]
        legacy_key='lesson-2-gawain-1'
        legacy_route=reverse('lesson_3_activity_progress')
        for round_index in range(3):
            StudentActivityProgress.objects.filter(student_id__in=users,activity_key=legacy_key).update(
                state={},activity_completed=False,current_index=0,completed_items=0,correct_items=0,total_items=3)
            connections.close_all()
            barrier=threading.Barrier(len(pairs))
            def legacy_one(pair):
                index,c=pair
                final=index%2==0;position=3 if final else 1
                return request(c,'overlapping_legacy_save',legacy_route,{'activity_key':legacy_key,
                    'total_items':3,'current_index':position,'completed_items':position,
                    'correct_items':position,'activity_completed':final},barrier=barrier)
            with cf.ThreadPoolExecutor(max_workers=60) as pool:outcomes=list(pool.map(legacy_one,enumerate(pairs)))
            complete=StudentActivityProgress.objects.filter(student_id__in=users,activity_key=legacy_key,
                activity_completed=True,current_index=3,completed_items=3).count()
            connections.close_all()
            report['legacy_races'].append({'round':round_index,'completions_preserved':complete,'expected':COUNT})
            assert complete==COUNT and all(row['ok'] for row,data in outcomes)
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    except Exception as exc:
        report['aborted']=True;report['error_type']=type(exc).__name__
        import traceback
        report['error_locations']=[{'file':os.path.basename(f.filename),'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
        print('PABASA_ARAL_ABORT '+json.dumps({'error_type':report['error_type'],'error_locations':report['error_locations']}),flush=True)
    finally:
        for c in clients:c['connection'].close()
        connections.close_all()
        names=set(StudentActivityRecordingSubmission.objects.filter(student_id__in=users).values_list('audio_file',flat=True))
        names.update(PrescribedReadingAttempt.objects.filter(student_id__in=users).values_list('audio_file',flat=True))
        assert all('p30-'+rid+'-' in name for name in names),'Refuse to clean an unowned media file'
        storage=StudentActivityRecordingSubmission._meta.get_field('audio_file').storage
        with cf.ThreadPoolExecutor(max_workers=4) as cleanup_pool:
            list(cleanup_pool.map(storage.delete,names))
            report['remaining_media']=sum(cleanup_pool.map(storage.exists,names))
        report['temporary_media_references_removed']=len(names)
        report['temporary_media_deleted']=sum(not name.endswith('-missing.webm') for name in names)
        Session.objects.filter(session_key__in=keys).delete()
        Notification.objects.filter(created_by_id__in=users).delete()
        ActivityLog.objects.filter(actor_id__in=users).delete()
        User.objects.filter(pk__in=users).delete()
        if section:Section.objects.filter(pk=section.pk).delete()
        if calendar:SchoolCalendar.objects.filter(pk=calendar.pk).delete()
        if school:School.objects.filter(pk=school.pk).delete()
        report['remaining_users']=User.objects.filter(pk__in=users).count()
        report['remaining_sessions']=Session.objects.filter(session_key__in=keys).count()
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        report['operations']={name:stats([r for r in rows if r['operation']==name]) for name in sorted({r['operation'] for r in rows})}
        report['stream_error_types']={name:sum(r['error_type']==name for r in rows if r['operation']=='stream') for name in sorted({r['error_type'] for r in rows if r['operation']=='stream' and r['error_type']})}
        report['total_requests']=len(rows);report['failures']=sum(not r['ok'] for r in rows)
        print('PABASA_ARAL_RESULT '+json.dumps(report),flush=True)
    if report['aborted']:raise SystemExit(1)


if __name__=='__main__':run()
