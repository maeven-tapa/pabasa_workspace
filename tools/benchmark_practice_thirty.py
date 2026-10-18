"""Opt-in 30-account practice probe; run only in an authorized Cloud Run job.

Uses owned synthetic accounts and materials; prints aggregate evidence only.
The same shared material is completed by all thirty students in each mode.
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

COUNT = 30
HOST = os.environ.get('PABASA_BENCHMARK_HOST', 'tupcpabasa.app')


def run():
    assert os.environ.get('CLOUD_RUN_EXECUTION') and os.environ.get('PABASA_AUTHORIZED_PRACTICE_TEST') == '30'
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth.hashers import make_password
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.db import connections
    from pabasa_app.models import ActivityLog, HuntStarAward, Material, Notification, User
    logging.disable(logging.CRITICAL)
    rid = uuid.uuid4().hex[:12]
    report = dict(test_id=rid, clients=COUNT, started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  user_agent='PABASA-authorized-practice-thirty-' + rid, aborted=False, waves=[], persisted={})
    users, keys, clients, materials, rows = [], [], [], [], []
    csrf = secrets.token_hex(32)
    password = secrets.token_urlsafe(24)
    hashed = make_password(password)
    faults = os.environ.get('PABASA_PRACTICE_FAULTS') == '1'

    def request(c, op, route, payload=None, expected=200, barrier=None, content_type='application/json'):
        if barrier:
            barrier.wait(timeout=90)
        start = time.perf_counter()
        status, data, error = 0, {}, None
        try:
            c['connection'].request('POST' if payload is not None else 'GET', route,
                body=payload if isinstance(payload, bytes) else json.dumps(payload) if payload is not None else None,
                headers={'Cookie': settings.SESSION_COOKIE_NAME + '=' + c['key'] + '; csrftoken=' + csrf,
                    'X-CSRFToken': csrf, 'Origin': 'https://' + HOST, 'Referer': 'https://' + HOST + '/',
                    'User-Agent': report['user_agent'], 'Content-Type': content_type, 'Accept': 'application/json',
                    'X-Pabasa-STT-Provider':'google', 'X-Pabasa-STT-Model':'chirp_3',
                    'X-Requested-With': 'XMLHttpRequest'})
            response = c['connection'].getresponse()
            status = response.status
            raw = response.read()
            if op == 'login' and status == 200:
                from http.cookies import SimpleCookie
                cookies=SimpleCookie()
                for name,value in response.getheaders():
                    if name.lower()=='set-cookie':cookies.load(value)
                if settings.SESSION_COOKIE_NAME in cookies:
                    c['key']=cookies[settings.SESSION_COOKIE_NAME].value
                    keys.append(c['key'])
            if 'json' in response.getheader('Content-Type', ''):
                data = json.loads(raw)
            ok = status == expected and (expected != 200 or data.get('success', True) is True)
        except Exception as exc:
            error = type(exc).__name__
            ok = False
            c['connection'].close()
            c['connection'] = http.client.HTTPSConnection(HOST, timeout=90)
        row = dict(operation=op, status=status, ok=ok, ms=round((time.perf_counter()-start)*1000, 2), error_type=error)
        rows.append(row)
        return data

    def wave(pool, op, route, payload=None, expected=200):
        barrier = threading.Barrier(COUNT)
        futures = [pool.submit(request, c, op, route, payload(c) if callable(payload) else payload, expected, barrier) for c in clients]
        result = [f.result() for f in futures]
        sample = [r for r in rows if r['operation'] == op]
        values = sorted(r['ms'] for r in sample)
        summary = dict(operation=op, count=len(sample), mean_ms=round(statistics.mean(values), 2),
            p95_ms=values[math.ceil(.95*len(values))-1], max_ms=max(values), failures=sum(not r['ok'] for r in sample),
            statuses={str(s):sum(r['status']==s for r in sample) for s in sorted({r['status'] for r in sample})})
        report['waves'].append(summary)
        print('PABASA_PRACTICE_WAVE ' + json.dumps(summary), flush=True)
        return result

    def speech(pool, game, material_id):
        import asyncio
        import base64
        import io
        import av
        from websockets.asyncio.client import connect
        pcm=base64.b64decode(os.environ['PABASA_PRACTICE_PCM_BASE64'],validate=True)
        assert 16000 < len(pcm) < 320000
        tickets=wave(pool,game+'_speech_ticket','/api/reading/material-stream/start/',
            {'purpose':'practice','material_id':material_id,'mode':'word','target_text':'cat','complete_utterance':True})
        assert all(result.get('ticket') for result in tickets)
        async def stream(index, go=None, ready=None, drop=False):
            start=time.perf_counter();token=None;ok=False;error=None
            try:
                async with connect('wss://'+HOST+'/ws/reading/crla/',origin='https://'+HOST,
                    additional_headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+clients[index]['key'],
                        'User-Agent':report['user_agent']},open_timeout=40,close_timeout=5) as ws:
                    await ws.send(json.dumps({'ticket':tickets[index]['ticket']}))
                    message=json.loads(await asyncio.wait_for(ws.recv(),40))
                    assert message.get('type')=='ready'
                    if drop:
                        await ws.send(pcm[:6400]);ok=True
                    else:
                        ready.append(index)
                        while not go.is_set():
                            await ws.send(bytes(6400))
                            try:await asyncio.wait_for(go.wait(),.2)
                            except asyncio.TimeoutError:pass
                        async def send_audio():
                            for offset in range(0,len(pcm),6400):
                                await ws.send(pcm[offset:offset+6400]);await asyncio.sleep(.2)
                            await ws.send('{"type":"finish"}')
                        sender=asyncio.create_task(send_audio())
                        try:
                            while True:
                                message=json.loads(await asyncio.wait_for(ws.recv(),40))
                                if message.get('type')=='finished':
                                    assert message.get('has_speech') and message.get('result_token')
                                    token=message['result_token'];ok=True;break
                                if message.get('type')=='error':raise RuntimeError('Stream failed')
                        finally:
                            await sender
            except Exception as exc:error=type(exc).__name__
            rows.append({'operation':game+('_speech_drop' if drop else '_speech_stream'),'status':101,'ok':ok,
                'ms':round((time.perf_counter()-start)*1000,2),'error_type':error})
            return token
        async def exercise():
            await asyncio.gather(*(stream(i,drop=True) for i in range(0,COUNT,5)))
            go=asyncio.Event();ready=[]
            tasks=[asyncio.create_task(stream(i,go,ready)) for i in range(COUNT)]
            try:
                deadline=time.monotonic()+50
                while len(ready)<COUNT and time.monotonic()<deadline and not any(t.done() for t in tasks):await asyncio.sleep(.05)
                assert len(ready)==COUNT
                go.set();return await asyncio.gather(*tasks)
            finally:
                go.set()
                for task in tasks:
                    if not task.done():task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
        tokens=asyncio.run(exercise());assert all(tokens)
        generated=io.BytesIO()
        with av.open(generated,'w',format='webm') as container:
            encoder=container.add_stream('libopus',rate=16000);encoder.layout='mono';encoder.codec_context.format='s16'
            frame=av.AudioFrame(format='s16',layout='mono',samples=len(pcm)//2);frame.sample_rate=16000;frame.planes[0].update(pcm)
            for packet in encoder.encode(frame):container.mux(packet)
            for packet in encoder.encode(None):container.mux(packet)
        def clip(index,token=True):
            fields={'material_id':str(material_id),'target_text':'cat','mode':'word','language':'English'}
            if token:fields['material_stream_token']=tokens[index]
            boundary='PabasaPracticeGeneratedAudio'
            body=b''.join((f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode() for k,v in fields.items())
            body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="generated.webm"\r\nContent-Type: audio/webm\r\n\r\n').encode()+generated.getvalue()+(f'\r\n--{boundary}--\r\n').encode()
            return body
        barrier=threading.Barrier(COUNT)
        results=list(pool.map(lambda i:request(clients[i],game+'_speech_clip','/api/reading/transcribe/',clip(i),200,barrier,'multipart/form-data; boundary=PabasaPracticeGeneratedAudio'),range(COUNT)))
        assert all(r.get('success') and r.get('complete') and r.get('stt_provider')=='google' for r in results)
        report.setdefault('speech',{})[game]={'simultaneous_ready_streams':COUNT,'successful_evaluations':len(results),'intentional_disconnects':6}
        # Exercise the browser's clip path without a stream result as well.
        if game=='free':
            barrier=threading.Barrier(COUNT)
            results=list(pool.map(lambda i:request(clients[i],'free_direct_clip','/api/reading/transcribe/',clip(i,False),200,barrier,'multipart/form-data; boundary=PabasaPracticeGeneratedAudio'),range(COUNT)))
            assert all(r.get('success') and r.get('complete') and r.get('stt_provider')=='google' for r in results)

    try:
        for n in range(COUNT):
            user = User.objects.create(custom_id='P30-' + rid + '-' + str(n), role='student', first_name='Synthetic',
                last_name='Practice Test', sex='female', birth_month=1, birth_day=1, birth_year=2015,
                email='p30-' + rid + '-' + str(n) + '@example.invalid', password_hash=hashed, grade_level='Grade 1')
            users.append(user.pk)
            session = SessionStore()
            session.update({'user_id':user.pk, 'user_role':'student', 'practice_thirty_probe':rid})
            session.set_expiry(1800)
            session.create()
            keys.append(session.session_key)
            clients.append({'user_id':user.pk, 'custom_id':user.custom_id, 'key':session.session_key,
                'connection':http.client.HTTPSConnection(HOST, timeout=90), 'attempt_id':uuid.uuid4().hex})
        for mode in ('free', 'color', 'hunt'):
            material = Material.objects.create(title='Synthetic practice ' + rid + ' ' + mode, type='practice',
                source_type='shared', is_system_owned=True, status='published', is_active=True, language='English',
                # JSON-only fixture avoids occupying an existing administrator
                # slot; the ordinary reader/evaluator consumes its five items.
                difficulty_level='easy', item_type='word', content_text='',
                content_json={'mode':mode, 'difficulty':'easy', 'level':'level_1', 'items':['cat','dog','sun','moon','star']})
            materials.append(material.pk)
        report['http_started_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        with cf.ThreadPoolExecutor(max_workers=COUNT) as pool:
            wave(pool, 'practice_menu', '/dashboard/practice/?language=English')
            for mode, material_id in zip(('free','color','hunt'), materials):
                wave(pool, mode+'_progression', '/dashboard/practice/progression/'+mode+'/?language=English')
                route='/dashboard/practice/word/?game='+mode+'&difficulty=easy&level=level_1&id='+str(material_id)
                wave(pool, mode+'_reader', route)
                if faults:
                    speech(pool,mode,material_id)
                    assert not Material.objects.get(pk=material_id).content_json.get('student_completions')
                    # Lost connections and expired authentication cannot invent completion.
                    for c in clients:
                        c['connection'].close();c['connection']=http.client.HTTPSConnection(HOST,timeout=90)
                    wave(pool,mode+'_rejoin',route)
                    wave(pool,mode+'_invalid_metrics','/record-assessment-completion/',
                        {'material_id':material_id,'activity_type':'practice','correct_responses':'invalid'},400)
                    wave(pool,mode+'_invalid_body','/record-assessment-completion/',[],400)
                    wave(pool,mode+'_foreign_completion','/record-assessment-completion/',
                        lambda c:{'material_id':material_id,'activity_type':'practice',
                            'student_id':users[(users.index(c['user_id'])+1)%COUNT],'items_completed':5},403)
                    if mode=='hunt':
                        wave(pool,'hunt_forged_identity','/api/practice/hunt/award-stars/',
                            lambda c:{'student_id':users[(users.index(c['user_id'])+1)%COUNT],'level_id':material_id,'attempt_id':c['attempt_id'],'award_type':'word','word_index':0,'transcript':'cat','confidence':.95},403)
                        for word_index,target in enumerate(('cat','dog','sun','moon','star')):
                            award=lambda c:{'student_id':c['user_id'],'level_id':material_id,'attempt_id':c['attempt_id'],
                                'award_type':'word','word_index':word_index,'transcript':target,'confidence':.95}
                            wave(pool,'hunt_word_'+str(word_index),'/api/practice/hunt/award-stars/',award)
                            wave(pool,'hunt_word_replay_'+str(word_index),'/api/practice/hunt/award-stars/',award)
                        bonus=lambda c:{'student_id':c['user_id'],'level_id':material_id,'attempt_id':c['attempt_id'],'award_type':'completion','total_points':10,'percentage':100}
                        wave(pool,'hunt_bonus','/api/practice/hunt/award-stars/',bonus)
                        wave(pool,'hunt_bonus_replay','/api/practice/hunt/award-stars/',bonus)
                        wave(pool,'hunt_conflicting_replay','/api/practice/hunt/award-stars/',
                            lambda c:{'student_id':c['user_id'],'level_id':material_id,'attempt_id':c['attempt_id'],'award_type':'word','word_index':0,'transcript':'wrong','confidence':.95},409)
                        assert HuntStarAward.objects.filter(student_id__in=users).count()==COUNT*6
                        assert all(stars==13 for stars in User.objects.filter(pk__in=users).values_list('available_stars',flat=True))
                        report['hunt_wallets_exact']=COUNT
                payload={'material_id':material_id,'activity_type':'practice','game_mode':mode,
                    'stars_earned':0 if mode=='hunt' else 3, 'items_completed':5,'total_practice_items':5,
                    'total_read_words':5,'total_skipped_words':0,'correct_responses':5,'incorrect_responses':0,
                    'reading_time_seconds':10,'score':100,'attempt_number':1}
                wave(pool, mode+'_complete', '/record-assessment-completion/', payload)
                material=Material.objects.get(pk=material_id)
                completed=material.content_json.get('student_completions',{})
                report['persisted'][mode]=sum(completed.get(str(uid),{}).get('status')=='completed' for uid in users)
                wave(pool, mode+'_completion_replay', '/record-assessment-completion/', payload)
                if faults and mode=='color':
                    wave(pool,'color_lower_replay','/record-assessment-completion/',{**payload,'stars_earned':1})
                    assert all(v['stars_earned']==3 for v in Material.objects.get(pk=material_id).content_json['student_completions'].values())
                if faults:
                    refreshed=Material.objects.get(pk=material_id).content_json.get('student_completions',{})
                    assert sum(refreshed.get(str(uid),{}).get('status')=='completed' for uid in users)==COUNT
                wave(pool, mode+'_return', route)
            if faults:
                from urllib.parse import urlencode
                Session.objects.filter(session_key__in=[c['key'] for c in clients]).delete();connections.close_all()
                wave(pool,'expired_login','/record-assessment-completion/',payload,401)
                barrier=threading.Barrier(COUNT)
                logins=list(pool.map(lambda c:request(c,'login','/api/login/',urlencode({'custom_id':c['custom_id'],'password':password}).encode(),200,barrier,'application/x-www-form-urlencoded'),clients))
                assert all(r.get('success') for r in logins)
                wave(pool,'after_login','/dashboard/practice/?language=English')
                report['expired_logins_recovered']=COUNT
        report['all_thirty_preserved']=all(v==COUNT for v in report['persisted'].values())
    except Exception as exc:
        report['aborted']=True
        report['error_type']=type(exc).__name__
        report['error_locations']=[{'file':os.path.basename(f.filename),'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
    finally:
        report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        # Let owned notification follow-ups settle before deleting their actors.
        time.sleep(5)
        for c in clients:
            c['connection'].close()
        connections.close_all()
        Notification.objects.filter(created_by_id__in=users).delete()
        ActivityLog.objects.filter(actor_id__in=users).delete()
        Session.objects.filter(session_key__in=keys).delete()
        User.objects.filter(pk__in=users).delete()
        Material.objects.filter(pk__in=materials).delete()
        report['remaining_users']=User.objects.filter(pk__in=users).count()
        report['remaining_sessions']=Session.objects.filter(session_key__in=keys).count()
        report['remaining_materials']=Material.objects.filter(pk__in=materials).count()
        report['total_requests']=len(rows)
        report['failures']=sum(not r['ok'] for r in rows)
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        print('PABASA_PRACTICE_RESULT '+json.dumps(report), flush=True)
    if report['aborted'] or report['failures'] or not report.get('all_thirty_preserved'):
        raise SystemExit(1)


if __name__ == '__main__':
    run()
