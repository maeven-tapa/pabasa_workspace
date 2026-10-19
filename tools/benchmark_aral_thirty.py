"""Opt-in ARAL Sessions 1–15 saving probe for an isolated Cloud Run Job.

Uses synthetic checkpoints, generated recording audio and disposable records.
This does not establish full speech-recognition or scoring correctness.
Never prints identities, cookies,
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
        'scope':'30 distinct synthetic students and six teachers/classes. Sessions 1-15 checkpoint persistence, reload, malformed requests, stale saves, and synthetic recording upload/playback/review. Seeded oral/prerequisite checkpoints; not a full microphone or scoring benchmark.'}
    print('PABASA_ARAL_START '+json.dumps({'test_id':rid,'clients':COUNT}),flush=True)
    users,keys,clients,rows=[],[],[],[]
    school=calendar=section=None
    csrf=secrets.token_hex(32)
    password=secrets.token_urlsafe(24)
    hashed=make_password(password)
    pcm=base64.b64decode(os.environ['PABASA_BENCHMARK_PCM_BASE64'],validate=True)
    assert 16000<len(pcm)<640000
    import av
    recorded=io.BytesIO()
    with av.open(recorded,'w',format='webm') as container:
        encoder=container.add_stream('libopus',rate=16000)
        encoder.layout='mono';encoder.codec_context.format='s16'
        frame=av.AudioFrame(format='s16',layout='mono',samples=len(pcm)//2)
        frame.sample_rate=16000;frame.planes[0].update(pcm)
        for packet in encoder.encode(frame):container.mux(packet)
        for packet in encoder.encode(None):container.mux(packet)
    webm=recorded.getvalue()
    expected_audio_hash=hashlib.sha256(webm).hexdigest()

    def multipart(fields,filename):
        boundary='PabasaPrescribedGeneratedAudio'
        body=b''.join((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode() for key,value in fields.items())
        body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="{filename}"\r\nContent-Type: audio/webm\r\n\r\n').encode()+webm+(f'\r\n--{boundary}--\r\n').encode()
        return body,'multipart/form-data; boundary='+boundary

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
                'X-CSRFToken':csrf,'Accept':'application/json','Origin':'https://'+HOST,'Referer':'https://'+HOST+'/',
                'User-Agent':report['user_agent'],'Content-Type':content_type,
                'X-Pabasa-STT-Provider':'google','X-Pabasa-STT-Model':'chirp_3'}
            c['connection'].request('POST' if payload is not None else 'GET',route,
                body=payload if isinstance(payload,bytes) else json.dumps(payload) if payload is not None else None,headers=headers)
            response=c['connection'].getresponse();status=response.status;raw=response.read()
            from http.cookies import SimpleCookie
            cookies=SimpleCookie()
            for header,value in response.getheaders():
                if header.lower()=='set-cookie':cookies.load(value)
            if settings.SESSION_COOKIE_NAME in cookies:
                updated_key=cookies[settings.SESSION_COOKIE_NAME].value
                if updated_key:c['cookie']=updated_key;keys.append(updated_key)
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
            admin=make_user('a','admin')
            teachers=[make_user('t'+str(i),'teacher') for i in range(6)]
            sections=[Section.objects.create(school=school,school_calendar=calendar,teacher=teacher,
                class_code='P30'+rid+str(i),class_name='Synthetic five-student class',subject='English',grade_level='Grade 2') for i,teacher in enumerate(teachers)]
            material=__import__('pabasa_app.models',fromlist=['Material']).Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
            assert material,'Official material unavailable'
            students=[]
            order=_prescribed_activity_order()
            for index in range(COUNT):
                teacher=teachers[index//5];section=sections[index//5]
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
            teacher_clients=[client(teachers[index//5]) for index in range(COUNT)]
            report['teachers']=len(teachers);report['classes']=len(sections)
        connections.close_all()
        report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        recovery_only=os.environ.get('PABASA_ARAL_RECOVERY_ONLY')=='1'
        fixtures=[] if recovery_only else json.loads(os.environ['PABASA_ARAL_FIXTURES_JSON'])['activities']
        session_smoke=os.environ.get('PABASA_ARAL_SESSION_SMOKE')=='1'
        if session_smoke and not recovery_only:
            sampled={}
            for case in fixtures:
                prior=sampled.get(case['session'])
                if prior is None or ((prior['payload'].get('reset') or prior['payload'].get('action')=='restart')
                                     and not case['payload'].get('reset') and case['payload'].get('action')!='restart'):
                    sampled[case['session']]=case
            fixtures=[sampled[key] for key in sorted(sampled)]
            report['scope']='30 synthetic students and six teachers: one checkpoint per active session (2–15), seven legacy chart completions, Session 1 recording/review and expired-login recovery. Public-routing smoke test; not the full 85-activity matrix.'
        report['session_smoke']=session_smoke
        report['recovery_only']=recovery_only
        if recovery_only:report['scope']='30 synthetic students and six teachers: recording, private playback, cross-class denial, review and expired-login recovery only; no activity checkpoint matrix.'
        report['activities']=[];report['saved_checkpoints']=0;report['reloads']=0
        report['legacy_completed']=0
        seed_state={'fluency_classifications':{str(i):'GREEN' for i in range(30)},'classification_sources':{str(i):'teacher' for i in range(30)}}
        def restore_prerequisite(key):
            StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key).update(
                state=seed_state,activity_completed=True,current_index=1,completed_items=1,correct_items=0,total_items=1)
            connections.close_all()
        def seed(key,before):
            q=StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key)
            if before:q.update(**before)
            else:q.delete()
            connections.close_all()
        def canonical(value):
            if isinstance(value,dict):return {k:canonical(v) for k,v in value.items() if k not in ('choice_tokens','pending_reading_nonce','picture_order','target_word','started_at','elapsed_seconds')}
            if isinstance(value,list):return [canonical(v) for v in value]
            return value
        with cf.ThreadPoolExecutor(max_workers=COUNT) as pool:
            admin_client=client(admin)
            wave(pool,[admin_client],'admin_calendar_during_setup',reverse('admin_school_calendar'))
            wave(pool,students,'dashboard','/dashboard/assessment/')
            legacy_keys=[] if recovery_only else ['lesson-2-gawain-1','lesson-3-gawain-1','lesson-3-gawain-2','lesson-4-gawain-1','lesson-5-gawain-1','lesson-6-gawain-1','lesson-7-gawain-1']
            for key in legacy_keys:
                StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key).update(
                    state={},current_index=0,completed_items=0,correct_items=0,total_items=3,activity_completed=False)
                connections.close_all()
                route=reverse('lesson_3_activity_progress')
                base={'activity_key':key,'total_items':3}
                wave(pool,students,'legacy_checkpoint',route,{**base,'current_index':1,'completed_items':1,'correct_items':1})
                wave(pool,students,'legacy_finish',route,{**base,'current_index':3,'completed_items':3,'correct_items':3,'activity_completed':True})
                outcomes=wave(pool,students,'legacy_stale_save',route,{**base,'current_index':1,'completed_items':1,'correct_items':1})
                assert all(x['progress']['activity_completed'] and x['progress']['current_index']==3 for x in outcomes)
                report['legacy_completed']+=COUNT;restore_prerequisite(key)
            wave(pool,students,'legacy_invalid_json',reverse('lesson_3_activity_progress'),b'[]',expected=400)
            for case in fixtures:
                key=case['key'];seed(key,case['before'])
                page=reverse('prescribed_activity_page',kwargs={'activity_key':key})
                wave(pool,students,'activity_start',page)
                wave(pool,students,'checkpoint_save',case['path'],case['payload'])
                fields=list(case['after'])
                stored=list(StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key).order_by('student_id').values(*fields))
                mismatches=[v for v in stored if canonical(v)!=canonical(case['after'])]
                connections.close_all()
                if len(stored)!=COUNT or mismatches:
                    report['mismatch']={'key':key,'rows':len(stored),'mismatches':len(mismatches),
                        'fields':sorted({f for v in mismatches for f in fields if canonical(v.get(f))!=canonical(case['after'].get(f))})}
                    raise AssertionError('Checkpoint state differed from its validated fixture')
                # Close every connection to exercise persistence across reconnect.
                for c in students:c['connection'].close()
                # Completed dedicated activities may redirect to the dashboard.
                expected=302 if key=='lesson9-gawain3' and case['after']['activity_completed'] else 200
                wave(pool,students,'activity_reload',page,expected=expected)
                restored=list(StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key).order_by('student_id').values(*fields))
                connections.close_all()
                assert [canonical(v) for v in restored]==[canonical(v) for v in stored],'Reload changed a saved checkpoint'
                assert [v['state'].get('target_word') for v in restored]==[v['state'].get('target_word') for v in stored],'Reload changed the selected reading target'
                report['reloads']+=COUNT;report['saved_checkpoints']+=COUNT
                wave(pool,students,'invalid_json',case['path'],b'[]',expected=400)
                report['activities'].append({'key':key,'session':case['session'],
                    'kind':'restart' if case['payload'].get('reset') or case['payload'].get('action')=='restart' else 'checkpoint',
                    'students_saved':COUNT,'students_reloaded':COUNT})
                restore_prerequisite(key)
                print('PABASA_ARAL_ACTIVITY '+json.dumps(report['activities'][-1]),flush=True)
            # The first session's teacher-reviewed recording uses generated
            # audio; the video-completion precondition is a synthetic fixture.
            key='lesson-1-gawain-1';seed(key,None)
            wave(pool,students,'session1_page',reverse('lesson_1_gawain_1_page'))
            uploads=wave(pool,students,'session1_upload',reverse('lesson_1_gawain_1_submit'),lambda c:multipart(
                {'duration_seconds':'2','video_completed':'true'},f'p30-{rid}-{c["user_id"]}-lesson1.webm'))
            for c,t,d in zip(students,teacher_clients,uploads):t['submission_id']=d['submission_id']
            for index,t in enumerate(teacher_clients):t['foreign_submission_id']=uploads[(index+5)%COUNT]['submission_id']
            wave(pool,students,'session1_upload_replay',reverse('lesson_1_gawain_1_submit'),lambda c:multipart(
                {'duration_seconds':'2','video_completed':'true'},f'p30-{rid}-{c["user_id"]}-replay.webm'))
            wave(pool,teacher_clients,'playback',lambda c:reverse('teacher_lesson_1_gawain_1_audio',args=[c['submission_id']]))
            wave(pool,teacher_clients,'foreign_recording_denied',lambda c:reverse('teacher_lesson_1_gawain_1_audio',args=[c['foreign_submission_id']]),expected=403)
            wave(pool,teacher_clients,'session1_teacher_review',reverse('teacher_lesson_1_gawain_1_review_action'),lambda c:{'submission_id':c['submission_id'],'action':'checked'})
            wave(pool,students,'session1_reload',reverse('lesson_1_gawain_1_page'))
            report['session1_recordings_completed']=StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key,activity_completed=True).count()
            assert report['session1_recordings_completed']==COUNT
            Session.objects.filter(session_key__in=[c['cookie'] for c in students]).delete()
            connections.close_all()
            wave(pool,students,'expired_save',reverse('lesson_3_activity_progress'),{'activity_key':'lesson-2-gawain-1','total_items':3,'current_index':1,'completed_items':1},expected=401)
            from urllib.parse import urlencode
            wave(pool,students,'login_recovery','/api/login/',lambda c:urlencode({'custom_id':c['custom_id'],'password':password}).encode(),content_type='application/x-www-form-urlencoded')
            wave(pool,students,'authenticated_reload',reverse('lesson_1_gawain_1_page'))
            wave(pool,[admin_client],'admin_calendar_after_assessment',reverse('admin_school_calendar'))
            report['expired_logins_recovered']=COUNT
            report['sessions_covered']=sorted({case['session'] for case in fixtures}|{1})
            report['all_thirty_preserved']=bool(fixtures) and report['saved_checkpoints']==len(fixtures)*COUNT and report['reloads']==len(fixtures)*COUNT
            if not recovery_only:assert report['all_thirty_preserved'] and report['legacy_completed']==210
            else:report['recovery_only_complete']=report['session1_recordings_completed']==report['expired_logins_recovered']==COUNT
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
        if school:Section.objects.filter(school=school).delete()
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
