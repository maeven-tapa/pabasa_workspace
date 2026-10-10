"""Authenticated CRLA audio transport; grading stays in the shared reading view."""
import asyncio
import importlib
import json
import logging
import uuid
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import signing
from django.http import HttpRequest, JsonResponse, QueryDict
from django.http.request import validate_host
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)
TICKET_SALT = 'crla-stream-start-v1'
FINAL_SALT = 'crla-stream-final-v1'
PRESCRIBED_RESULT_SALT = 'prescribed-stream-result-v1'
STREAM_PATH = '/ws/reading/crla/'
MAX_FRAME_BYTES = 12800


def session_binding(session):
    return salted_hmac(TICKET_SALT, session.session_key or '').hexdigest()


def authorize(request, material_id):
    from . import views
    user = views._current_user(request)
    if (not user or user.is_archived or user.account_status == 'archived'
            or user.role not in {'student', 'teacher', 'admin'}
            or user.role != request.session.get('user_role')):
        raise PermissionError('Sign in again to use speech recognition.')
    material = views._admin_published_crla(material_id)
    if not material or views._assessment_kind_value(material) != 'crla':
        raise PermissionError('This CRLA assessment is unavailable.')
    blocked = views._enforce_student_access_for_request(request, material=material, json_response=True)
    if blocked:
        raise PermissionError('This assessment is not available for your account.')
    return material


def decode_ticket(token, salt, session, max_age):
    payload = signing.loads(token, salt=salt, max_age=max_age)
    if not constant_time_compare(payload['session'], session_binding(session)):
        raise PermissionError('Speech session expired. Start recording again.')
    return payload


def authorize_prescribed(request, activity_key):
    from . import views
    user = views._current_user(request)
    if (not user or user.is_archived or user.account_status == 'archived'
            or user.role not in {'student', 'teacher', 'admin'}
            or user.role != request.session.get('user_role')):
        raise PermissionError('Sign in again to use speech recognition.')
    activity = views.prescribed_activity(activity_key)
    if not activity:
        activity = next((item for item in views.LEGACY_SESSION_PROGRESS_ACTIVITIES
                         if item['activity_key'] == activity_key), None)
    if not activity:
        raise PermissionError('This prescribed activity is unavailable.')
    if user.role == 'student' and not views._student_can_open_prescribed_activity(user, activity_key):
        raise PermissionError('This activity is not available for your account.')
    return activity


@csrf_protect
@require_POST
def prescribed_stream_ticket(request):
    """Recognition only; the activity's existing endpoint still owns grading."""
    from . import views
    from .reading_stt import language_code_for
    if not getattr(settings, 'CRLA_STREAMING_ENABLED', True):
        return JsonResponse({'success': False, 'error': 'Streaming is disabled.'}, status=503)
    try:
        data = json.loads(request.body)
        activity_key = str(data['activity_key'])
        activity = authorize_prescribed(request, activity_key)
        if data.get('language') and str(data['language']).lower() not in {'filipino', 'tagalog', 'english', 'fil-ph', 'en-ph', 'en-us'}:
            raise ValueError('Invalid language.')
        language = language_code_for(data.get('language') or activity.get('language', 'Filipino'), 'reading')
        if language not in {'fil-PH', 'en-PH', 'en-US'}:
            raise ValueError('Invalid language.')
        model = views._requested_chirp_model(request) or getattr(settings, 'GOOGLE_STT_MODEL', 'chirp_3').strip()
        if language == 'fil-PH' and not views._requested_chirp_model(request):
            model = 'chirp_3'
        if views.uses_knowlez_stt(request) or model != 'chirp_3':
            return JsonResponse({'success': False, 'error': 'This provider uses clip recognition.'}, status=409)
        payload = {'session': session_binding(request.session), 'purpose': 'prescribed',
                   'activity_key': activity_key,
                   'fields': {'language': language, 'mode': 'reading'}}
        return JsonResponse({'success': True, 'ticket': signing.dumps(payload, salt=TICKET_SALT, compress=True),
                             'path': STREAM_PATH})
    except PermissionError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=403)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'success': False, 'error': 'Invalid reading context.'}, status=400)


