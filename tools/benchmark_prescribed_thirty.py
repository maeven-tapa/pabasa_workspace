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
    if not os.environ.get('CLOUD_RUN_EXECUTION') or os.environ.get('PABASA_AUTHORIZED_PRESCRIBED_TEST')!='30':
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
        'user_agent':'PABASA-authorized-prescribed-thirty-'+rid,'waves':[],'aborted':False,
        'scope':'30 distinct synthetic students, one teacher/class, isolated calendar and finalized CRLA eligibility. Generated speech, prescribed streaming and clips, four recordings each, teacher playback/review, completion, return pages and invalid-input recovery. No real student audio.'}
    print('PABASA_PRESCRIBED_START '+json.dumps({'test_id':rid,'clients':COUNT}),flush=True)
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
        session=SessionStore();session.update({'user_id':user.pk,'user_role':user.role,'pabasa_prescribed_benchmark':rid})
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
        report['waves'].append(summary);print('PABASA_PRESCRIBED_WAVE '+json.dumps(summary),flush=True)
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
            calendar=SchoolCalendar.objects.create(school_year='P30-'+rid,current_term=1,is_active=False)
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
        page=reverse('prescribed_activity_page',kwargs={'activity_key':KEY})
        progress=reverse('prescribed_activity_progress',kwargs={'activity_key':KEY})
        with cf.ThreadPoolExecutor(max_workers=COUNT) as pool:
            from urllib.parse import urlencode
            wave(pool,students,'login','/api/login/',lambda c:urlencode({'custom_id':c['custom_id'],'password':password}).encode(),content_type='application/x-www-form-urlencoded')
            wave(pool,students,'dashboard','/dashboard/assessment/')
            wave(pool,students,'activity_page',page)
            wave(pool,students,'reset',progress,{'reset':True})
            tickets=wave(pool,students,'ticket','/api/reading/prescribed-stream/start/',{'activity_key':KEY,'language':'English'})
            from websockets.asyncio.client import connect
            async def streams():
                ready=[];go=asyncio.Event()
                async def one(c,ticket):
                    start=time.perf_counter();final=None;error=None
                    try:
                        async with connect('wss://'+HOST+'/ws/reading/crla/',origin='https://'+HOST,
                            additional_headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+c['cookie'],'User-Agent':report['user_agent']},open_timeout=40) as ws:
                            await ws.send(json.dumps({'ticket':ticket}));message=json.loads(await asyncio.wait_for(ws.recv(),40))
                            assert message.get('type')=='ready';ready.append(True)
                            # Real microphones keep sending PCM while classmates
                            # connect. Silence maintains real-time provider input
                            # without allowing a result before all thirty join.
                            while not go.is_set():
                                await ws.send(bytes(6400))
                                try:await asyncio.wait_for(go.wait(),.2)
                                except asyncio.TimeoutError:pass
                            for at in range(0,len(pcm),6400):await ws.send(pcm[at:at+6400]);await asyncio.sleep(.2)
                            await ws.send('{"type":"finish"}')
                            while True:
                                message=json.loads(await asyncio.wait_for(ws.recv(),45))
                                if message.get('type')=='finished':
                                    assert message.get('has_speech'),'Generated stream contained no recognized speech'
                                    final=message['result_token'];break
                                if message.get('type')=='error':raise RuntimeError('Provider failure')
                    except Exception as exc:error=type(exc).__name__
                    rows.append({'operation':'stream','ms':(time.perf_counter()-start)*1000,'status':101 if final else 0,'ok':bool(final),'error_type':error})
                    return final
                tasks=[asyncio.create_task(one(c,t['ticket'])) for c,t in zip(students,tickets)]
                try:
                    until=time.monotonic()+40
                    while len(ready)<COUNT and time.monotonic()<until and not any(t.done() for t in tasks):await asyncio.sleep(.05)
                    assert len(ready)==COUNT,'All thirty prescribed streams must be ready together'
                    go.set();return await asyncio.gather(*tasks)
                finally:
                    go.set()
                    for task in tasks:
                        if not task.done():task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
            finals=asyncio.run(streams());assert all(finals)
            for c,token in zip(students,finals):c['final']=token
            common={'target_text':'The cat wore a hat,','language':'English','mode':'sentence','prescribed_activity_key':KEY}
            evaluations=wave(pool,students,'evaluate','/api/reading/transcribe/',lambda c:multipart({**common,
                'prescribed_stream_activity':KEY,'prescribed_stream_token':c['final']},'p30-'+rid+'-evaluation.webm'))
            assert all(d.get('complete') and d.get('correct_word_count')==5 for d in evaluations),'Generated verse recognition failed'
            wave(pool,students,'clip','/api/reading/transcribe/',multipart(common,'p30-'+rid+'-clip.webm'))
            wave(pool,students,'verse_progress',progress,{'action':'verse_read','item_index':0,'verse_index':0,'success':True})
            wave(pool,students,'resume',progress,{'action':'state_sync'})
            wave(pool,students,'return_page','/dashboard/assessment/')
            # A second activity covers file persistence, teacher review and finish.
            key='lesson-13-gawain-1';url=reverse('prescribed_activity_progress',kwargs={'activity_key':key})
            wave(pool,students,'recording_activity_page',reverse('prescribed_activity_page',kwargs={'activity_key':key}))
            wave(pool,students,'recording_reset',url,{'reset':True})
            for item in range(4):
                uploads=wave(pool,students,'recording','/api/lesson-13-gawain-1/recording/',lambda c:multipart(
                    {'item_index':item,'duration_seconds':'2'},f'p30-{rid}-{c["user_id"]}-{item}.webm'))
                for c,t,d in zip(students,teacher_clients,uploads):t['recording_id']=d['recording_id'];t['student_id']=c['user_id']
                wave(pool,teacher_clients,'playback',lambda c:reverse('teacher_lesson_13_gawain_1_audio',args=[c['recording_id']]))
                wave(pool,teacher_clients,'teacher_review','/api/teacher/lesson-13-gawain-1/score/',lambda c:{'submission_id':c['recording_id'],'score':0})
                wave(pool,students,'recording_progress',url,{'completed_items':item+1,'current_index':item+1,'state':{'current_item':item+1}})
            wave(pool,students,'finish',reverse('prescribed_activity_complete',kwargs={'activity_key':key}),{})
            wave(pool,students,'finish_replay',reverse('prescribed_activity_complete',kwargs={'activity_key':key}),{})
            wave(pool,students,'finish_return','/dashboard/assessment/')
            for c in students:c['attempt_id']=str(uuid.uuid4())
            evidence=wave(pool,students,'attempt_upload',reverse('session_5_lesson_14_gawain_4_recording'),lambda c:multipart(
                {'item_index':'0','duration_seconds':'2','attempt_id':c['attempt_id'],'stt_match':'false','transcript':'synthetic mismatched reading'},f'p30-{rid}-{c["user_id"]}-attempt.webm'))
            wave(pool,students,'attempt_replay',reverse('session_5_lesson_14_gawain_4_recording'),lambda c:multipart(
                {'item_index':'0','duration_seconds':'2','attempt_id':c['attempt_id'],'stt_match':'false'},f'p30-{rid}-{c["user_id"]}-replay.webm'))
            wave(pool,students,'invalid_duration',reverse('session_5_lesson_14_gawain_4_recording'),lambda c:multipart(
                {'item_index':'0','duration_seconds':'NaN'},f'p30-{rid}-invalid.webm'),expected=400)
            wave(pool,students,'invalid_json',progress,b'[]',expected=400)
            # Reproduce a missing recording using only disposable metadata.
            # Authorization must succeed before storage returns the expected 404.
            for c,t in zip(students,teacher_clients):
                missing=StudentActivityRecordingSubmission.objects.create(student_id=c['user_id'],
                    activity_key='session-4-gawain-1',item_index=0,
                    audio_file=f'activity_recordings/p30-{rid}-{c["user_id"]}-missing.webm')
                t['missing_recording_id']=missing.pk
            connections.close_all()
            wave(pool,teacher_clients,'missing_playback',lambda c:reverse('teacher_session_4_gawain_1_audio',args=[c['missing_recording_id']]),expected=404)
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                pending=PrescribedReadingAttempt.objects.filter(student_id__in=users,audio_analysis_status='pending').count()
                connections.close_all()
                if not pending:break
                wave(pool,students,'analysis_wait','/dashboard/assessment/');time.sleep(1)
            report['analysis_complete']=PrescribedReadingAttempt.objects.filter(student_id__in=users,audio_analysis_status='complete').count()
            report['attempts']=PrescribedReadingAttempt.objects.filter(student_id__in=users).count()
            report['completed_activities']=StudentActivityProgress.objects.filter(student_id__in=users,activity_key=key,activity_completed=True).count()
            report['checked_recordings']=StudentActivityRecordingSubmission.objects.filter(student_id__in=users,activity_key=key,status='checked').count()
            report['student_logins_preserved']=Session.objects.filter(session_key__in=[c['cookie'] for c in students]).count()
            assert report['analysis_complete']==report['attempts']==report['completed_activities']==report['student_logins_preserved']==30
            assert report['checked_recordings']==120
            report['simultaneous_ready_streams']=30
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    except Exception as exc:
        report['aborted']=True;report['error_type']=type(exc).__name__
        import traceback
        report['error_locations']=[{'file':os.path.basename(f.filename),'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
        print('PABASA_PRESCRIBED_ABORT '+json.dumps({'error_type':report['error_type'],'error_locations':report['error_locations']}),flush=True)
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
        print('PABASA_PRESCRIBED_THIRTY '+json.dumps(report),flush=True)
    if report['aborted']:raise SystemExit(1)


if __name__=='__main__':run()
