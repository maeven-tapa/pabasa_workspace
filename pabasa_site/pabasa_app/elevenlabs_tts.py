"""Server-side ElevenLabs narration for CRLA; no alternate-provider fallback."""
import base64
import hashlib
import json
import socket
import time
import urllib.error
import urllib.request

from django.core.cache import cache


CRLA_TTS_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"  # Alice
CRLA_TTS_MODEL_ID = "eleven_v4"
CRLA_TTS_DELIVERY_TAGS = "[filipino teacher accent][slow][Cheerful and Encouraging]"
TTS_REQUEST_BUDGET_SECONDS = 60
TTS_ATTEMPT_TIMEOUT_SECONDS = 20


def normalize_api_keys(value):
    """Accept the legacy single key or an ordered comma/whitespace-separated pool."""
    if isinstance(value, str):
        value = value.replace(',', ' ').split()
    return tuple(dict.fromkeys(str(key).strip() for key in (value or ()) if str(key).strip()))


def _cooldown_cache_key(api_key):
    # Cache keys must not reveal credentials, including with a shared backend.
    digest = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    return f'crla:elevenlabs:cooldown:{CRLA_TTS_VOICE_ID}:{digest}'


class _TtsFailure(RuntimeError):
    def __init__(self, message, *, try_next=True, cooldown=5):
        super().__init__(message)
        self.try_next = try_next
        self.cooldown = cooldown


def _provider_error_code(exc):
    """Read only a bounded error code; never return/log provider message text."""
    try:
        data = json.loads(exc.read(16384))
        if not isinstance(data, dict):
            return ''
        detail = data.get('detail')
        if isinstance(detail, dict):
            return detail.get('status') or detail.get('code') or ''
        return data.get('code') or ''
    except (ValueError, OSError):
        return ''
    finally:
        exc.close()


def _post_audio(payload, api_key, timeout):
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{CRLA_TTS_VOICE_ID}"
        "?output_format=mp3_44100_128",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/mpeg", "xi-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            audio = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        code = _provider_error_code(exc)
        if code in ('quota_exceeded', 'insufficient_credits', 'credit_limit_exceeded'):
            raise _TtsFailure('ElevenLabs TTS quota exhausted for this key.', cooldown=900) from None
        if code == 'detected_unusual_activity':
            raise _TtsFailure('ElevenLabs TTS access is restricted. Check the account.', try_next=False) from None
        # Invalid text/model parameters affect every key; do not repeat them.
        key_error = code in ('invalid_api_key', 'voice_not_found', 'missing_permissions', 'permission_denied')
        if status in (400, 413, 422) and not key_error:
            raise _TtsFailure('ElevenLabs TTS rejected the reading text or synthesis settings.', try_next=False) from None
        messages = {
            401: "Check the server API key.",
            403: "Check the API key permissions and access to the configured voice.",
            404: "The configured voice is unavailable to this account.",
            429: "The request limit or account quota was reached. Please try again later.",
        }
        cooldown = 30 if status == 429 else 300 if status in (401, 403, 404) or key_error else 5
        raise _TtsFailure(
            f"ElevenLabs TTS HTTP {status}: "
            + messages.get(status, "Audio generation failed. Please try again."),
            cooldown=cooldown,
        ) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError):
        raise _TtsFailure("Unable to reach ElevenLabs TTS. Please try again.") from None
    if not audio:
        raise _TtsFailure("ElevenLabs TTS returned no audio.")
    if content_type not in {"audio/mpeg", "audio/mp3"}:
        raise _TtsFailure("ElevenLabs TTS returned an invalid audio response.")
    return base64.b64encode(audio).decode("ascii")


def synthesize_crla_read_aloud_audio(text, api_key, language_code="en-US"):
    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        raise RuntimeError("Text is required for read aloud.")
    api_keys = normalize_api_keys(api_key)
    if not api_keys:
        raise RuntimeError("CRLA read aloud requires ELEVENLABS_API_KEYS or ELEVENLABS_API_KEY on the server.")
    locale = str(language_code or "").lower()
    if locale in {"fil", "fil-ph", "tl", "tl-ph"}:
        language = "fil"
    elif locale == "en" or locale.startswith("en-"):
        language = "en"
    else:
        raise RuntimeError("CRLA read aloud supports Filipino and English only.")
    payload = {
        "text": f"{CRLA_TTS_DELIVERY_TAGS} {clean_text}",
        "model_id": CRLA_TTS_MODEL_ID,
        "language_code": language,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    deadline = time.monotonic() + TTS_REQUEST_BUDGET_SECONDS
    last_error = None
    for key in api_keys:
        cooldown_key = _cooldown_cache_key(key)
        if cache.get(cooldown_key):
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            return _post_audio(payload, key, min(TTS_ATTEMPT_TIMEOUT_SECONDS, remaining))
        except _TtsFailure as exc:
            if not exc.try_next:
                raise RuntimeError(str(exc)) from None
            cache.set(cooldown_key, True, timeout=exc.cooldown)
            last_error = str(exc)
    message = 'All configured ElevenLabs keys are unavailable. Please try again later.'
    if last_error:
        message += f' {last_error}'
    raise RuntimeError(message) from None
