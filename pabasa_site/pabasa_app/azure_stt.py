"""Server-only Azure Speech adapter for prescribed activity recordings."""

import json
import re

import requests
from django.conf import settings


class AzureSpeechError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def uses_azure_stt(request):
    return request.headers.get('X-Pabasa-STT-Provider', '').strip().lower() == 'azure'


def transcribe_azure_audio(audio, language_code):
    """Accept browser recordings directly, without exposing keys to the browser."""
    key = settings.AZURE_SPEECH_KEY
    region = settings.AZURE_SPEECH_REGION.lower()
    if not key or not re.fullmatch(r'[a-z0-9-]+', region):
        raise AzureSpeechError(
            'Microsoft Azure Speech is not configured. Ask your administrator to '
            'configure Azure Speech, or turn off Microsoft Azure in Audio Settings.',
            status=503,
        )
    if not audio.size:
        raise AzureSpeechError('No audio was recorded. Please try again.', status=400)
    if audio.size > 12 * 1024 * 1024:
        raise AzureSpeechError('The recording is too large. Please record a shorter clip.', status=413)

    url = (f'https://{region}.api.cognitive.microsoft.com/speechtotext/'
           'transcriptions:transcribe?api-version=2025-10-15')
    try:
        response = requests.post(
            url,
            headers={'Ocp-Apim-Subscription-Key': key},
            files={'audio': ('recording', audio.read(), audio.content_type or 'audio/webm')},
            data={'definition': json.dumps({'locales': [language_code]})},
            timeout=(5, 12),
            allow_redirects=False,
        )
    except requests.RequestException:
        # Never return provider exception details, credentials, or response bodies.
        raise AzureSpeechError('Microsoft Azure Speech could not be reached. Please try again.') from None

    if response.status_code != 200:
        if response.status_code in (401, 403):
            message = 'Microsoft Azure Speech could not authenticate. Ask your administrator to check its configuration.'
        elif response.status_code == 429:
            message = 'Microsoft Azure Speech is busy. Please try again shortly.'
        else:
            message = 'Microsoft Azure Speech could not transcribe this recording. Please try again.'
        raise AzureSpeechError(message)
    try:
        phrases = response.json()['combinedPhrases']
        if not isinstance(phrases, list) or any(
            not isinstance(phrase, dict) or not isinstance(phrase.get('text'), str)
            for phrase in phrases
        ):
            raise ValueError('Invalid phrases')
        transcript = ' '.join(phrase['text'].strip() for phrase in phrases).strip()
    except (ValueError, KeyError, TypeError):
        raise AzureSpeechError('Microsoft Azure Speech returned an invalid result. Please try again.') from None
    return transcript, 'azure_fast', ''
