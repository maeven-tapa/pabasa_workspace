"""Local Chrome tests with synthetic microphone audio, mocked Google, and no DB writes."""
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
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core.asgi import get_asgi_application
from django.db.backends.utils import CursorWrapper
from django.template.loader import render_to_string
from django.test import override_settings
from google.cloud.speech_v2.types import cloud_speech
import uvicorn
from pabasa_app import crla_stream, views
from pabasa_site import asgi

material = SimpleNamespace(pk=12, language='English', content_json={})
session = SessionStore()
session.update({'user_id': 1, 'user_role': 'student'})
session.set_expiry(settings.SESSION_COOKIE_AGE)
session.save()
frames, clients = [], []


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
                    assert list(request.streaming_config.config.language_codes) == ['en-PH']
                    continue
                frames.append(bytes(request.audio))
                count += 1
                if count in {2, 5}:
                    yield cloud_speech.StreamingRecognizeResponse(results=[{
                        'alternatives': [{'transcript': 'cat'}], 'is_final': count == 5}])
        return responses()


async def application(scope, receive, send):
    path = scope.get('path', '')
    if scope['type'] == 'http' and path.startswith('/browser-test/'):
        game = path.strip('/').split('/')[-1]
        fixture = {'id': 'practice-12', 'raw_id': 12, 'title': 'Synthetic test', 'type': 'word',
                   'game_mode': game, 'difficulty': 'easy', 'level': 'level_1', 'language': 'English',
                   'items': ['cat', 'dog'], 'content': 'cat\ndog'}
        template = 'pabasa_app/practice_word_page.html'
        context = {
            'practice_materials': [fixture], 'student_available_stars': 0, 'mascot_animation_frames': {},
            'request': SimpleNamespace(GET={'game': game, 'difficulty': 'easy'}),
            'csrf_token': 'a' * 32,
        }
        if game == 'supplementary':
            template = 'pabasa_app/reading_word_page.html'
            context.update({'custom_material_launch_data_json': json.dumps({
                'id': 'material-12', 'raw_id': 12, 'title': 'Synthetic supplementary',
                'item_type': 'word', 'language': 'English', 'items': ['cat', 'dog'],
                'content_json': {'template_source': 'template', 'template_title': 'Reading Practice'},
            }), 'nav_role': 'student'})
        content = render_to_string(template, context).encode()
        content_type, status = b'text/html', 200
    elif scope['type'] == 'http' and path.startswith('/static/'):
        asset = ROOT / 'pabasa_site/pabasa_app/static' / path.removeprefix('/static/')
        if asset.suffix == '.js' and asset.is_file() and asset.resolve().is_relative_to(ROOT):
            content, content_type, status = asset.read_bytes(), b'application/javascript', 200
        else:
            content, content_type, status = b'', b'text/plain', 204
    elif scope['type'] == 'http' and path in {'/api/practice/hunt/award-stars/', '/record-assessment-completion/'}:
        content, content_type, status = b'{"success":true,"attempt_stars":2}', b'application/json', 200
    else:
        await asgi.application(scope, receive, send)
        return
    await send({'type': 'http.response.start', 'status': status, 'headers': [(b'content-type', content_type)]})
    await send({'type': 'http.response.body', 'body': content})


def forbidden_sql(*args, **kwargs):
    raise AssertionError('Browser streaming test attempted a database query or write')


def main():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(application, host='127.0.0.1', port=port,
                                         lifespan='off', ws='websockets-sansio', log_level='warning'))
    with override_settings(ALLOWED_HOSTS=['127.0.0.1'], CSRF_TRUSTED_ORIGINS=[f'http://127.0.0.1:{port}'],
                           DEBUG=True, CRLA_STREAMING_ENABLED=True,
                           SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                           SESSION_SAVE_EVERY_REQUEST=False,
                           SECURE_SSL_REDIRECT=False, CSRF_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False), \
            patch.object(crla_stream, 'authorize_material', return_value=material), \
            patch.object(crla_stream, 'speech_credentials', return_value=None), \
            patch.object(views, '_enforce_student_access_for_request', return_value=None), \
            patch.object(views, 'transcribe_audio_bytes_with_model', side_effect=AssertionError('Unexpected clip fallback')), \
            patch('google.cloud.speech_v2.SpeechAsyncClient', GoogleStream), \
            patch.object(CursorWrapper, 'execute', forbidden_sql):
        asgi.django_application = get_asgi_application()
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.05)
            assert server.started
            script = r'''
const {chromium} = require('playwright');
(async () => {
 const origin = `http://127.0.0.1:${process.env.STREAM_TEST_PORT}`;
 const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
   headless:true,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try {
  for (const game of ['free','color','hunt','supplementary']) {
   const context = await browser.newContext({permissions:['microphone']});
   await context.addCookies([{name:'sessionid',value:process.env.STREAM_TEST_SESSION,url:origin},
     {name:'csrftoken',value:'a'.repeat(32),url:origin}]);
   const page = await context.newPage(), errors = [], requests = [];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',route=>route.request().url().startsWith(origin) ? route.continue() : route.abort());
   await page.addInitScript(() => {
    window.__microphones = [];
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async options => {const mic=await original(options); __microphones.push(mic); return mic;};
   });
   const evaluationPath = game === 'supplementary' ? '/api/reading/material-stream/evaluate/' : '/api/reading/transcribe/';
   page.on('request',request => {if(request.url().endsWith(evaluationPath)) requests.push(request.postData());});
   await page.goto(`${origin}/browser-test/${game}/?id=practice-12&game=${game}&difficulty=easy&level=level_1`);
   if(errors.length) throw Error(`${game}: initialization: ${errors.join('; ')}`);
   const button = game === 'supplementary' ? '#btnStartReading' : game === 'free' ? '#scrollRecordBtn' : '#recordBtn';
   const evaluated = page.waitForResponse(response => response.url().endsWith(evaluationPath), {timeout:15000});
   await page.click(button);
   const response = await evaluated, result = await response.json();
   if(!response.ok() || !result.success || !result.complete) throw Error(`${game}: reading was not accepted`);
   if(errors.length) throw Error(`${game}: ${errors.join('; ')}`);
   if(!requests.length || !requests[0].includes(game === 'supplementary' ? 'final_token' : 'material_stream_token')) throw Error(`${game}: unsigned/clip-only evaluation`);
   await page.click(game === 'supplementary' ? '#btnToggleMic' : button);
   await page.waitForFunction(() => __microphones.length && __microphones.every(mic=>mic.getTracks().every(track=>track.readyState==='ended')));
   await context.close();
   console.log(`PASS: actual ${game} practice reader -> microphone -> PCM -> WebSocket -> signed complete result -> existing scoring`);
  }
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
'''
            subprocess.run(['node', '-e', script], env={**os.environ,
                'STREAM_TEST_PORT': str(port), 'STREAM_TEST_SESSION': session.session_key}, check=True)
            assert frames and all(0 < len(frame) <= crla_stream.MAX_FRAME_BYTES for frame in frames)
            assert clients and all(client.transport.close.await_count == 1 for client in clients)
            print('PASS: browser integration completed with database access forbidden')
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
