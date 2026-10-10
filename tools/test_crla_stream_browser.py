"""Local Chrome/ASGI integration using synthetic speech and a mocked Google stream.

Run with a Python environment containing uvicorn/websockets and NODE_PATH pointing
to an installed Playwright package. No database or cloud writes are performed.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pabasa_site'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()

from django.conf import settings
from django.core.asgi import get_asgi_application
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import override_settings
from django.db.backends.utils import CursorWrapper
from google.cloud.speech_v2.types import cloud_speech
from google.cloud.speech_v2 import SpeechAsyncClient
from google.oauth2.credentials import Credentials
import uvicorn

from pabasa_app import crla_stream, views
from pabasa_site.asgi import application as real_application
from pabasa_site import asgi

frames = []
clients = []
progress_requests = []
english_prescribed = False
material = SimpleNamespace(pk=12, language='Filipino')
session = SessionStore()
session.update({'user_id': 1, 'user_role': 'admin'})
session.set_expiry(settings.SESSION_COOKIE_AGE)
session.save()

HTML = '''<!doctype html><html><head><script src="/static/crla_speech_stream.js"></script></head>
<body><button id="start">Start microphone</button><span id="partial"></span><span id="result"></span>
<script>
window.__PABASA_CRLA_PCM_WORKLET__='/static/crla_pcm_worklet.js';
window.results=[];window.interims=[];window.errors=[];
document.getElementById('start').onclick=async()=>{
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  window.mic=stream;
  window.live=new CrlaSpeechStream({csrf:()=>document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1],
    fields:{material_id:12,target_text:'Si Bibo ay bata.',mode:'sentence'},
    onInterim:text=>{interims.push(text);document.getElementById('partial').textContent=text},
    onFinal:async message=>{
      const response=await fetch('/api/reading/crla-stream/evaluate/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1]},body:JSON.stringify({final_token:message.final_token})});
      const data=await response.json();if(!response.ok||!data.success)throw new Error(data.error);
      results.push(data);document.getElementById('result').textContent=data.transcript;
    },onError:error=>errors.push(error.message)});
  await live.start(stream);
};
</script></body></html>'''


class GoogleStream:
    def __init__(self, **kwargs):
        self.transport = SimpleNamespace(close=AsyncMock())
        clients.append(self)

    async def streaming_recognize(self, requests, **kwargs):
        async def responses():
            count = 0
            async for request in requests:
                if request.streaming_config:
                    assert request.streaming_config.config.model == 'chirp_3'
                    assert request.streaming_config.config.explicit_decoding_config.sample_rate_hertz == 16000
                    if english_prescribed:
                        assert list(request.streaming_config.config.language_codes) == ['en-PH']
                    continue
                frames.append(bytes(request.audio))
                count += 1
                if count in {2, 5}:
                    yield cloud_speech.StreamingRecognizeResponse(results=[{
                        'alternatives': [{'transcript': ('The cat' if count == 2 else 'The cat wore a hat.')
                                          if english_prescribed else ('Si Bibo' if count == 2 else 'Si Bibo ay bata.')}],
                        'is_final': count == 5,
                    }])
        return responses()


async def test_application(scope, receive, send):
    path = scope.get('path')
    if scope['type'] == 'http' and path == '/stream-test/progress/':
        body = b''
        while True:
            message = await receive()
            body += message.get('body', b'')
            if not message.get('more_body'):
                break
        progress_requests.append(json.loads(body))
        content = json.dumps({'success': True, 'progress': {'state': {
            'phase': 'reading', 'item_index': 0, 'verse_index': 1, 'attempts': 0, 'selected': []}}}).encode()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'application/json')]})
        await send({'type': 'http.response.body', 'body': content})
        return
    if scope['type'] == 'http' and (path == '/stream-test/' or path.startswith('/static/')):
        if path == '/stream-test/':
            content = HTML.encode()
            content_type = b'text/html'
        else:
            filename = path.removeprefix('/static/')
            if filename not in {'crla_speech_stream.js', 'crla_pcm_worklet.js', 'basahin.js',
                                'basahin_button.js', 'prescribed_rhyming_verses_lesson27_activity1.js'}:
                raise ValueError('Unknown test asset')
            content = (ROOT / 'pabasa_site/pabasa_app/static/pabasa_app/js' / filename).read_bytes()
            content_type = b'application/javascript'
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', content_type)]})
        await send({'type': 'http.response.body', 'body': content})
    else:
        await real_application(scope, receive, send)


def forbidden_sql(*args, **kwargs):
    raise AssertionError('Streaming integration test attempted a database query/write')


def main():
    global english_prescribed
    english_prescribed = '--prescribed-english' in sys.argv
    live_google = '--live-google' in sys.argv
    prescribed = '--prescribed' in sys.argv or english_prescribed
    if prescribed and live_google:
        raise ValueError('The prescribed integration mode uses synthetic audio and the mocked provider only.')
    credentials = None
    if prescribed:
        global HTML
        HTML = '''<!doctype html><html lang="fil"><head>
<script>window.__PABASA_PRESCRIBED_ACTIVITY__='lesson-13-gawain-3';
window.__PABASA_CRLA_PCM_WORKLET__='/static/crla_pcm_worklet.js';</script>
<script src="/static/crla_speech_stream.js"></script><script src="/static/basahin.js"></script></head>
<body><button id="start">Basahin</button><span id="partial"></span><span id="result"></span>
<script>
window.results=[];window.interims=[];window.errors=[];window.evaluations=0;
window.addEventListener('basahin:state',e=>{
  if(e.detail.state==='interim') {interims.push(e.detail.transcript);document.getElementById('partial').textContent='Hearing: '+e.detail.transcript;}
});
document.getElementById('start').onclick=async()=>{
  try {
    const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async options=>{const stream=await original(options);window.mic=stream;return stream;};
    const result=await Basahin.read({target_text:'Si Bibo ay bata.',language:'Filipino',mode:'sentence'},
      {onProgress:()=>evaluations++,button:document.getElementById('start')});
    results.push(result);
    document.getElementById('result').textContent=result.transcript;
  }catch(e){errors.push(e.message);}
};
</script></body></html>'''
    if english_prescribed:
        fixture = {
            'activity_key': 'lesson-27-gawain-1', 'transcribe_url': '/api/reading/transcribe/',
            'progress_url': '/stream-test/progress/',
            'items': [{'title': 'The Cat in the Hat', 'lines': [
                {'text': 'The cat wore a hat.', 'words': []}, {'text': 'He sat on a mat.', 'words': []}]}],
        }
        HTML = '''<!doctype html><html lang="en"><head>
<script>window.__PABASA_CRLA_PCM_WORKLET__='/static/crla_pcm_worklet.js';</script>
<script src="/static/crla_speech_stream.js"></script><script src="/static/basahin_button.js"></script>
<script src="/static/basahin.js"></script></head><body><div id="app"></div>
<script id="prescribed-activity-data" type="application/json">''' + json.dumps(fixture) + '''</script>
<script>
window.results=[];window.interims=[];window.errors=[];window.evaluations=0;
window.addEventListener('basahin:state',e=>{if(e.detail.state==='interim')interims.push(e.detail.transcript);});
const originalMic=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia=async options=>{const stream=await originalMic(options);window.mic=stream;return stream;};
const originalRead=Basahin.read;
window.Basahin={...Basahin,read:async (...args)=>{try{const result=await originalRead(...args);results.push(result);return result;}
  catch(e){errors.push(e.message);throw e;}}};
const originalFetch=window.fetch;
window.fetch=async (url,options)=>{
  if(url==='/api/reading/transcribe/') {
    evaluations++;
    if(!options.body.get('prescribed_stream_token')||options.body.get('prescribed_activity_key')!=='lesson-27-gawain-1')
      throw Error('English Read did not send its signed streaming result.');
  }
  return originalFetch(url,options);
};
window.Audio=class extends EventTarget {
  play(){queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();}
  pause(){this.dispatchEvent(new Event('pause'));}
};
</script><script src="/static/prescribed_rhyming_verses_lesson27_activity1.js"></script></body></html>'''
    if live_google:
        cli = r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
        token = subprocess.check_output([cli, 'auth', 'print-access-token'], text=True).strip()
        credentials = Credentials(token=token, quota_project_id=settings.GOOGLE_CLOUD_PROJECT_ID)
        material.language = 'English'
        HTML = HTML.replace('Si Bibo ay bata.', 'The cat sat on the mat.')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(test_application, host='127.0.0.1', port=port,
                                         lifespan='off', ws='websockets-sansio', log_level='error'))
    with override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                           ALLOWED_HOSTS=['127.0.0.1'], DEBUG=True), \
            patch.object(crla_stream, 'authorize', return_value=material), \
            patch.object(crla_stream, 'authorize_prescribed', return_value={}), \
            patch.object(crla_stream, 'speech_credentials', return_value=credentials), \
            patch.object(views, '_enforce_student_access_for_request', return_value=None), \
            patch('google.cloud.speech_v2.SpeechAsyncClient', SpeechAsyncClient if live_google else GoogleStream), \
            patch.object(CursorWrapper, 'execute', forbidden_sql):
        asgi.django_application = get_asgi_application()
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started
            env = {**os.environ, 'CRLA_TEST_PORT': str(port), 'CRLA_TEST_SESSION': session.session_key,
                   'CRLA_TEST_LIVE': '1' if live_google else '0', 'CRLA_TEST_PRESCRIBED': '1' if prescribed else '0',
                   'CRLA_TEST_ENGLISH': '1' if english_prescribed else '0'}
            audio_file = None
            if prescribed:
                import math
                import struct
                import tempfile
                import wave
                handle = tempfile.NamedTemporaryFile(prefix='pabasa-prescribed-synthetic-', suffix='.wav', delete=False)
                audio_file = Path(handle.name)
                handle.close()
                with wave.open(str(audio_file), 'wb') as wav:
                    wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                    wav.writeframes(b''.join(struct.pack('<h', int(14000 * math.sin(2 * math.pi * 440 * i / 16000))
                                                        if 16000 <= i < 35200 else 0) for i in range(96000)))
                env['CRLA_TEST_SYNTHETIC'] = str(audio_file)
            script = r'''
const {chromium}=require('playwright');
(async()=>{
  const liveGoogle=process.env.CRLA_TEST_LIVE==='1';
  const prescribed=process.env.CRLA_TEST_PRESCRIBED==='1';
  const english=process.env.CRLA_TEST_ENGLISH==='1';
  const args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'];
  if(prescribed)args.push('--use-file-for-fake-audio-capture='+process.env.CRLA_TEST_SYNTHETIC+'%noloop');
  if(liveGoogle)args.push('--use-file-for-fake-audio-capture='+require('node:path').join(process.env.TEMP,'pabasa-crla-stream-test.wav'));
  const browser=await chromium.launch({executablePath:process.env.CRLA_CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args});
  try {
    const context=await browser.newContext({permissions:['microphone']});
    await context.addCookies([
      {name:'sessionid',value:process.env.CRLA_TEST_SESSION,url:`http://127.0.0.1:${process.env.CRLA_TEST_PORT}`},
      {name:'csrftoken',value:'a'.repeat(32),url:`http://127.0.0.1:${process.env.CRLA_TEST_PORT}`}]);
    const page=await context.newPage();const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
    await page.goto(`http://127.0.0.1:${process.env.CRLA_TEST_PORT}/stream-test/`);
    await page.click(english?'#record-verse':'#start');
    await page.waitForFunction(()=>window.results.length>=1||window.errors.length>0,{},{timeout:15000});
    if(english)await page.waitForFunction(()=>document.querySelector('.lesson27-prompt')?.textContent.includes('verse 2'),{},{timeout:5000});
    const state=await page.evaluate(async()=>{
      if(window.live)await live.finish();
      const tracksEnded=mic.getTracks().every(track=>track.readyState==='ended');
      mic.getTracks().forEach(track=>track.stop());
      return {interims,results:results.map(x=>({complete:x.complete,correct_word_count:x.correct_word_count,cursor:x.current_syllable_index,targetCount:x.target_syllable_count,stt_model:x.stt_model,audioBytes:x.audio_blob?.size})),errors,tracksEnded,evaluations:window.evaluations};
    });
    if(pageErrors.length||state.errors.length||(!liveGoogle&&state.interims.length!==(prescribed?2:1))||!state.results[0].complete||state.results[0].correct_word_count!==(liveGoogle?6:english?5:4))throw new Error(JSON.stringify({state,pageErrors}));
    if(prescribed&&(!state.tracksEnded||state.evaluations!==1||!state.results[0].audioBytes))throw new Error('Prescribed recording lifecycle failed: '+JSON.stringify(state));
    console.log('PASS: '+(prescribed?'Basahin -> ':'')+'Chrome microphone -> AudioWorklet PCM -> real Uvicorn WebSocket -> '+(liveGoogle?'live Google':'mock Google')+' -> signed final -> shared HTTP evaluator; '+(prescribed?'one completed attempt':state.results[0].correct_word_count+' words scored')+', '+state.interims.length+' provisional updates');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
'''
            try:
                subprocess.run(['node', '-e', script], env=env, check=True)
            finally:
                if audio_file:
                    audio_file.unlink()
            if not live_google:
                assert frames and all(0 < len(frame) <= crla_stream.MAX_FRAME_BYTES for frame in frames)
                assert clients and all(client.transport.close.await_count == 1 for client in clients)
            if english_prescribed:
                assert progress_requests == [{'action': 'verse_read', 'item_index': 0, 'verse_index': 0, 'success': True}]
                print('PASS: actual English Read button streams en-PH and saves exactly one completed verse')
            print('PASS: streaming integration completed with database access forbidden')
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