def prescribed_stream_transcript(request, language_code):
    """Accept only a completed, signed provider utterance for this login/activity."""
    token = request.POST.get('prescribed_stream_token')
    if not token:
        return None
    from . import views
    from .reading_stt import language_code_for
    try:
        result = decode_ticket(token, PRESCRIBED_RESULT_SALT, request.session, 300)
        activity_key = result['activity_key']
        if result.get('purpose') != 'prescribed' or not isinstance(result['transcript'], str):
            raise ValueError('Invalid speech result.')
        if not result['transcript'].strip():
            raise ValueError('No final speech was received.')
        authorize_prescribed(request, activity_key)
        # Workbook endpoints supply the target from their locked current state.
        # Never allow a recognition token to enable the official CRLA path.
        expected = request.POST.get('prescribed_stream_activity')
        if expected != activity_key or (request.POST.get('prescribed_activity_key')
                                       and request.POST['prescribed_activity_key'] != activity_key):
            raise ValueError('Speech activity changed.')
        if '/activity/prescribed/' in request.path:
            path_key = request.path.split('/activity/prescribed/', 1)[1].split('/', 1)[0]
            path_key = {'lesson2-gawain1': 'lesson-2-gawain-1',
                        'lesson3-gawain1': 'lesson-3-gawain-1'}.get(path_key, path_key)
            if path_key != activity_key:
                raise ValueError('Speech activity changed.')
        if (request.POST.get('official_crla_assessment') == '1'
                or request.POST.get('official_assessment_id')
                or views.uses_knowlez_stt(request)
                or views._requested_chirp_model(request) not in {'', 'chirp_3'}
                or language_code_for(result['fields']['language'], 'reading') != language_code):
            raise ValueError('Speech provider or language changed.')
        return result['transcript']
    except (signing.BadSignature, PermissionError, ValueError, TypeError, KeyError) as exc:
        raise PermissionError('Speech session is unavailable. Start recording again.') from exc


@csrf_protect
@require_POST
def crla_stream_ticket(request):
    if not getattr(settings, 'CRLA_STREAMING_ENABLED', True):
        return JsonResponse({'success': False, 'error': 'Streaming is disabled.'}, status=503)
    try:
        data = json.loads(request.body)
        material = authorize(request, int(data['material_id']))
        mode = data['mode']
        target = str(data['target_text']).strip()
        if mode not in {'word', 'sentence', 'paragraph'} or not target or len(target) > 20000:
            raise ValueError('Invalid reading context.')
        # Bind the same displayed item and original material to every final.
        # Client input cannot enable any prescribed activity's write path.
        fields = {
            'official_assessment_id': str(material.pk), 'official_crla_assessment': '1',
            'mode': mode, 'target_text': target, 'language': material.language or data.get('language', ''),
            'crla_rhymes': '1' if data.get('rhymes') else '0',
            'crla_story_reading': '1' if mode == 'paragraph' else '0',
            'crla_sentence_word_scoring': '1' if mode == 'sentence' else '0',
        }
        payload = {'session': session_binding(request.session), 'fields': fields}
        return JsonResponse({'success': True, 'ticket': signing.dumps(payload, salt=TICKET_SALT, compress=True),
                             'path': STREAM_PATH})
    except PermissionError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=403)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'success': False, 'error': 'Invalid reading context.'}, status=400)


