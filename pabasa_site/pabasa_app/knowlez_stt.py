"""Server-only Knowlez STT adapter (https://api-stt.knowlez.com/docs).

AZURE_SPEECH_KEY and the legacy 'azure' selection remain supported so existing
Cloud Run secret mappings and saved browser preferences keep working.
"""

import base64

import requests
from django.conf import settings


class KnowlezSpeechError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def uses_knowlez_stt(request):
    return request.headers.get('X-Pabasa-STT-Provider', '').strip().lower() in {'knowlez', 'azure'}


def transcribe_knowlez_audio(audio, language_code):
    """Accept browser recordings directly, without exposing keys to the browser."""
    key = settings.AZURE_SPEECH_KEY
    if not key:
        raise KnowlezSpeechError(
            'Knowlez speech recognition is not configured. Ask your administrator '
            'to configure it, or turn off Knowlez in Audio Settings.',
            status=503,
        )
    if not audio.size:
        raise KnowlezSpeechError('No audio was recorded. Please try again.', status=400)
    if audio.size > 12 * 1024 * 1024:
        raise KnowlezSpeechError('The recording is too large. Please record a shorter clip.', status=413)

    # Knowlez expects ISO-639-1 codes, not Azure/Google locale identifiers.
    language = 'tl' if language_code.lower().startswith(('fil', 'tl')) else 'en'
    mime = (audio.content_type or 'audio/webm').split(';')[0].lower()
    extension = {'audio/ogg': 'ogg', 'audio/wav': 'wav', 'audio/x-wav': 'wav',
                 'audio/mp4': 'm4a', 'video/mp4': 'mp4', 'audio/mpeg': 'mp3',
                 'audio/flac': 'flac'}.get(mime, 'webm')
    try:
        response = requests.post(
            'https://api-stt.knowlez.com/v1/stt/transcribe',
            headers={'X-API-Key': key},
            json={'audio_base64': base64.b64encode(audio.read()).decode('ascii'),
                  'filename': f'recording.{extension}', 'language': language},
            timeout=(5, 25),
            allow_redirects=False,
        )
    except requests.RequestException:
        # Never return provider exception details, credentials, or response bodies.
        raise KnowlezSpeechError('Knowlez speech recognition could not be reached. Please try again.') from None

    if response.status_code not in (200, 201):
        if response.status_code in (401, 403):
            message = 'Knowlez could not authenticate. Ask your administrator to check the STT API key and subscription.'
        elif response.status_code == 429:
            message = 'Knowlez has reached its usage limit or is busy. Please try again later.'
        else:
            message = 'Knowlez could not transcribe this recording. Please try again.'
        raise KnowlezSpeechError(message)
    try:
        result = response.json()
        transcript = result['text']
        if not isinstance(transcript, str):
            raise ValueError('Invalid transcript')
    except (ValueError, KeyError, TypeError):
        raise KnowlezSpeechError('Knowlez returned an invalid transcription result. Please try again.') from None
    return transcript.strip(), 'knowlez_stt', ''
