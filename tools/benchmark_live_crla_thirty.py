"""Bounded, opt-in live CRLA benchmark using 30 disposable enrolled students.

Run only in a purpose-created Cloud Run diagnostic job with the deployed image,
identity and database configuration. Never prints cookies, names or response
bodies. Does not alter service settings, existing accounts or official material.
Optional generated PCM exercises real Google streaming; never use student audio.
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

CLIENT_COUNT = 30
CLASS_COUNT = int(os.environ.get('PABASA_BENCHMARK_CLASSES', '3'))
if CLASS_COUNT not in (1, 3):
    raise ValueError('Use one 30-student class or three 10-student classes')
CLASS_SIZE = CLIENT_COUNT // CLASS_COUNT
HOST = os.environ.get('PABASA_BENCHMARK_HOST', 'tupcpabasa.app')
MARKER = 'PABASA_LIVE_CRLA_THIRTY '


def run_speech(students, material_id, settings, report, rows, request, poll_students=None):
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
        try:
            async with connect('wss://' + HOST + '/ws/reading/crla/', origin='https://' + HOST,
                    additional_headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+client['key'],
                        'User-Agent':report['user_agent']}, open_timeout=30, close_timeout=5) as ws:
                await ws.send(json.dumps({'ticket':ticket}))
                message = json.loads(await asyncio.wait_for(ws.recv(), 30))
                assert message.get('type') == 'ready', 'Stream not ready'
                ready.append(True)
                await asyncio.wait_for(go.wait(), 30)
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
                            break
                        if message.get('type') == 'error':
                            raise RuntimeError('Provider or stream failure')
                finally:
                    await sender
        except Exception as exc:
            error_type = type(exc).__name__
        rows.append({'operation':'stream','ms':(time.perf_counter()-start)*1000,
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
            'synthetic_words_per_student':6,'recording_format':'WebM/Opus'}



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
    if not os.environ.get('CLOUD_RUN_EXECUTION') or os.environ.get('PABASA_AUTHORIZED_CAPACITY_TEST') != '30':
        raise RuntimeError('Requires an explicitly authorized disposable 30-client diagnostic job.')
    if not os.environ.get('PABASA_BENCHMARK_PCM_BASE64') and os.environ.get('PABASA_BENCHMARK_PROFILE_ONLY') != '1':
        raise RuntimeError('The full thirty-student test requires a generated speech fixture.')
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    logging.disable(logging.CRITICAL)
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.auth.hashers import make_password
    from django.contrib.sessions.models import Session
    from django.core.management import call_command
    from django.db import connection, connections, transaction
    from django.utils import timezone
    from pabasa_app.system_clock import today as system_today
    from pabasa_app.models import (ActivityLog, Assessment, CalendarEvent, Enrollment, Notification,
        LiveAssessmentSession, Material, School, SchoolCalendar, Section, User)
    call_command('check_migration_readiness', require_recorded=True, verbosity=0)
    call_command('migrate', check=True, verbosity=0)
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise RuntimeError('Live probe requires the verified PostgreSQL configuration.')
    run_id = uuid.uuid4().hex[:12]
    report = {'test_id': run_id, 'clients': CLIENT_COUNT, 'teacher_clients': CLASS_COUNT,
        'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': ('SQL profile only; no concurrent HTTP load. ' if os.environ.get('PABASA_BENCHMARK_PROFILE_ONLY') == '1' else '') + f'30 distinct synthetic enrolled students in {CLASS_COUNT} live CRLA session(s) of {CLASS_SIZE}; HTTPS polling, state updates, completed synthetic snapshots, teacher End Session and post-end authentication. Real Google streaming and recorded uploads from generated speech in the full probe; no browser microphone in this HTTP probe.',
        'user_agent': 'PABASA-authorized-live-crla-thirty-' + run_id,
        'aborted': False, 'waves': []}
    print('PABASA_LIVE_CRLA_THIRTY_START '+json.dumps({'test_id':run_id,'clients':CLIENT_COUNT}),flush=True)
    keys, users, sections, live_ids, clients, rows = [], [], [], [], [], []
    school_id = None
    csrf = secrets.token_hex(32)
    test_password = secrets.token_urlsafe(24)
    test_password_hash = make_password(test_password)
    source_material = Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
    material = None
    calendar = SchoolCalendar.objects.filter(is_active=True).order_by('-id').first()
    if source_material is None or calendar is None:
        raise RuntimeError('Required official CRLA material/current calendar unavailable.')

    def make_user(label, role):
        user = User.objects.create(custom_id=f'CAP-{run_id}-{label}', role=role,
            first_name='Synthetic', last_name='Capacity Test', middle_initial='', suffix='',
            sex='female', birth_month=1, birth_day=1, birth_year=2012,
            email=None, password_hash=test_password_hash, school_record_id=school_id)
        users.append(user.pk)
        return user

    def login(user, live_id):
        store = SessionStore()
        store.update({'user_id': user.pk, 'user_role': user.role, 'pabasa_benchmark':run_id})
        store.set_expiry(600)
        store.create()
        keys.append(store.session_key)
        client = {'user_id': user.pk, 'custom_id':user.custom_id, 'key': store.session_key, 'live_id':live_id,
                  'connection':http.client.HTTPSConnection(HOST, timeout=90)}
        clients.append(client)
        return client

    def request(client, operation, payload=None, barrier=None, network_retry=True):
        if barrier: barrier.wait(timeout=30)
        start = time.perf_counter()
        status, ok, error, data = 0, False, None, {}
        route = f'/api/live-assessment/session/{client["live_id"]}/'
        if operation in ('update', 'complete'): route += 'student-update/'
        if operation == 'ticket': route = '/api/reading/crla-stream/start/'
        if operation == 'evaluate': route = '/api/reading/crla-stream/evaluate/'
        if operation in ('clip','crla_clip'): route = '/api/reading/transcribe/'
        if operation == 'login':
            from urllib.parse import urlencode
            route = '/api/login/'
            payload = urlencode({'custom_id':client['custom_id'],'password':test_password}).encode()
        if operation in ('end', 'start', 'load_batch'): route += 'action/'
        if operation == 'dashboard': route = '/dashboard/assessment/'
        if operation == 'reader': route = f'/dashboard/assessment/reading_ui/word/?official_assessment_id={material.pk}&live=1&live_session_id={client["live_id"]}&countdown=0&crla_stage=words'
        headers = {'Cookie': settings.SESSION_COOKIE_NAME + '=' + client['key'] + '; csrftoken=' + csrf,
            'User-Agent':report['user_agent'], 'X-Requested-With':'XMLHttpRequest',
            'Origin':'https://' + HOST, 'Referer':'https://' + HOST + '/',
            'X-CSRFToken':csrf, 'Content-Type':'application/json'}
        if operation in ('clip','crla_clip'):
            headers.update({'Content-Type':'multipart/form-data; boundary=PabasaGeneratedRecording',
                'X-Pabasa-STT-Provider':'google','X-Pabasa-STT-Model':'chirp_3'})
        if operation == 'login': headers['Content-Type'] = 'application/x-www-form-urlencoded'
        try:
            client['connection'].request('POST' if payload is not None else 'GET', route,
                body=payload if isinstance(payload,bytes) else json.dumps(payload) if payload is not None else None, headers=headers)
            response=client['connection'].getresponse()
            status=response.status
            raw=response.read()
            data=json.loads(raw) if operation not in ('dashboard','reader') else {}
            ok=status==200 and (data.get('success') is True or operation in ('dashboard','reader'))
            if operation=='post_end': ok=ok and data.get('session',{}).get('status')=='ended'
            if not ok: error='UnexpectedStatusOrContent'
        except Exception as exc:
            error=type(exc).__name__
            client['connection'].close()
            client['connection']=http.client.HTTPSConnection(HOST,timeout=90)
            # Match the reader's bounded replay of identical speech after a
            # transport failure. Never retry an HTTP 5xx or hide it as success.
            if (network_retry and status == 0 and operation in ('clip','crla_clip','evaluate')
                    and isinstance(exc,(OSError,http.client.HTTPException))):
                time.sleep(1)
                retried=request(client,operation,payload,network_retry=False)
                retried['transport_retries']=1
                retried['transport_errors']=[error]
                retried['ms']=(time.perf_counter()-start)*1000
                return retried
        return {'operation':operation,'ms':(time.perf_counter()-start)*1000,
                'status':status,'ok':ok,'error_type':error, **({'_ticket':data.get('ticket')} if operation=='ticket' and ok else {}), **({'_result':data} if operation in ('evaluate','clip','crla_clip') and ok else {})}

    def wave(pool, members, operation, payload=None):
        barrier=threading.Barrier(len(members))
        start=dt.datetime.now(dt.timezone.utc).isoformat()
        result=list(pool.map(lambda c:request(c,operation,payload,barrier),members))
        rows.extend(result)
        report['waves'].append({'operation':operation,'started_utc':start,**stats(result)})
        print('PABASA_LIVE_CRLA_THIRTY_WAVE '+json.dumps(report['waves'][-1]),flush=True)
        if any(not r['ok'] for r in result):
            report['aborted']=True
            raise RuntimeError('Benchmark wave failed; stopping before further load.')

    try:
        with transaction.atomic():
            school=School.objects.create(name='Synthetic capacity test '+run_id,code='CAP'+run_id)
            school_id=school.pk
            today=system_today()
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
                        item_type=source_material.item_type,language='English',
                        content_json=source_material.content_json,content_text=source_material.content_text,
                        prompt_text=source_material.prompt_text,type='assessment',is_active=True,status='published',student_access=True)
                material.assigned_sections.add(section)
                members=[]
                for index in range(CLASS_SIZE):
                    student=make_user(f'S{group*CLASS_SIZE+index}','student')
                    section.add_student(student)
                    members.append(student)
                live_id=f'capacity-{run_id}-{group}'
                LiveAssessmentSession.objects.create(id=live_id,teacher=teacher,section=section,
                    material=material,status='waiting',start_at=None,countdown_seconds=0,
                    student_ids=[s.pk for s in members],student_count=CLASS_SIZE,batch_size=10,
                    current_batch=1,total_batches=CLASS_SIZE//10,
                    batch_assignments={str(s.pk):index//10+1 for index,s in enumerate(members)},
                    student_states={str(s.pk):{'status':'reading','progress':0,'connection_status':'connected'} for s in members})
                live_ids.append(live_id)
                teachers.append(login(teacher,live_id))
                students.extend(login(s,live_id) for s in members)
        report['enrolled_students']=Enrollment.objects.filter(student_id__in=users, status='active',is_active=True).count()
        assert len(students)==report['enrolled_students']==CLIENT_COUNT
        if os.environ.get('PABASA_BENCHMARK_PROFILE_ONLY') == '1':
            from collections import defaultdict
            from django.test import Client
            import re
            import traceback
            counts = defaultdict(lambda: {'count':0,'ms':0})
            def profile(execute, sql, params, many, context):
                table = re.search(r'(?:FROM|INTO|UPDATE)\s+"?([a-z_]+)',sql,re.I)
                table = table.group(1) if table else 'other'
                frame = next((f for f in reversed(traceback.extract_stack())
                    if '/pabasa_app/' in f.filename and f.name != 'profile'), None)
                key = table + ':' + (frame.name if frame else 'framework')
                started = time.perf_counter()
                try:
                    return execute(sql,params,many,context)
                finally:
                    counts[key]['count'] += 1
                    counts[key]['ms'] += (time.perf_counter()-started)*1000
            client = Client(raise_request_exception=False)
            client.cookies[settings.SESSION_COOKIE_NAME] = students[0]['key']
            def profile_page():
                counts.clear()
                started = time.perf_counter()
                with connection.execute_wrapper(profile):
                    response = client.get('/dashboard/assessment/',secure=True,HTTP_HOST='tupcpabasa.app')
                return {'status':response.status_code,'elapsed_ms':round((time.perf_counter()-started)*1000,2),
                    'queries':sum(v['count'] for v in counts.values()),
                    'groups':sorted([{'query_source':k,'count':v['count'],'ms':round(v['ms'],2)} for k,v in counts.items()],key=lambda g:-g['ms'])[:20]}
            report['dashboard_profile_before'] = profile_page()
            from pabasa_app.views import _end_live_assessment_session
            from pabasa_app.background_work import completion_work
            evidence={'stage':'completed','temporary_completed':True,'task1_score':0,
                'task2_type':'Task 2L / Rhymes','task2_rhymes_score':0,
                'part1_total_score':0,'learner_experience_rating':3}
            for live in LiveAssessmentSession.objects.filter(pk__in=live_ids):
                live.status='started'
                live.student_states={str(sid):{'status':'completed','progress':1,
                    'elapsed_seconds':6,'recovery_state':evidence} for sid in live.student_ids}
                live.save(update_fields=['status','student_states'])
                _end_live_assessment_session(live)
            assert completion_work.drain(timeout=120)
            report['dashboard_profile_after'] = profile_page()
            return
        with connection.cursor() as cursor:
            cursor.execute('SHOW max_connections')
            report['database_max_connections']=int(cursor.fetchone()[0])
        connections.close_all()
        report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        # All 30 independent students participate in each synchronized wave.
        with cf.ThreadPoolExecutor(max_workers=CLIENT_COUNT) as pool:
            wave(pool,students,'login',{})
            teacher_barrier=threading.Barrier(CLASS_COUNT)
            with cf.ThreadPoolExecutor(max_workers=CLASS_COUNT) as starts:
                start_rows=list(starts.map(lambda t:request(t,'start',{'action':'start','countdown_seconds':0},teacher_barrier),teachers))
                rows.extend(start_rows)
                assert all(r['ok'] for r in start_rows), 'Start session failed'
            time.sleep(11)
            wave(pool,students,'poll')
            # Exercise page rendering before synthetic audio transport.
            wave(pool,students,'dashboard')
            evidence={'stage':'completed','temporary_completed':True,'task1_score':0,
                'task2_type':'Task 2L / Rhymes','task2_rhymes_score':0,
                'part1_total_score':0,'learner_experience_rating':3}
            speech_batches=[]
            for batch_index in range(3 if CLASS_COUNT == 1 else 1):
                active = students[batch_index*10:(batch_index+1)*10] if CLASS_COUNT == 1 else students
                if batch_index:
                    wave(pool,teachers,'load_batch',{'action':'load_next_batch','target_batch':batch_index+1})
                    wave(pool,teachers,'start',{'action':'start','countdown_seconds':0})
                    time.sleep(11)
                    wave(pool,students,'poll')
                wave(pool,active,'reader')
                speech_batches.append(run_speech(active,material.pk,settings,report,rows,request,poll_students=students))
                for round_index in range(3):
                    wave(pool,active,'update',{'status':'reading','progress':(round_index+1)/10,
                        'elapsed_seconds':round_index*2,'recovery_state':{'stage':'words','task1_score':0}})
                    wave(pool,students,'poll')
                    time.sleep(2)
                wave(pool,active,'complete',{'status':'completed','progress':1,'elapsed_seconds':6,'recovery_state':evidence})
            report['speech_batches']=speech_batches
            report['speech']={'simultaneous_ready_streams':max(b['simultaneous_ready_streams'] for b in speech_batches),
                'provider_finals':sum(b['provider_finals'] for b in speech_batches),
                'authorized_evaluations':sum(b['authorized_evaluations'] for b in speech_batches),
                'recorded_uploads':{op:sum(b['recorded_uploads'][op] for b in speech_batches) for op in ('clip','crla_clip')},
                'synthetic_words_per_student':6,'recording_format':'WebM/Opus'}
            # Keep all 30 students polling while the teacher(s) finalize.
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
            wave(pool,students,'dashboard')
            time.sleep(1)
            wave(pool,students,'dashboard')
            # Leave active requests running while optional follow-ups drain.
            for _ in range(10):
                time.sleep(1)
                wave(pool,students,'post_end')
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        report['completed_results']=Assessment.objects.filter(student_id__in=users,material=material,attempt_status='completed').count()
        report['ended_sessions']=LiveAssessmentSession.objects.filter(pk__in=live_ids,status='ended').count()
        report['student_logins_preserved']=Session.objects.filter(session_key__in=[c['key'] for c in students]).count()
        assert report['completed_results']==report['student_logins_preserved']==30
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
        report['cleanup_remaining_materials']=Material.objects.filter(pk=material.pk).count() if material is not None else 0
        report['cleanup_remaining_enrollments']=Enrollment.objects.filter(student_id__in=users).count()
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        report['operations']={name:stats([r for r in rows if r['operation']==name]) for name in sorted({r['operation'] for r in rows})}
        report['total_requests']=len(rows)
        report['failures']=sum(not r['ok'] for r in rows)
        report['transport_retries']=sum(r.get('transport_retries',0) for r in rows)
        print(MARKER+json.dumps(report),flush=True)
    if report['aborted']: raise SystemExit(1)


if __name__=='__main__':
    run()
