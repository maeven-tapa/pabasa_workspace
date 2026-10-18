"""Opt-in live lifecycle probe: six teachers, five enrolled students each.

Only run in a disposable Cloud Run diagnostic job with the serving release's
application source and database identity. Uses normal HTTPS/Google APIs and
temporary simulated reading evidence; never reads real students or recordings.
Full provider accuracy for every CRLA item is outside this bounded probe.
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
import traceback
import uuid

CLIENT_COUNT=30
TEACHER_COUNT=6
CLASS_SIZE=5
HOST=os.environ.get('PABASA_BENCHMARK_HOST','tupcpabasa.app')

def run_speech(students, material_id, settings, report, rows, request, poll_students=None, record_uploads=True):
    """Thirty real authenticated WebSockets with generated PCM, no provider mocks."""
    import asyncio
    import base64
    from websockets.asyncio.client import connect
    pcm = base64.b64decode(os.environ['PABASA_BENCHMARK_PCM_BASE64'], validate=True)
    assert 16000 < len(pcm) < 640000, 'Expected a short generated mono 16 kHz PCM fixture'
    target = 'The cat sat on the mat.'
    speech_clients = len(students)
    barrier = threading.Barrier(speech_clients)
    def ticket(client):
        row = request(client, 'ticket', {'material_id':material_id, 'mode':'sentence',
            'target_text':target}, barrier)
        token = row.pop('_ticket', None)
        rows.append(row)
        assert row['ok'] and token, 'Speech authorization failed'
        return token
    with cf.ThreadPoolExecutor(max_workers=speech_clients) as pool:
        tickets = list(pool.map(ticket, students))

    async def stream(client, ticket, ready, go):
        start = time.perf_counter()
        final = None
        error_type = None
        ready_wait_ms = 0
        try:
            async with connect('wss://' + HOST + '/ws/reading/crla/', origin='https://' + HOST,
                    additional_headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+client['key'],
                        'User-Agent':report['user_agent']}, open_timeout=30, close_timeout=5) as ws:
                await ws.send(json.dumps({'ticket':ticket}))
                message = json.loads(await asyncio.wait_for(ws.recv(), 30))
                assert message.get('type') == 'ready', 'Stream not ready'
                ready.append(True)
                # Actual microphones send captured PCM as soon as ready. Keep
                # the provider supplied while the synthetic spoken fixtures
                # synchronize; an idle benchmark barrier can otherwise cause
                # an avoidable provider input-timeout/Aborted response.
                ready_at=time.perf_counter()
                while not go.is_set():
                    await ws.send(bytes(6400))
                    try:await asyncio.wait_for(go.wait(),.2)
                    except asyncio.TimeoutError:pass
                ready_wait_ms=(time.perf_counter()-ready_at)*1000
                async def send_audio():
                    for at in range(0, len(pcm), 6400):
                        await ws.send(pcm[at:at+6400])
                        await asyncio.sleep(.2)
                    await ws.send('{"type":"finish"}')
                sender = asyncio.create_task(send_audio())
                try:
                    while True:
                        message = json.loads(await asyncio.wait_for(ws.recv(), 35))
                        if message.get('type') == 'final':
                            final = message['final_token']
                            # A final transcript can precede the end of the
                            # provider stream. Drain it before closing the
                            # socket, matching the browser's finish handshake.
                            continue
                        if message.get('type') == 'finished':
                            break
                        if message.get('type') == 'error':
                            raise RuntimeError('Provider or stream failure')
                finally:
                    await sender
        except Exception as exc:
            error_type = type(exc).__name__
        rows.append({'operation':'stream','ms':(time.perf_counter()-start)*1000,'ready_wait_ms':ready_wait_ms,
                     'status':101 if final else 0,'ok':bool(final),'error_type':error_type})
        return final

    async def all_streams():
        ready, go = [], asyncio.Event()
        tasks = [asyncio.create_task(stream(c,t,ready,go)) for c,t in zip(students,tickets)]
        stop_polls = asyncio.Event()
        async def poll_while_recording():
            while not stop_polls.is_set():
                wave = await asyncio.gather(*(asyncio.to_thread(request,c,'poll') for c in (poll_students or students)))
                rows.extend(wave)
                assert all(row['ok'] for row in wave), 'Polling failed during speech'
                await asyncio.sleep(1)
        polling = None
        try:
            deadline = time.monotonic() + 35
            while len(ready) < speech_clients and time.monotonic() < deadline:
                if any(t.done() for t in tasks): break
                await asyncio.sleep(.05)
            assert len(ready) == speech_clients, 'Not all active streams became ready together'
            go.set()
            polling = asyncio.create_task(poll_while_recording())
            result = await asyncio.gather(*tasks)
            stop_polls.set()
            await polling
            return result
        finally:
            stop_polls.set()
            if polling and not polling.done():
                await polling
            go.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finals = asyncio.run(all_streams())
    assert all(finals), 'All live Google finals required'
    barrier = threading.Barrier(speech_clients)
    def evaluate(pair):
        client, token = pair
        row = request(client, 'evaluate', {'final_token':token,'sentence_word_results':[]}, barrier)
        result = row.pop('_result', {})
        rows.append(row)
        assert row['ok'] and result.get('complete') and result.get('correct_word_count') == 6, 'Generated speech did not score as expected'
        return True
    with cf.ThreadPoolExecutor(max_workers=speech_clients) as pool:
        evaluations = list(pool.map(evaluate, zip(students, finals)))
    if not record_uploads:
        return {'simultaneous_ready_streams':speech_clients,'provider_finals':len(finals),'authorized_evaluations':sum(evaluations),'recorded_uploads':{}}
    # Also exercise real recorded-file uploads through the normal clip path.
    import io
    import av
    audio = io.BytesIO()
    with av.open(audio, 'w', format='webm') as container:
        encoder = container.add_stream('libopus', rate=16000)
        encoder.layout = 'mono'
        encoder.codec_context.format = 's16'
        frame = av.AudioFrame(format='s16', layout='mono', samples=len(pcm)//2)
        frame.sample_rate = 16000
        frame.planes[0].update(pcm)
        for packet in encoder.encode(frame): container.mux(packet)
        for packet in encoder.encode(None): container.mux(packet)
    boundary = 'PabasaGeneratedRecording'
    fields = {'official_assessment_id':str(material_id),'official_crla_assessment':'1','target_text':target,
              'mode':'sentence','language':'English','current_syllable_index':'0',
              'crla_sentence_word_scoring':'1','sentence_word_results':'[]'}
    clip_counts = {}
    for operation, official in (('clip','0'), ('crla_clip','1')):
        fields['official_crla_assessment'] = official
        multipart = b''.join((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
                             for name,value in fields.items())
        multipart += (f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="generated.webm"\r\nContent-Type: audio/webm\r\n\r\n').encode()
        multipart += audio.getvalue() + (f'\r\n--{boundary}--\r\n').encode()
        barrier = threading.Barrier(speech_clients)
        def clip(client):
            row = request(client,operation,multipart,barrier)
            result = row.pop('_result',{})
            rows.append(row)
            assert row['ok'] and result.get('correct_word_count') == 6, 'Recorded upload failed or scored incorrectly'
            return True
        with cf.ThreadPoolExecutor(max_workers=speech_clients) as pool:
            clip_counts[operation] = sum(pool.map(clip,students))
    return {'simultaneous_ready_streams':speech_clients,'provider_finals':len(finals),
            'authorized_evaluations':sum(evaluations),'recorded_uploads':clip_counts,
            'synthetic_words_per_student':6,'recording_format':'WebM/Opus',
            'longest_pre_audio_wait_ms':round(max(row.get('ready_wait_ms',0) for row in rows if row['operation']=='stream'),2)}



def stats(rows):
    values = sorted(row['ms'] for row in rows)
    return {'count': len(rows), 'mean_ms': round(statistics.mean(values), 2),
            'p95_ms': round(values[math.ceil(.95 * len(values)) - 1], 2),
            'max_ms': round(max(values), 2), 'failures': sum(not r['ok'] for r in rows),
            'statuses': {str(s): sum(r['status'] == s for r in rows)
                         for s in sorted({r['status'] for r in rows})},
            'transport_retries':sum(r.get('transport_retries',0) for r in rows),
            'transport_error_types':sorted({error for row in rows for error in row.get('transport_errors',[])})}


def run():
    if not os.environ.get('CLOUD_RUN_EXECUTION') or os.environ.get('PABASA_AUTHORIZED_CRLA30_RESILIENCE')!='30':
        raise RuntimeError('Requires an authorized disposable 6x5 diagnostic job')
    if not os.environ.get('PABASA_BENCHMARK_PCM_BASE64'):
        raise RuntimeError('Generated speech fixture required')
    sys.path.insert(0,os.environ.get('PABASA_DIAGNOSTIC_SOURCE_ROOT','/app/pabasa_site'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.auth.hashers import make_password
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.core.management import call_command
    from django.db import connections, transaction
    from pabasa_app.system_clock import today
    from pabasa_app.models import (ActivityLog,Assessment,CalendarEvent,Enrollment,LiveAssessmentSession,
        Material,Notification,School,SchoolCalendar,Section,User)
    call_command('check_migration_readiness',require_recorded=True,verbosity=0)
    call_command('migrate',check=True,verbosity=0)
    # No migrations are applied. Verify fixture columns before creating rows.
    from django.db import connection
    with connection.cursor() as cursor:
        for model in (ActivityLog,Assessment,CalendarEvent,Enrollment,LiveAssessmentSession,Material,Notification,School,SchoolCalendar,Section,User):
            columns={column.name for column in connection.introspection.get_table_description(cursor,model._meta.db_table)}
            assert {field.column for field in model._meta.local_fields}<=columns,'Diagnostic ORM differs from the live schema'
    assert settings.DATABASES['default']['ENGINE']=='django.db.backends.postgresql'
    rid=uuid.uuid4().hex[:12]
    report={'test_id':rid,'clients':CLIENT_COUNT,'teacher_clients':TEACHER_COUNT,'students_per_class':CLASS_SIZE,
        'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'user_agent':'PABASA-authorized-crla-thirty-resilience-'+rid,
        'aborted':False,'waves':[],
        'scope':'Six HTTP-created teacher sessions, five distinct enrolled students each; actual Google streams and generated WebM clips, simulated complete reading/question/rating evidence, normal completion/finalization endpoints. No real microphone or real student data.'}
    print('PABASA_CRLA30_START '+json.dumps({'test_id':rid,'students':30,'teachers':6}),flush=True)
    users=[];keys=[];sections=[];live_ids=[];clients=[];rows=[];students=[];teachers=[]
    school=calendar=material=None
    csrf=secrets.token_hex(32);password=secrets.token_urlsafe(24);password_hash=make_password(password)
    def user(label,role):
        u=User.objects.create(custom_id='R3-'+rid+'-'+label,role=role,first_name='Synthetic',last_name='Resilience Test',
            sex='female',birth_month=1,birth_day=1,birth_year=2012,email=None,password_hash=password_hash,school_record=school)
        users.append(u.pk);return u
    def client(u,group):
        store=SessionStore();store.update({'user_id':u.pk,'user_role':u.role,'pabasa_benchmark':rid});store.set_expiry(1200);store.create();keys.append(store.session_key)
        c={'user_id':u.pk,'custom_id':u.custom_id,'key':store.session_key,'group':group,'live_id':'',
            'connection':http.client.HTTPSConnection(HOST,timeout=90)}
        clients.append(c);return c
    def request(c,operation,payload=None,barrier=None,network_retry=False,expected=200):
        if barrier:barrier.wait(timeout=45)
        start=time.perf_counter();status=0;data={};error=None;ok=False
        route=f'/api/live-assessment/session/{c["live_id"]}/'
        if operation in ('update','complete','late_complete','paused_write','disconnect','save_ack','saved_write'):route+='student-update/'
        if operation in ('start','end','end_replay','pause','resume','foreign_teacher','student_action','interrupt','interrupt_replay','close_save','cancel','abandon'):route+='action/'
        if operation=='recovery_validation':
            from urllib.parse import urlencode
            route+='recovery-validation/?'+urlencode({'section_id':c['section'],'school_calendar_id':calendar.pk,'term':calendar.current_term,
                'material_id':material.pk,'assessment_week':'pre_assessment','assessment_phase':'pre_assessment'})
        if operation=='create':route='/dashboard/teacher/start-live-assessment/'
        if operation=='invitation':route='/api/live-assessment/active-invitation/'
        if operation=='ticket':route='/api/reading/crla-stream/start/'
        if operation=='evaluate':route='/api/reading/crla-stream/evaluate/'
        if operation in ('clip','crla_clip'):route='/api/reading/transcribe/'
        if operation=='dashboard':route='/dashboard/assessment/'
        if operation=='control':route=f'/dashboard/live-assessment/{c["live_id"]}/control/'
        if operation=='waiting':route=f'/dashboard/live-assessment/{c["live_id"]}/waiting/'
        if operation.startswith('reader_'):
            stage=operation.removeprefix('reader_')
            route=f'/dashboard/assessment/reading_ui/{"para" if "story" in stage else "word"}/?official_assessment_id={material.pk}&live=1&live_session_id={c["live_id"]}&live_recovery=1&countdown=0&crla_stage={stage}'
        if operation=='login':
            from urllib.parse import urlencode
            route='/api/login/';payload=urlencode({'custom_id':c['custom_id'],'password':password}).encode()
        headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+c['key']+'; csrftoken='+csrf,
            'User-Agent':report['user_agent'],'Origin':'https://'+HOST,'Referer':'https://'+HOST+'/',
            'X-CSRFToken':csrf,'X-Requested-With':'XMLHttpRequest','Content-Type':'application/json'}
        if operation in ('clip','crla_clip'):headers.update({'Content-Type':'multipart/form-data; boundary=PabasaGeneratedRecording',
            'X-Pabasa-STT-Provider':'google','X-Pabasa-STT-Model':'chirp_3'})
        if operation=='login':headers['Content-Type']='application/x-www-form-urlencoded'
        page=operation in ('dashboard','control','waiting') or operation.startswith('reader_')
        try:
            c['connection'].request('POST' if payload is not None else 'GET',route,
                body=payload if isinstance(payload,bytes) else json.dumps(payload) if payload is not None else None,headers=headers)
            response=c['connection'].getresponse();status=response.status;raw=response.read()
            if operation=='login' and status==200:
                from http.cookies import SimpleCookie
                cookies=SimpleCookie()
                for name,value in response.getheaders():
                    if name.lower()=='set-cookie':cookies.load(value)
                if settings.SESSION_COOKIE_NAME in cookies:
                    c['key']=cookies[settings.SESSION_COOKIE_NAME].value
                    if c['key'] not in keys:keys.append(c['key'])
            if not page:data=json.loads(raw)
            ok=status==expected and (expected!=200 or page or data.get('success') is True)
            if operation=='post_end':ok=ok and data.get('session',{}).get('status')=='ended'
            if operation=='poll':ok=ok and data.get('session',{}).get('status')=='started'
            if operation=='recovery_validation':ok=ok and data.get('conclusively_invalid') is False
            if operation=='recovery_poll':
                state=data.get('session',{}).get('student_states',{}).get(str(c['user_id']),{})
                ok=ok and state.get('recovery_state',{}).get('crla_question_index')==3
            if operation=='completed_poll':
                state=data.get('session',{}).get('student_states',{}).get(str(c['user_id']),{})
                ok=ok and state.get('status')=='completed' and state.get('recovery_state',{}).get('temporary_completed') is True
            if not ok:
                error='UnexpectedStatusOrContent'
                if operation=='create':
                    allowed=('No active students found for this course','Material not found','Live Assessment is available only for the official CRLA assessment.',
                        'Live CRLA assessments require an active Assessment Week for this section.','A numeric section_id is required','Section not found')
                    report.setdefault('creation_error_categories',[]).append(data.get('error') if data.get('error') in allowed else 'Other validation error')
        except Exception as exc:
            error=type(exc).__name__;c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=90)
        row={'operation':operation,'status':status,'ok':ok,'error_type':error,'ms':(time.perf_counter()-start)*1000}
        if operation=='ticket' and ok:row['_ticket']=data.get('ticket')
        if operation in ('evaluate','clip','crla_clip') and ok:row['_result']=data
        if operation=='create' and ok:
            session=data.get('session',{});c['live_id']=session.get('id','');live_ids.append(c['live_id'])
            c['available_ids']={s['id'] for s in session.get('available_students',[])}
        return row
    def wave(pool,members,operation,payload=None,expected=200):
        barrier=threading.Barrier(len(members));started=dt.datetime.now(dt.timezone.utc).isoformat()
        result=list(pool.map(lambda c:request(c,operation,payload(c) if callable(payload) else payload,barrier,expected=expected),members))
        rows.extend(result);summary={'operation':operation,'started_utc':started,**stats(result)};report['waves'].append(summary)
        print('PABASA_CRLA30_WAVE '+json.dumps(summary),flush=True)
        assert all(r['ok'] for r in result),'Wave failed: '+operation
    try:
        with transaction.atomic():
            source=Material.objects.filter(system_assessment_key='bosy_crla_pretest').first();assert source
            school=School.objects.create(name='Synthetic thirty resilience '+rid,code='R30'+rid)
            # Teacher creation intentionally rejects enrollments in an inactive
            # year. Reuse the current calendar without changing it; all added
            # events are scoped exclusively to this disposable school.
            calendar=SchoolCalendar.objects.filter(is_active=True).order_by('-updated_at','-id').first();assert calendar
            term=calendar.current_term or 1
            day=today()
            for kind,first,last in [('school_opening',day-dt.timedelta(days=2),day-dt.timedelta(days=2)),
                    ('pre_assessment',day-dt.timedelta(days=1),day+dt.timedelta(days=1)),('school_closing',day+dt.timedelta(days=20),day+dt.timedelta(days=20))]:
                CalendarEvent.objects.create(school_calendar=calendar,school=school,scope=CalendarEvent.SCOPE_SCHOOL,term=term,title='Synthetic '+kind,event_type=kind,start_date=first,end_date=last)
            for group in range(TEACHER_COUNT):
                t=user('T'+str(group),'teacher')
                section=Section.objects.create(school=school,school_calendar=calendar,teacher=t,class_code='R30'+rid+str(group),class_name='Synthetic resilience class',subject='Reading',assessment_week_enabled=True)
                sections.append(section.pk)
                if material is None:
                    root=Assessment.objects.create(teacher=t,title='Synthetic thirty resilience '+rid,code='R30ROOT'+rid,assessment_type=source.item_type,status='published',is_system_owned=True,
                        system_assessment_key='r30_'+rid,system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1)
                    material=Material.objects.create(assessment=root,teacher=t,title='Synthetic thirty resilience '+rid,code='R30MAT'+rid,is_system_owned=True,
                        system_assessment_key='r30_'+rid,is_official_reading=True,assessment_kind='crla',assessment_set='crla',system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1,
                        item_type=source.item_type,language='English',content_json=source.content_json,content_text=source.content_text,prompt_text=source.prompt_text,type='assessment',is_active=True,status='published',student_access=True)
                material.assigned_sections.add(section)
                tc=client(t,group);tc['section']=section.pk;tc['members']=[];teachers.append(tc)
                for index in range(CLASS_SIZE):
                    s=user('S'+str(group*CLASS_SIZE+index),'student');section.add_student(s);tc['members'].append(s.pk);students.append(client(s,group))
        report['enrolled_students']=Enrollment.objects.filter(student_id__in=users,status='active',is_active=True).count()
        assert report['enrolled_students']==CLIENT_COUNT and len(teachers)==TEACHER_COUNT
        connections.close_all();report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        with cf.ThreadPoolExecutor(max_workers=CLIENT_COUNT+TEACHER_COUNT) as pool:
            wave(pool,clients,'login',{})
            wave(pool,teachers,'create',lambda c:{'section_id':c['section'],'material_id':material.pk})
            assert len(set(live_ids))==TEACHER_COUNT
            for t in teachers:assert set(t['members'])<=t['available_ids']
            for c in students:c['live_id']=teachers[c['group']]['live_id']
            wave(pool,teachers,'control')
            wave(pool,teachers,'start',lambda c:{'action':'start','selected_student_ids':c['members'],'countdown_seconds':0})
            wave(pool,students,'poll');wave(pool,students,'invitation');wave(pool,students,'dashboard');wave(pool,students,'reader_words')
            # Thirty simultaneous provider streams; students poll during capture.
            report['speech']=run_speech(students,material.pk,settings,report,rows,request,poll_students=students)
            # Six teacher controls run while thirty students send updates.
            wave(pool,teachers,'pause',{'action':'pause'})
            wave(pool,students,'paused_write',{'status':'reading','progress':.99,'recovery_state':{'stage':'sentences','crla_question_index':9}})
            paused=list(LiveAssessmentSession.objects.filter(pk__in=live_ids))
            assert all(l.status=='paused' and all(s.get('recovery_state',{}).get('crla_question_index')!=9 for s in l.student_states.values()) for l in paused)
            wave(pool,teachers,'resume',{'action':'resume'});wave(pool,students,'poll')
            # Save a real server recovery checkpoint before deliberate faults.
            checkpoint={'stage':'words','branch':'words','crla_question_index':3,'task1_score':2,
                'task1_word_scores':[1,1,None],'material_id':str(material.pk)}
            wave(pool,students,'update',{'status':'reading','progress':.2,'recovery_state':checkpoint})
            # Legacy sessions can have an assigned roster but no saved batch
            # map. Exercise repair and final-save acknowledgements during Pause.
            wave(pool,teachers,'pause',{'action':'pause'})
            LiveAssessmentSession.objects.filter(pk__in=live_ids).update(batch_assignments={},total_batches=0)
            wave(pool,students,'save_ack',{'status':'reading','save_acknowledged':True,'recovery_state':{'stage':'words','crla_question_index':99}})
            paused=list(LiveAssessmentSession.objects.filter(pk__in=live_ids))
            assert all(s.get('status')=='paused' and s.get('recovery_state',{}).get('crla_question_index')==3 and s.get('participation_status')!='saved' for l in paused for s in l.student_states.values())
            wave(pool,teachers,'close_save',{'action':'close_and_save'})
            wave(pool,students,'save_ack',{'status':'reading','save_acknowledged':True,'recovery_state':checkpoint})
            saved=list(LiveAssessmentSession.objects.filter(pk__in=live_ids))
            assert all(l.status=='paused' and len(l.batch_assignments)==CLASS_SIZE and l.total_batches==1 for l in saved)
            assert sum(s.get('status')=='paused' and s.get('participation_status')=='saved' and s.get('recovery_state',{}).get('crla_question_index')==3 for l in saved for s in l.student_states.values())==CLIENT_COUNT
            versions={l.pk:l.state_version for l in saved}
            wave(pool,teachers,'close_save',{'action':'close_and_save'})
            assert all(l.state_version==versions[l.pk] for l in LiveAssessmentSession.objects.filter(pk__in=live_ids))
            wave(pool,teachers,'resume',{'action':'resume'});wave(pool,students,'recovery_poll')
            assert all(s.get('participation_status')=='active' for l in LiveAssessmentSession.objects.filter(pk__in=live_ids) for s in l.student_states.values())
            report['legacy_batch_maps_repaired']=TEACHER_COUNT;report['paused_save_acknowledgements']=CLIENT_COUNT
            report['paused_save_replay_versions_unchanged']=True
            # All thirty close their transport without a final save, then rejoin.
            for c in students:
                c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=90)
            wave(pool,students,'recovery_poll');wave(pool,students,'reader_words')
            report['student_transport_rejoins']=CLIENT_COUNT
            # One expired login per class must request authentication without
            # clearing its saved progress. Reauthenticate with normal login.
            expired=students[::CLASS_SIZE]
            Session.objects.filter(session_key__in=[c['key'] for c in expired]).delete();connections.close_all()
            wave(pool,expired,'expired_login',expected=401)
            wave(pool,expired,'login',{})
            wave(pool,students,'recovery_poll');report['expired_student_logins_recovered']=len(expired)
            # Teacher page exits use the existing interrupt beacon. Repeated
            # exits are idempotent; other student writes cannot reopen pause.
            wave(pool,teachers,'interrupt',{'action':'interrupt'})
            wave(pool,teachers,'interrupt_replay',{'action':'interrupt'})
            wave(pool,students,'paused_write',{'status':'reading','recovery_state':{'stage':'words','crla_question_index':99}})
            for c in teachers:
                c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=90)
            wave(pool,teachers,'control');wave(pool,teachers,'recovery_validation')
            wave(pool,students,'recovery_poll')
            wave(pool,teachers,'resume',{'action':'resume'});wave(pool,students,'poll')
            report['teacher_exit_recoveries']=TEACHER_COUNT
            # A teacher losing connectivity without delivering an unload beacon
            # does not implicitly finalize a result or erase student progress.
            for c in teachers:
                c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=90)
            wave(pool,students,'recovery_poll');wave(pool,teachers,'control')
            assert Assessment.objects.filter(student_id__in=users,material=material,attempt_status='completed').count()==0
            # Explicit Save & Exit waits for thirty final acknowledgements.
            wave(pool,teachers,'close_save',{'action':'close_and_save'})
            wave(pool,students,'save_ack',{'status':'reading','save_acknowledged':True,'connection_status':'disconnected','recovery_state':checkpoint})
            wave(pool,students,'saved_write',{'status':'reading','recovery_state':{'stage':'sentences','crla_question_index':99}})
            saved=list(LiveAssessmentSession.objects.filter(pk__in=live_ids))
            assert sum(s.get('participation_status')=='saved' and s.get('recovery_state',{}).get('crla_question_index')==3 for l in saved for s in l.student_states.values())==CLIENT_COUNT
            wave(pool,teachers,'resume',{'action':'resume'});wave(pool,students,'recovery_poll')
            report['close_save_acknowledgements']=CLIENT_COUNT
            # Cut six real provider sockets mid-audio while classmates poll.
            import asyncio,base64
            from websockets.asyncio.client import connect
            victims=students[::CLASS_SIZE];tickets=[]
            for c in victims:
                row=request(c,'ticket',{'material_id':material.pk,'mode':'sentence','target_text':'The cat sat on the mat.'})
                ticket=row.pop('_ticket',None);rows.append(row);assert row['ok'] and ticket;tickets.append(ticket)
            report['intentional_drop_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            async def disconnect_all():
                ready=[];go=asyncio.Event()
                async def cut(c,ticket):
                    started=time.perf_counter()
                    async with connect('wss://'+HOST+'/ws/reading/crla/',origin='https://'+HOST,
                            additional_headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+c['key'],'User-Agent':report['user_agent']+'-intentional-drop'},open_timeout=30,close_timeout=5) as ws:
                        await ws.send(json.dumps({'ticket':ticket}));message=json.loads(await asyncio.wait_for(ws.recv(),30));assert message.get('type')=='ready'
                        ready.append(True);await asyncio.wait_for(go.wait(),30)
                        pcm=base64.b64decode(os.environ['PABASA_BENCHMARK_PCM_BASE64'])
                        for offset in range(0,19200,6400):
                            await ws.send(pcm[offset:offset+6400]);await asyncio.sleep(.2)
                        ws.transport.abort();await ws.wait_closed()
                    rows.append({'operation':'intentional_stream_disconnect','status':101,'ok':True,'ms':(time.perf_counter()-started)*1000})
                tasks=[asyncio.create_task(cut(c,t)) for c,t in zip(victims,tickets)]
                try:
                    deadline=time.monotonic()+35
                    while len(ready)<len(victims) and time.monotonic()<deadline:
                        if any(t.done() for t in tasks):break
                        await asyncio.sleep(.05)
                    assert len(ready)==TEACHER_COUNT;go.set()
                    polls=await asyncio.gather(*(asyncio.to_thread(request,c,'poll') for c in students));rows.extend(polls);assert all(p['ok'] for p in polls)
                    await asyncio.gather(*tasks)
                finally:
                    go.set()
                    for task in tasks:
                        if not task.done():task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
            asyncio.run(disconnect_all());report['intentional_drop_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            wave(pool,students,'recovery_poll')
            report['speech_after_disconnect']=run_speech(victims,material.pk,settings,report,rows,request,poll_students=students,record_uploads=False)
            assert report['speech_after_disconnect']['provider_finals']==TEACHER_COUNT
            evidence={'material_id':str(material.pk),'task1_score':0,'task1_word_scores':[]}
            for item in range(10):
                evidence.update(stage='words',branch='words',crla_question_index=item+1,task1_score=item+1,task1_word_scores=[1]*(item+1))
                wave(pool,students,'update',{'status':'reading','progress':(item+1)/30,'recovery_state':dict(evidence)})
            evidence.update(stage='transition_to_sentence',next_stage='sentences')
            wave(pool,students,'update',{'status':'reading','recovery_state':dict(evidence)})
            wave(pool,students,'reader_sentences')
            for item in range(5):
                evidence.update(stage='sentences',branch='sentences',crla_question_index=item+1,task2_sentences_score=(item+1)*2,task2_type='Task 2S / Sentences',task2_sentence_scores=[2]*(item+1),part1_total_score=10+(item+1)*2)
                wave(pool,students,'update',{'status':'reading','progress':.35+(item+1)/25,'recovery_state':dict(evidence)})
            for stage in ('story_selection','story_ready','story_reading'):
                evidence.update(stage=stage,branch='story',selected_story='Synthetic story',story_number=1,crla_question_index=0)
                wave(pool,students,'update',{'status':'reading','recovery_state':dict(evidence)})
            wave(pool,students,'reader_story_reading')
            evidence.update(story_word_results={'0':{str(i):'correct' for i in range(6)},'1':{str(i):'correct' for i in range(6)}},
                words_read=12,total_words_read=12,story_total_words=12,total_story_words=12,miscues=0,duration_seconds=6,wpm=120,story_reading_elapsed_ms=6000)
            for segment in range(2):
                evidence['story_segment_index']=segment
                wave(pool,students,'update',{'status':'reading','progress':.65+segment/10,'recovery_state':dict(evidence)})
            for question in range(3):
                evidence.update(stage='story_comprehension',crla_question_index=question+1,crla_answers=['Synthetic answer']*(question+1),crla_results=[True]*(question+1),correct_answers=question+1,total_questions=3)
                wave(pool,students,'update',{'status':'reading','progress':.8+question/30,'recovery_state':dict(evidence)})
            evidence.update(stage='learner_experience')
            wave(pool,students,'update',{'status':'reading','recovery_state':dict(evidence)})
            evidence.update(stage='completed',next_stage='completed',temporary_completed=True,learner_experience_rating=4)
            wave(pool,students,'complete',{'status':'completed','progress':1,'elapsed_seconds':30,'recovery_state':dict(evidence)})
            wave(pool,students,'completed_poll');wave(pool,students,'waiting')
            report['results_before_teacher_end']=Assessment.objects.filter(student_id__in=users,material=material,attempt_status='completed').count()
            assert report['results_before_teacher_end']==0,'Students must not finalize official live results'
            # Late heartbeats cannot revert a temporarily completed learner.
            wave(pool,students,'late_complete',{'status':'reading','progress':0,'recovery_state':{'stage':'words','crla_question_index':0}})
            wave(pool,students,'completed_poll')
            # Isolation: a different teacher and a student cannot end a class.
            for t in teachers:t['own_live']=t['live_id'];t['live_id']=teachers[(t['group']+1)%TEACHER_COUNT].get('own_live',teachers[(t['group']+1)%TEACHER_COUNT]['live_id'])
            wave(pool,teachers,'foreign_teacher',{'action':'end'},expected=403)
            for t in teachers:t['live_id']=t.pop('own_live')
            wave(pool,students,'student_action',{'action':'end'},expected=403)
            with cf.ThreadPoolExecutor(max_workers=TEACHER_COUNT) as controls:
                barrier=threading.Barrier(TEACHER_COUNT)
                pending=[controls.submit(request,t,'end',{'action':'end'},barrier) for t in teachers]
                wave(pool,students,'completed_poll')
                ends=[f.result() for f in pending];rows.extend(ends);report['end_session']=stats(ends)
                assert all(r['ok'] for r in ends),'End Session failed'
            wave(pool,students,'post_end');wave(pool,students,'dashboard');wave(pool,teachers,'control')
            wave(pool,teachers,'end_replay',{'action':'end'})
            for _ in range(5):
                time.sleep(1);wave(pool,students,'post_end');wave(pool,students,'dashboard')
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        results=Assessment.objects.filter(student_id__in=users,material=material,attempt_status='completed')
        report['completed_results']=results.count();report['distinct_result_students']=results.values('student_id').distinct().count()
        report['classified_results']=sum(bool(r.crla_classification or r.classification) for r in results)
        owned_enrollments={e.student_id:e.pk for e in Enrollment.objects.filter(student_id__in=users)}
        report['results_with_correct_enrollment']=sum(r.enrollment_id==owned_enrollments.get(r.student_id) for r in results)
        live_rows=list(LiveAssessmentSession.objects.filter(pk__in=live_ids));report['ended_sessions']=sum(l.status=='ended' for l in live_rows)
        report['per_class_completed_results']=[results.filter(student_id__in=t['members']).count() for t in teachers]
        report['student_logins_preserved']=Session.objects.filter(session_key__in=[c['key'] for c in students]).count()
        report['all_logins_preserved']=Session.objects.filter(session_key__in=keys).count()
        assert report['completed_results']==report['distinct_result_students']==report['student_logins_preserved']==CLIENT_COUNT
        assert report['classified_results']==report['results_with_correct_enrollment']==CLIENT_COUNT
        assert report['per_class_completed_results']==[CLASS_SIZE]*TEACHER_COUNT and report['ended_sessions']==TEACHER_COUNT and report['all_logins_preserved']==CLIENT_COUNT+TEACHER_COUNT
    except Exception as exc:
        report['aborted']=True;report['error_type']=type(exc).__name__
        report['error_locations']=[{'file':os.path.basename(f.filename),'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
        report['error_stage']=rows[-1]['operation'] if rows else 'fixture'
    finally:
        report.setdefault('http_finished_utc',dt.datetime.now(dt.timezone.utc).isoformat())
        # Keep aggregate evidence even if a later cleanup failure needs repair.
        print('PABASA_CRLA30_PRE_CLEANUP '+json.dumps({k:v for k,v in report.items() if k!='waves'}),flush=True)
        for c in clients:c['connection'].close()
        connections.close_all();Session.objects.filter(session_key__in=keys).delete()
        Notification.objects.filter(created_by_id__in=users).delete();ActivityLog.objects.filter(actor_id__in=users).delete()
        User.objects.filter(pk__in=users).delete();Section.objects.filter(pk__in=sections).delete()
        if school:
            CalendarEvent.objects.filter(school_id=school.pk).delete()
            School.objects.filter(pk=school.pk).delete()
        report['remaining_users']=User.objects.filter(pk__in=users).count();report['remaining_sessions']=Session.objects.filter(session_key__in=keys).count()
        report['remaining_live_sessions']=LiveAssessmentSession.objects.filter(pk__in=live_ids).count()
        report['remaining_materials']=Material.objects.filter(pk=material.pk).count() if material else 0
        report['operations']={name:stats([r for r in rows if r['operation']==name]) for name in sorted({r['operation'] for r in rows})}
        report['total_requests']=len(rows);report['failures']=sum(not r['ok'] for r in rows);report['transport_retries']=sum(r.get('transport_retries',0) for r in rows)
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        print('PABASA_CRLA30_RESULT '+json.dumps(report),flush=True)
    if report['aborted']:raise SystemExit(1)

if __name__=='__main__':run()
