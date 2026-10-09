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
                    continue
                frames.append(bytes(request.audio))
                count += 1
                if count in {2, 5}:
                    yield cloud_speech.StreamingRecognizeResponse(results=[{
                        'alternatives': [{'transcript': 'Si Bibo' if count == 2 else 'Si Bibo ay bata.'}],
                        'is_final': count == 5,
                    }])
        return responses()


async def test_application(scope, receive, send):
    path = scope.get('path')
    if scope['type'] == 'http' and (path == '/stream-test/' or path.startswith('/static/')):
        if path == '/stream-test/':
            content = HTML.encode()
            content_type = b'text/html'
        else:
            filename = path.removeprefix('/static/')
            if filename not in {'crla_speech_stream.js', 'crla_pcm_worklet.js'}:
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
    live_google = '--live-google' in sys.argv
    credentials = None
    if live_google:
        cli = r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
        token = subprocess.check_output([cli, 'auth', 'print-access-token'], text=True).strip()
        credentials = Credentials(token=token, quota_project_id=settings.GOOGLE_CLOUD_PROJECT_ID)
        material.language = 'English'
        global HTML
        HTML = HTML.replace('Si Bibo ay bata.', 'The cat sat on the mat.')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(test_application, host='127.0.0.1', port=port,
                                         lifespan='off', ws='websockets-sansio', log_level='error'))
    with override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                           ALLOWED_HOSTS=['127.0.0.1'], DEBUG=True), \
            patch.object(crla_stream, 'authorize', return_value=material), \
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
                   'CRLA_TEST_LIVE': '1' if live_google else '0'}
            script = r'''
const {chromium}=require('playwright');
(async()=>{
  const liveGoogle=process.env.CRLA_TEST_LIVE==='1';
  const args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'];
  if(liveGoogle)args.push('--use-file-for-fake-audio-capture='+require('node:path').join(process.env.TEMP,'pabasa-crla-stream-test.wav'));
  const browser=await chromium.launch({executablePath:process.env.CRLA_CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args});
  try {
    const context=await browser.newContext({permissions:['microphone']});
    await context.addCookies([
      {name:'sessionid',value:process.env.CRLA_TEST_SESSION,url:`http://127.0.0.1:${process.env.CRLA_TEST_PORT}`},
      {name:'csrftoken',value:'a'.repeat(32),url:`http://127.0.0.1:${process.env.CRLA_TEST_PORT}`}]);
    const page=await context.newPage();const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
    await page.goto(`http://127.0.0.1:${process.env.CRLA_TEST_PORT}/stream-test/`);
    await page.click('#start');
    await page.waitForFunction(()=>window.results.length>=1||window.errors.length>0,{},{timeout:15000});
    const state=await page.evaluate(async()=>{
      await live.finish();mic.getTracks().forEach(track=>track.stop());
      return {interims,results:results.map(x=>({complete:x.complete,correct_word_count:x.correct_word_count,stt_model:x.stt_model})),errors};
    });
    if(pageErrors.length||state.errors.length||(!liveGoogle&&state.interims.length!==1)||!state.results[0].complete||state.results[0].correct_word_count!==(liveGoogle?6:4))throw new Error(JSON.stringify({state,pageErrors}));
    console.log('PASS: Chrome microphone -> AudioWorklet PCM -> real Uvicorn WebSocket -> '+(liveGoogle?'live Google':'mock Google')+' -> signed final -> shared HTTP evaluator; '+state.results[0].correct_word_count+' words scored, '+state.interims.length+' interim updates');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
'''
            subprocess.run(['node', '-e', script], env=env, check=True)
            if not live_google:
                assert frames and all(0 < len(frame) <= crla_stream.MAX_FRAME_BYTES for frame in frames)
                assert clients and all(client.transport.close.await_count == 1 for client in clients)
            print('PASS: streaming integration completed with database access forbidden')
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