@csrf_protect
@require_POST
def crla_stream_evaluate(request):
    """Only signed provider finals may enter the existing clip evaluator."""
    from .views import _reading_transcribe_response
    try:
        data = json.loads(request.body)
        final = decode_ticket(data['final_token'], FINAL_SALT, request.session, 300)
        authorize(request, int(final['fields']['official_assessment_id']))
        fields = dict(final['fields'])
        fields['current_syllable_index'] = str(max(0, int(data.get('current_syllable_index', 0))))
        fields['syllable_context'] = str(data.get('syllable_context', ''))[:80]
        prior = data.get('sentence_word_results', [])
        if not isinstance(prior, list) or len(prior) > 1000:
            raise ValueError('Invalid sentence state.')
        fields['sentence_word_results'] = json.dumps(prior)
        # Materialize Django's JSON request parsing before setting trusted POST
        # fields; otherwise a later FILES access resets POST to an empty dict.
        request.FILES
        request.POST = QueryDict('', mutable=True)
        request.POST.update(fields)
        return _reading_transcribe_response(request, stream_transcript=final['transcript'])
    except (signing.BadSignature, PermissionError):
        return JsonResponse({'success': False, 'error': 'Speech session is unavailable. Start recording again.'}, status=403)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'success': False, 'error': 'Invalid speech result.'}, status=400)


def allowed_origin(scope):
    headers = dict(scope.get('headers', []))
    origin = headers.get(b'origin', b'').decode('ascii', errors='ignore')
    parsed = urlsplit(origin)
    host = headers.get(b'host', b'').decode('ascii', errors='ignore')
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.path:
        return False
    return (origin in settings.CSRF_TRUSTED_ORIGINS
            or (parsed.netloc == host and validate_host(parsed.hostname, settings.ALLOWED_HOSTS)
                and (parsed.scheme == 'https' or settings.DEBUG)))


def socket_session(scope):
    cookies = SimpleCookie()
    cookies.load(dict(scope.get('headers', [])).get(b'cookie', b'').decode('latin1'))
    cookie = cookies.get(settings.SESSION_COOKIE_NAME)
    engine = importlib.import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore(session_key=cookie.value if cookie else None)
    # Load in the sync worker; auth later must not query in the event loop.
    session.get('user_id')
    return session


def validate_socket_ticket(token, session):
    payload = decode_ticket(token, TICKET_SALT, session, 60)
    request = HttpRequest()
    request.method = 'POST'
    request.session = session
    if payload.get('purpose') == 'prescribed':
        authorize_prescribed(request, payload['activity_key'])
    else:
        authorize(request, int(payload['fields']['official_assessment_id']))
    return payload


def speech_credentials():
    from google.oauth2 import service_account
    from .reading_stt import google_stt_credentials
    return google_stt_credentials(service_account, str(settings.GOOGLE_STT_CREDENTIALS_FILE))


