"""Opt-in live Google probe called only from the disposable concurrency fixture.

Set PABASA_LIVE_GOOGLE_AUDIO to the known synthetic English test WAV when running
tests_live_crla_concurrency. Uses real Google Speech and normal API billing, never
production student data. No token or signed speech result is printed or saved.
"""
import array
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import patch
import wave


def run(students, login_keys, material_id):
    from django.conf import settings
    from django.db import close_old_connections
    from django.test import Client
    from django.urls import reverse
    from google.oauth2.credentials import Credentials
    from pabasa_app import crla_stream
    from pabasa_app.models import Material

    database = Path(settings.DATABASES['default']['NAME']).resolve()
    if (settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3'
            or not database.parent.name.startswith('pabasa-live-concurrency-')
            or len(students) != 20):
        raise RuntimeError('This probe requires the isolated twenty-student test fixture.')
    target = 'The cat sat on the mat.'
    audio_path = Path(os.environ['PABASA_LIVE_GOOGLE_AUDIO'])
    with wave.open(str(audio_path), 'rb') as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise ValueError('Synthetic input must be mono 16-bit PCM WAV.')
        rate = audio.getframerate()
        samples = array.array('h', audio.readframes(audio.getnframes()))
    # Match the real AudioWorklet's mono 16 kHz wire format. Synthetic input
    # comes from a known local speech-synthesis fixture, never a student file.
    pcm = array.array('h')
    for index in range(int(len(samples) * 16000 / rate)):
        at = index * rate / 16000
        left = int(at)
        right = min(left + 1, len(samples) - 1)
        pcm.append(round(samples[left] + (samples[right] - samples[left]) * (at - left)))
    raw = pcm.tobytes()
    frames = [raw[offset:offset + 6400] for offset in range(0, len(raw), 6400)]
    cli = r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
    token = subprocess.check_output([cli, 'auth', 'print-access-token'], text=True).strip()
    credentials = Credentials(token=token, quota_project_id=settings.GOOGLE_CLOUD_PROJECT_ID)
    original_language = Material.objects.get(pk=material_id).language
    Material.objects.filter(pk=material_id).update(language='English')

    def ticket_for(student):
        close_old_connections()
        try:
            client = Client()
            client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
            response = client.post(reverse('crla_stream_ticket'), json.dumps({
                'material_id': material_id, 'mode': 'sentence', 'target_text': target,
            }), content_type='application/json')
            assert response.status_code == 200, 'Synthetic student ticket rejected'
            return response.json()['ticket']
        finally:
            close_old_connections()

    async def stream_for(student, ticket):
        incoming, ready = asyncio.Queue(), asyncio.Event()
        finals, errors = [], []
        await incoming.put({'type': 'websocket.connect'})
        await incoming.put({'type': 'websocket.receive', 'text': json.dumps({'ticket': ticket})})
        async def send(message):
            if message['type'] != 'websocket.send':
                return
            data = json.loads(message['text'])
            if data['type'] == 'ready':
                ready.set()
            elif data['type'] == 'final':
                finals.append(data['final_token'])
            elif data['type'] == 'error':
                errors.append(data['error'])
        async def produce():
            await asyncio.wait_for(ready.wait(), 20)
            for frame in frames:
                await incoming.put({'type': 'websocket.receive', 'bytes': frame})
                await asyncio.sleep(0.2)
            await incoming.put({'type': 'websocket.receive', 'text': '{"type":"finish"}'})
        scope = {'path': crla_stream.STREAM_PATH, 'headers': [
            (b'origin', b'https://testserver'), (b'host', b'testserver'),
            (b'cookie', (settings.SESSION_COOKIE_NAME + '=' + login_keys[student.pk]).encode()),
        ]}
        await asyncio.wait_for(asyncio.gather(
            crla_stream.crla_websocket(scope, incoming.get, send), produce()), 45)
        return finals, errors

    def evaluate(item):
        student, finals = item
        close_old_connections()
        try:
            client = Client()
            client.cookies[settings.SESSION_COOKIE_NAME] = login_keys[student.pk]
            prior = []
            for final in finals:
                response = client.post(reverse('crla_stream_evaluate'), json.dumps({
                    'final_token': final, 'sentence_word_results': prior,
                }), content_type='application/json')
                assert response.status_code == 200, 'Signed Google final rejected'
                data = response.json()
                assert data['success'] and data['stt_provider'] == 'google'
                assert data['stt_model'] == 'chirp_3' and data['language_code'] == 'en-PH'
                prior = data['word_results']
            assert data['complete'] and data['correct_word_count'] == 6, 'Synthetic speech accuracy check failed'
            return 200
        finally:
            close_old_connections()

    async def all_streams(tickets):
        return await asyncio.gather(*(stream_for(student, ticket) for student, ticket in zip(students, tickets)))

    started = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=20) as executor:
            tickets = list(executor.map(ticket_for, students))
        with patch.object(crla_stream, 'speech_credentials', return_value=credentials), \
                patch.object(crla_stream.logger, 'warning') as warnings:
            outcomes = asyncio.run(all_streams(tickets))
        successful = sum(bool(finals) and not errors for finals, errors in outcomes)
        error_types = [call.args[1] for call in warnings.call_args_list if len(call.args) > 1]
        assert successful == 20, (f'Live Google streams with usable finals: {successful}/20; '
                                  f'server exception types: {error_types}')
        finals = [result for result, _ in outcomes]
        with ThreadPoolExecutor(max_workers=20) as executor:
            assert list(executor.map(evaluate, zip(students, finals))) == [200] * 20
        print('LIVE_GOOGLE_TWENTY: 20 independent enrolled student sessions, 20 overlapping real Chirp 3 streams, '
              '20 authorized evaluations; six synthetic English words scored for every student; '
              f'elapsed_seconds={time.monotonic() - started:.3f}')
    finally:
        Material.objects.filter(pk=material_id).update(language=original_language)