async def crla_websocket(scope, receive, send):
    if scope.get('path') != STREAM_PATH or not allowed_origin(scope):
        await send({'type': 'websocket.close', 'code': 1008})
        return
    if not getattr(settings, 'CRLA_STREAMING_ENABLED', True):
        await send({'type': 'websocket.close', 'code': 1013})
        return
    connect = await receive()
    if connect['type'] != 'websocket.connect':
        return
    await send({'type': 'websocket.accept'})
    client = None
    reader = None
    provider = None
    disconnected = False

    async def emit(payload):
        await send({'type': 'websocket.send', 'text': json.dumps(payload)})

    try:
        session = await sync_to_async(socket_session, thread_sensitive=False)(scope)
        first = await asyncio.wait_for(receive(), 5)
        if first['type'] != 'websocket.receive' or not first.get('text') or len(first['text']) > 50000:
            raise ValueError('A speech ticket is required.')
        payload = await sync_to_async(validate_socket_ticket, thread_sensitive=False)(json.loads(first['text'])['ticket'], session)
        from google.api_core.client_options import ClientOptions
        from google.cloud.speech_v2 import SpeechAsyncClient
        from google.cloud.speech_v2.types import cloud_speech
        from .reading_stt import language_code_for
        location = settings.GOOGLE_STT_LOCATION
        client = SpeechAsyncClient(
            credentials=await sync_to_async(speech_credentials, thread_sensitive=False)(),
            client_options=ClientOptions(api_endpoint=f'{location}-speech.googleapis.com'),
        )
        queue = asyncio.Queue(maxsize=50)
        fields = payload['fields']
        config = cloud_speech.StreamingRecognizeRequest(
            recognizer=f'projects/{settings.GOOGLE_CLOUD_PROJECT_ID}/locations/{location}/recognizers/_',
            streaming_config=cloud_speech.StreamingRecognitionConfig(
                config=cloud_speech.RecognitionConfig(
                    explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                        encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=16000, audio_channel_count=1),
                    language_codes=[language_code_for(fields['language'], fields['mode'])], model='chirp_3'),
                streaming_features=cloud_speech.StreamingRecognitionFeatures(interim_results=True),
            ),
        )

        async def requests():
            yield config
            while True:
                audio = await queue.get()
                if audio is None:
                    return
                yield cloud_speech.StreamingRecognizeRequest(audio=audio)

        async def read_audio():
            nonlocal disconnected
            while True:
                message = await asyncio.wait_for(receive(), 60)
                if message['type'] == 'websocket.disconnect':
                    disconnected = True
                    await queue.put(None)
                    return
                audio = message.get('bytes')
                if audio is not None:
                    if not audio or len(audio) > MAX_FRAME_BYTES or len(audio) % 2:
                        raise ValueError('Invalid PCM audio frame.')
                    await asyncio.wait_for(queue.put(audio), 2)
                elif message.get('text') == '{"type":"finish"}':
                    await queue.put(None)
                    return
                else:
                    raise ValueError('Invalid speech message.')

        async def recognize():
            stream_id = uuid.uuid4().hex
            sequence = 0
            utterance = []
            transcript_size = 0
            responses = await client.streaming_recognize(requests=requests(), retry=None, timeout=260)
            await emit({'type': 'ready'})
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = result.alternatives[0].transcript.strip()
                    if not transcript:
                        continue
                    if result.is_final:
                        if payload.get('purpose') == 'prescribed':
                            transcript_size += len(transcript)
                            if transcript_size > 20000:
                                raise ValueError('Speech result exceeded the limit.')
                            utterance.append(transcript)
                            # Provisional display only; no grading until the entire
                            # voiced utterance and the provider stream are flushed.
                            await emit({'type': 'interim', 'transcript': ' '.join(utterance)})
                            continue
                        sequence += 1
                        final = {**payload, 'transcript': transcript, 'id': f'{stream_id}:{sequence}'}
                        await emit({'type': 'final', 'id': final['id'], 'transcript': transcript,
                                    'final_token': signing.dumps(final, salt=FINAL_SALT, compress=True)})
                    else:
                        await emit({'type': 'interim', 'transcript': transcript})
            if not disconnected:
                finished = {'type': 'finished'}
                if payload.get('purpose') == 'prescribed':
                    finished['has_speech'] = bool(utterance)
                    finished['result_token'] = signing.dumps(
                        {**payload, 'transcript': ' '.join(utterance)},
                        salt=PRESCRIBED_RESULT_SALT, compress=True)
                await emit(finished)

        reader = asyncio.create_task(read_audio())
        provider = asyncio.create_task(recognize())
        done, _ = await asyncio.wait((reader, provider), timeout=250, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise TimeoutError('Rotate the speech stream before its limit.')
        for task in done:
            task.result()
        if disconnected:
            return
        if reader in done:
            await asyncio.wait_for(provider, 10)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Do not log tickets, transcripts, or credentials.
        logger.warning('CRLA streaming ended with %s', type(exc).__name__)
        if not disconnected:
            await emit({'type': 'error', 'error': 'Live speech connection interrupted. Please restart the microphone.'})
    finally:
        for task in (reader, provider):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(*(t for t in (reader, provider) if t), return_exceptions=True)
        if client:
            await client.transport.close()
        if not disconnected:
            await send({'type': 'websocket.close', 'code': 1000})
