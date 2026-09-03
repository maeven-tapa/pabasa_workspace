import base64
from functools import lru_cache
import html
import json
import os
from pathlib import Path
import re
import socket
import unicodedata
import urllib.error
import urllib.request

from num2words import num2words
import pronouncing


MARUNGKO_PHRASE_HINTS = [
    "ma", "me", "mi", "mo", "mu",
    "sa", "se", "si", "so", "su",
    "ba", "be", "bi", "bo", "bu",
    "ta", "te", "ti", "to", "tu",
    "ka", "ke", "ki", "ko", "ku",
    "la", "le", "li", "lo", "lu",
    "na", "ne", "ni", "no", "nu",
    "ga", "ge", "gi", "go", "gu",
    "ra", "re", "ri", "ro", "ru",
    "pa", "pe", "pi", "po", "pu",
    "mama", "basa", "bata", "masa", "mimi",
]


VOWELS = set("aeiou")
SPOKEN_VOWELS = {
    "a": "a", "ah": "a", "ay": "a", "aye": "a",
    "e": "e", "eh": "e", "ee": "e",
    "i": "i", "eye": "i",
    "o": "o", "oh": "o", "owe": "o",
    "u": "u", "uh": "u", "oo": "u", "you": "u",
}
VOWEL_SOUND_ALIASES = {
    "a": {"a", "ah", "ay"},
    "e": {"e", "eh"},
    "i": {"i", "e", "ee", "y", "iy", "ie"},
    "o": {"o", "oh", "ow", "oy"},
    "u": {"u", "oo", "ew", "uy"},
}

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
}


_FILIPINO_UNDER_TWENTY = {
    0: "sero",
    1: "isa",
    2: "dalawa",
    3: "tatlo",
    4: "apat",
    5: "lima",
    6: "anim",
    7: "pito",
    8: "walo",
    9: "siyam",
    10: "sampu",
    11: "labing-isa",
    12: "labindalawa",
    13: "labintatlo",
    14: "labing-apat",
    15: "labinlima",
    16: "labing-anim",
    17: "labimpito",
    18: "labingwalo",
    19: "labinsiyam",
}
_FILIPINO_TENS = {
    20: "dalawampu",
    30: "tatlumpu",
    40: "apatnapu",
    50: "limampu",
    60: "animnapu",
    70: "pitumpu",
    80: "walumpu",
    90: "siyamnapu",
}
_FILIPINO_COUNTING_PREFIX = {
    1: "isang",
    2: "dalawang",
    3: "tatlong",
    4: "apat na",
    5: "limang",
    6: "anim na",
    7: "pitong",
    8: "walong",
    9: "siyam na",
}


def filipino_number_to_words(number):
    """Convert a whole number to commonly used Filipino/Tagalog words."""
    number = int(number)
    if number < 0:
        return f"negatibong {filipino_number_to_words(abs(number))}"
    if number < 20:
        return _FILIPINO_UNDER_TWENTY[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        base = _FILIPINO_TENS[tens * 10]
        return base if not ones else f"{base}'t {_FILIPINO_UNDER_TWENTY[ones]}"
    if number < 1_000:
        hundreds, remainder = divmod(number, 100)
        base = f"{_FILIPINO_COUNTING_PREFIX[hundreds]} daan"
        return base if not remainder else f"{base} at {filipino_number_to_words(remainder)}"

    for value, singular, plural in (
        (1_000_000_000, "isang bilyon", "bilyon"),
        (1_000_000, "isang milyon", "milyon"),
        (1_000, "isang libo", "libo"),
    ):
        if number >= value:
            count, remainder = divmod(number, value)
            if count == 1:
                base = singular
            elif count < 10:
                base = f"{_FILIPINO_COUNTING_PREFIX[count]} {plural}"
            else:
                base = f"{filipino_number_to_words(count)} {plural}"
            return base if not remainder else f"{base} at {filipino_number_to_words(remainder)}"
    return str(number)


def word_numbers_in_transcript(transcript, language_code="en-US"):
    """Return a display copy of an STT transcript with integer digits worded."""
    if not transcript:
        return transcript
    normalized_language = str(language_code or "").lower()
    is_filipino = normalized_language.startswith(("fil", "tl")) or "tagalog" in normalized_language
    is_english = normalized_language.startswith("en")
    if not is_english and not is_filipino:
        return transcript

    def replace_number(match):
        raw_number = match.group(0)
        try:
            number = int(raw_number.replace(",", ""))
            return filipino_number_to_words(number) if is_filipino else num2words(number, lang="en")
        except (NotImplementedError, OverflowError, ValueError):
            return raw_number

    integer_pattern = r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?![\w.]|\.\d)"
    return re.sub(integer_pattern, replace_number, transcript)


for tens_word, tens_value in (
    ("twenty", 20),
    ("thirty", 30),
    ("forty", 40),
    ("fifty", 50),
    ("sixty", 60),
    ("seventy", 70),
    ("eighty", 80),
    ("ninety", 90),
):
    for ones_word, ones_value in (
        ("one", 1),
        ("two", 2),
        ("three", 3),
        ("four", 4),
        ("five", 5),
        ("six", 6),
        ("seven", 7),
        ("eight", 8),
        ("nine", 9),
    ):
        NUMBER_WORDS[f"{tens_word}{ones_word}"] = str(tens_value + ones_value)

for number in range(0, 100):
    filipino_words = re.sub(r"[^a-z0-9]", "", filipino_number_to_words(number).lower())
    NUMBER_WORDS[filipino_words] = str(number)


def language_code_for(language="", mode=""):
    value = f"{language} {mode}".lower()
    if any(marker in value for marker in ("fil", "tagalog", "marungko")):
        return "fil-PH"
    return "en-PH"


def phrase_hints_for(language="", mode=""):
    return MARUNGKO_PHRASE_HINTS if language_code_for(language, mode) == "fil-PH" else []


def target_phrase_hints(target_text, language_code):
    """Bias Filipino STT toward the displayed words and their syllables."""
    if str(language_code).lower() != "fil-ph":
        return []

    hints = []
    for word in ReadingMatcher.readable_words(target_text or ""):
        normalized = ReadingMatcher.normalize_word(word)
        if not normalized:
            continue
        hints.append(normalized)
        hints.extend(ReadingMatcher.split_syllables(normalized))
    return list(dict.fromkeys(hints))[:100]


def target_aware_syllable_stitching(
    target_text,
    current_syllable_index,
    prior_context,
    transcript,
    language_code,
):
    """Join short Filipino STT results only while they prefix the target word."""
    if str(language_code).lower() != "fil-ph":
        return transcript, "", False

    matcher = ReadingMatcher(target_text, current_syllable_index, language_code)
    if matcher.current_word_index >= len(matcher.words):
        return transcript, "", False

    target_word = matcher.normalize_word(matcher.words[matcher.current_word_index])
    current_parts = matcher.normalize_spoken_words(transcript)[:6]
    prior_parts = matcher.normalize_spoken_words(prior_context)[-5:]
    if not target_word or not current_parts:
        return transcript, "", False

    combined_parts = (prior_parts + current_parts)[-6:]
    combined_word = "".join(combined_parts)
    current_word = "".join(current_parts)

    if prior_parts and combined_word == target_word:
        return " ".join(combined_parts), "", True
    if prior_parts and target_word.startswith(combined_word):
        return transcript, " ".join(combined_parts), False
    if current_word == target_word:
        return transcript, "", False
    if target_word.startswith(current_word):
        return transcript, " ".join(current_parts), False
    return transcript, "", False


def syllable_context_metrics(target_text, current_syllable_index, context, language_code):
    """Count TASS progress against target syllables, not STT token boundaries."""
    if str(language_code).lower() != "fil-ph":
        return 0, 0, 0

    matcher = ReadingMatcher(target_text, current_syllable_index, language_code)
    if matcher.current_word_index >= len(matcher.words):
        return 0, 0, 0

    target_word = matcher.normalize_word(matcher.words[matcher.current_word_index])
    target_syllables = matcher.split_syllables(target_word)
    context_word = "".join(matcher.normalize_spoken_words(context))
    if not target_syllables or not context_word or not target_word.startswith(context_word):
        return 0, len(target_syllables), 0

    matched_count = 0
    cumulative = ""
    for syllable in target_syllables:
        cumulative += syllable
        if len(cumulative) <= len(context_word):
            matched_count += 1
        else:
            break

    progress = round((matched_count / len(target_syllables)) * 100, 2)
    return matched_count, len(target_syllables), progress


def v1_model_for_language(model, language_code):
    requested_model = (model or "").strip()
    normalized_language = str(language_code or "").lower()
    if normalized_language == "en-ph":
        if requested_model in {"", "chirp_3", "latest_short", "latest_long"}:
            return "command_and_search"
    if normalized_language == "fil-ph":
        if requested_model in {"chirp_3", "latest_short", "latest_long"}:
            return ""
    if requested_model == "chirp_3":
        return "latest_short" if normalized_language.startswith("en-") else ""
    return requested_model or ("latest_short" if normalized_language.startswith("en-") else "")


def transcribe_audio_bytes(
    audio_bytes,
    api_key,
    language_code="en-US",
    phrase_hints=None,
    model="",
    project_id="",
    location="global",
    mime_type="audio/webm",
    credentials_file="",
):
    transcript, _model_used, _fallback_reason = transcribe_audio_bytes_with_model(
        audio_bytes,
        api_key,
        language_code,
        phrase_hints,
        model,
        project_id,
        location,
        mime_type,
        credentials_file,
    )
    return transcript


def transcribe_audio_bytes_with_model(
    audio_bytes,
    api_key,
    language_code="en-US",
    phrase_hints=None,
    model="",
    project_id="",
    location="global",
    mime_type="audio/webm",
    credentials_file="",
):
    fallback_reason = ""
    if model == "chirp_3":
        try:
            transcript = transcribe_audio_bytes_v2_chirp3(
                audio_bytes,
                language_code,
                project_id,
                location,
                credentials_file,
            )
            if transcript:
                return transcript, "chirp_3", ""
        except Exception as exc:
            fallback_reason = summarize_stt_error(exc)
            if not api_key:
                raise

    v1_model = v1_model_for_language(model, language_code)
    return transcribe_audio_bytes_v1(
        audio_bytes,
        api_key,
        language_code,
        phrase_hints,
        v1_model,
        mime_type,
    ), "stt_v1", fallback_reason


def summarize_stt_error(exc):
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 180:
        message = f"{message[:177]}..."
    return message or exc.__class__.__name__


def transcribe_audio_bytes_v2_chirp3(
    audio_bytes,
    language_code,
    project_id,
    location,
    credentials_file,
    timeout_seconds=12,
):
    if not project_id:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT_ID in settings.py to use Chirp 3.")
    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Install google-cloud-speech to use Chirp 3.") from exc

    credentials = google_stt_credentials(service_account, credentials_file)
    client_options = None
    if location and location != "global":
        client_options = ClientOptions(api_endpoint=f"{location}-speech.googleapis.com")
    client = SpeechClient(credentials=credentials, client_options=client_options)

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=[language_code],
        model="chirp_3",
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{project_id}/locations/{location or 'global'}/recognizers/_",
        config=config,
        content=audio_bytes,
    )
    response = client.recognize(request=request, timeout=timeout_seconds)
    if not response.results:
        return ""
    alternatives = response.results[0].alternatives
    if not alternatives:
        return ""
    return alternatives[0].transcript.strip()


def google_stt_credentials(service_account, credentials_file):
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials_path = Path(credentials_file or "")
    if credentials_path.exists():
        return service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=scopes,
        )

    encoded_json = os.environ.get("GOOGLE_STT_SERVICE_ACCOUNT_JSON_B64", "").strip()
    if encoded_json:
        try:
            credentials_info = json.loads(base64.b64decode(encoded_json).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("GOOGLE_STT_SERVICE_ACCOUNT_JSON_B64 is not valid Base64 JSON.") from exc
        return service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=scopes,
        )

    raw_json = os.environ.get("GOOGLE_STT_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        try:
            credentials_info = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_STT_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
        return service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=scopes,
        )

    # Cloud Run supplies Application Default Credentials through its service
    # account, avoiding a long-lived service-account key in the container.
    try:
        from google.auth import default
        credentials, _ = default(scopes=scopes)
        return credentials
    except Exception as exc:
        raise RuntimeError(
            f"Google service account file was not found: {credentials_path}. "
            "Configure a Cloud Run service account or GOOGLE_STT_SERVICE_ACCOUNT_JSON."
        ) from exc


def transcribe_audio_bytes_v1(
    audio_bytes,
    api_key,
    language_code,
    phrase_hints,
    model,
    mime_type,
    timeout_seconds=12,
):
    config = {
        "languageCode": language_code,
        "enableAutomaticPunctuation": str(language_code).lower().startswith("en-"),
        "maxAlternatives": 3,
    }
    if "webm" in (mime_type or "").lower():
        config.update({"encoding": "WEBM_OPUS", "sampleRateHertz": 48000})
    elif "ogg" in (mime_type or "").lower():
        config.update({"encoding": "OGG_OPUS", "sampleRateHertz": 48000})
    else:
        config.update({"encoding": "LINEAR16", "sampleRateHertz": 16000})
    if model:
        config["model"] = model
    if phrase_hints:
        config["speechContexts"] = [{"phrases": phrase_hints, "boost": 20.0}]

    payload = {
        "config": config,
        "audio": {"content": base64.b64encode(audio_bytes).decode("utf-8")},
    }
    return _post_google_stt(
        f"https://speech.googleapis.com/v1p1beta1/speech:recognize?key={api_key}",
        payload,
        "Google STT",
        timeout_seconds=timeout_seconds,
    )


def synthesize_read_aloud_audio(text, api_key="", language_code="en-US", speaking_rate=0.95, prosody_rate="92%", credentials_file=None):
    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        raise RuntimeError("Text is required for read aloud.")

    # Google TTS provides Filipino voices under the fil-PH locale.  The reading
    # APIs pass Tagalog and Filipino materials in with this language code, so
    # preserve it instead of always using the English assessment voice.
    if str(language_code or "").lower() in {"fil", "fil-ph", "tl", "tl-ph"}:
        tts_language = "fil-PH"
        voice_name = "fil-ph-Neural2-A"
    else:
        tts_language = "en-US"
        # Neural2 supports the SSML and pace controls used by this teaching
        # prompt; Chirp HD voices do not support those controls.
        voice_name = "en-US-Neural2-F"
    teaching_ssml = (
        '<speak>'
        f'<prosody rate="{prosody_rate}" pitch="+0st" volume="medium">'
        f'{html.escape(clean_text)}'
        '</prosody>'
        '</speak>'
    )
    payload = {
        "input": {"ssml": teaching_ssml},
        "voice": {
            "languageCode": tts_language,
            "name": voice_name,
            "ssmlGender": "FEMALE",
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate,
            "pitch": 0,
            "volumeGainDb": 0,
        },
    }
    headers = None
    tts_url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    if api_key:
        tts_url = f"{tts_url}?key={api_key}"
    else:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError("Install Google authentication libraries to use service-account TTS.") from exc
        credentials = google_stt_credentials(service_account, credentials_file)
        credentials.refresh(Request())
        headers = {"Authorization": f"Bearer {credentials.token}"}

    return _post_google_tts(tts_url, payload, headers=headers)


def _post_google_tts(url, payload, headers=None):
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            error_message = json.loads(details).get("error", {}).get("message", details)
        except json.JSONDecodeError:
            error_message = details or exc.reason
        raise RuntimeError(f"Google TTS HTTP {exc.code}: {error_message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while contacting Google TTS: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Google TTS returned an invalid response.") from exc

    audio_content = result.get("audioContent", "")
    if not audio_content:
        raise RuntimeError("Google TTS returned no audio.")
    return audio_content


def _post_google_stt(url, payload, label, timeout_seconds=12):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            error_message = json.loads(details).get("error", {}).get("message", details)
        except json.JSONDecodeError:
            error_message = details or exc.reason
        raise RuntimeError(f"{label} HTTP {exc.code}: {error_message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while contacting {label}: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"{label} timed out. Please keep reading and try again.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned an invalid response.") from exc

    if not result.get("results"):
        return ""
    alternatives = result["results"][0].get("alternatives", [])
    if not alternatives:
        return ""
    return alternatives[0].get("transcript", "").strip()


def _normalize_story_word_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", " ").replace("–", " ").replace("…", " ").replace("`", "'")
    text = text.lower()
    text = re.sub(r"[^a-z0-9'\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _story_alignment_tokens(text):
    normalized = _normalize_story_word_text(text)
    if not normalized:
        return []
    return [token for token in re.split(r"\s+", normalized) if token]


def _story_words_are_equivalent(expected_word, recognized_word):
    if expected_word is None or recognized_word is None:
        return False
    expected = _normalize_story_word_text(expected_word)
    recognized = _normalize_story_word_text(recognized_word)
    if not expected or not recognized:
        return False
    return expected == recognized


def _story_two_token_candidate(expected_word, first_token, second_token):
    """Return conservative evidence for one Story word split into two STT tokens."""
    expected = _normalize_story_word_text(expected_word).replace(" ", "")
    first = _normalize_story_word_text(first_token).replace(" ", "")
    second = _normalize_story_word_text(second_token).replace(" ", "")
    if len(expected) < 4 or len(first) < 2 or len(second) < 2:
        return None
    combined = first + second
    if len(combined) != len(expected):
        return None
    if combined == expected:
        return {"combined": combined, "correct": True, "cost": 0}
    expected_parts = ReadingMatcher.split_syllables(expected)
    if len(expected_parts) != 2 or [len(first), len(second)] != [len(part) for part in expected_parts]:
        return None
    distance = ReadingMatcher.edit_distance(combined, expected, 2)
    if distance > 2:
        return None
    return {
        "combined": combined,
        "correct": False,
        # A narrowly justified two-token substitution must beat two unrelated
        # one-token substitutions plus a trailing omission in cursor mode.
        "cost": 0 if distance == 0 else 0.9,
    }


def story_word_states_from_results(expected_text, recognized_text=None, total_words=None, word_results=None):
    """Return per-word visual states using the same attempted-then-advance pattern.

    The student can resolve one target word at a time. Correct attempts become
    green/read; miscues become red/read; untouched words remain pending. The
    comparison stops at the first mismatch, mirroring the other reading modes.
    """
    if recognized_text is not None:
        expected_words = _story_alignment_tokens(expected_text)
        recognized_words = _story_alignment_tokens(recognized_text)
        total = max(0, int(total_words or len(expected_words)))
        states = ["pending"] * total
        target_index = 0
        for spoken_word in recognized_words:
            if target_index >= len(expected_words) or target_index >= len(states):
                break
            expected_word = expected_words[target_index]
            if _story_words_are_equivalent(expected_word, spoken_word):
                states[target_index] = "correct"
                target_index += 1
                continue
            states[target_index] = "miscue"
            break
        return states

    resolved = ["pending"] * max(0, int(total_words or 0))
    if not isinstance(word_results, list):
        return resolved
    for item in word_results:
        if not isinstance(item, dict):
            continue
        result = str(item.get("result") or "").strip().lower()
        if result not in {"correct", "miscue"}:
            continue
        expected_index = item.get("expected_index")
        try:
            expected_index = int(expected_index)
        except (TypeError, ValueError):
            continue
        if expected_index < 0 or expected_index >= len(resolved):
            continue
        resolved[expected_index] = result
    return resolved


def align_story_transcript(expected_text, recognized_text, language_code="en-US", start_word_index=None):
    """Align a story transcript against the expected text at the word level.

    This is intentionally conservative: it tolerates punctuation/case/spacing
    artifacts but does not apply broad fuzzy matching to silently accept
    materially different words. The output preserves sequential order and records
    omissions, insertions, and substitutions at the word level.
    """
    all_expected_words = _story_alignment_tokens(expected_text)
    recognized_words = _story_alignment_tokens(recognized_text)
    cursor_relative = start_word_index is not None
    absolute_word_offset = min(max(0, int(start_word_index or 0)), len(all_expected_words))
    expected_words = all_expected_words[absolute_word_offset:] if cursor_relative else all_expected_words
    if cursor_relative and recognized_words:
        expected_words = expected_words[:len(recognized_words)]
    if not expected_words and not recognized_words:
        return {
            "expected_text": str(expected_text or ""),
            "recognized_text": str(recognized_text or ""),
            "language_code": language_code,
            "expected_words": [],
            "recognized_words": [],
            "total_words": 0,
            "correct_words": 0,
            "miscues": 0,
            "accuracy": 0.0,
            "word_results": [],
        }

    rows = len(expected_words) + 1
    cols = len(recognized_words) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        dp[i][0] = i
    for j in range(1, cols):
        dp[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            expected_word = expected_words[i - 1]
            recognized_word = recognized_words[j - 1]
            substitution_cost = 0 if _story_words_are_equivalent(expected_word, recognized_word) else 1
            candidates = [
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + substitution_cost,
            ]
            if j >= 2:
                multi_token = _story_two_token_candidate(
                    expected_word,
                    recognized_words[j - 2],
                    recognized_words[j - 1],
                )
                if multi_token:
                    candidates.append(dp[i - 1][j - 2] + multi_token["cost"])
            dp[i][j] = min(candidates)

    word_results = []
    insertion_count = 0
    i = len(expected_words)
    j = len(recognized_words)
    while i > 0 or j > 0:
        if i > 0 and j >= 2:
            expected_word = expected_words[i - 1]
            multi_token = _story_two_token_candidate(
                expected_word,
                recognized_words[j - 2],
                recognized_words[j - 1],
            )
            if multi_token and dp[i][j] == dp[i - 1][j - 2] + multi_token["cost"]:
                word_results.append({
                    "expected": expected_word,
                    "recognized": f"{recognized_words[j - 2]} {recognized_words[j - 1]}",
                    "result": "correct" if multi_token["correct"] else "miscue",
                    "type": "multi_token_correct" if multi_token["correct"] else "multi_token_substitution",
                    "expected_index": i - 1,
                    "recognized_index": j - 2,
                    "recognized_start_index": j - 2,
                    "recognized_end_index": j,
                })
                i -= 1
                j -= 2
                continue
        if i > 0 and j > 0:
            expected_word = expected_words[i - 1]
            recognized_word = recognized_words[j - 1]
            substitution_cost = 0 if _story_words_are_equivalent(expected_word, recognized_word) else 1
            if dp[i][j] == dp[i - 1][j - 1] + substitution_cost:
                if _story_words_are_equivalent(expected_word, recognized_word):
                    word_results.append({
                        "expected": expected_word,
                        "recognized": recognized_word,
                        "result": "correct",
                        "type": "correct",
                        "expected_index": i - 1,
                        "recognized_index": j - 1,
                    })
                else:
                    word_results.append({
                        "expected": expected_word,
                        "recognized": recognized_word,
                        "result": "miscue",
                        "type": "substitution",
                        "expected_index": i - 1,
                        "recognized_index": j - 1,
                    })
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            word_results.append({
                "expected": expected_words[i - 1],
                "recognized": None,
                "result": "miscue",
                "type": "omission",
                "expected_index": i - 1,
                "recognized_index": None,
            })
            i -= 1
            continue
        if j > 0:
            recognized_word = recognized_words[j - 1]
            if i > 0:
                expected_word = expected_words[i - 1]
                has_future_match = any(
                    _story_words_are_equivalent(expected_word, later_word)
                    for later_word in recognized_words[: j - 1]
                )
                if (
                    not _story_words_are_equivalent(expected_word, recognized_word)
                    and has_future_match
                ):
                    insertion_count += 1
                    j -= 1
                    continue
            word_results.append({
                "expected": None,
                "recognized": recognized_word,
                "result": "miscue",
                "type": "insertion",
                "expected_index": None,
                "recognized_index": j - 1,
            })
            j -= 1

    word_results.reverse()
    if cursor_relative:
        while word_results and word_results[-1].get("type") == "omission":
            word_results.pop()
        for item in word_results:
            if item.get("expected_index") is not None:
                item["expected_index"] += absolute_word_offset
    correct_words = sum(1 for item in word_results if item.get("result") == "correct")
    miscues = sum(1 for item in word_results if item.get("result") == "miscue") + insertion_count
    total_words = max(len(all_expected_words), 0)
    accuracy = (correct_words / total_words * 100.0) if total_words else 0.0
    return {
        "expected_text": str(expected_text or ""),
        "recognized_text": str(recognized_text or ""),
        "language_code": language_code,
        "expected_words": all_expected_words,
        "recognized_words": recognized_words,
        "total_words": total_words,
        "correct_words": correct_words,
        "miscues": miscues,
        "accuracy": round(accuracy, 2),
        "word_results": word_results,
    }


def analyze_reading(target_text, current_syllable_index=0, transcript="", language_code="en-US", strict_rhyme=False):
    matcher = ReadingMatcher(target_text, current_syllable_index, language_code, strict_rhyme=strict_rhyme)
    matched = matcher.advance_for_spoken_text(transcript)
    return matcher.payload(matched, transcript)


def analyze_sentence_reading(target_text, transcript="", prior_results=None, language_code="en-US", debug=False):
    """Resolve a sentence sequentially while allowing an immediate self-correction."""
    matcher = ReadingMatcher(target_text, 0, language_code)
    spoken_words = matcher.normalize_spoken_words(transcript)
    debug_trace = []
    if debug:
        debug_trace.append({
            "prefix": "[SENTENCE DEBUG][STT]",
            "raw_transcript": str(transcript or ""),
            "normalized_transcript": " ".join(spoken_words),
            "recognized_words": spoken_words,
            "interim": False,
            "final": True,
        })
    results = []
    prior_by_index = {}
    for item in prior_results or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("expected_index"))
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(matcher.words):
            prior_by_index[index] = dict(item)

    for index, expected in enumerate(matcher.words):
        previous = prior_by_index.get(index, {})
        status = str(previous.get("result") or "").lower()
        if status in {"correct", "miscue"}:
            results.append(previous)
        else:
            results.append({
                "expected": matcher.normalize_word(expected),
                "recognized": previous.get("recognized"),
                "result": "pending",
                "type": "pending",
                "expected_index": index,
                "recognized_index": None,
                "correct": False,
                "self_corrected": False,
                "miscue": False,
                "points": 0,
                "attempt_count": int(previous.get("attempt_count") or 0),
            })

    target_index = next((i for i, item in enumerate(results) if item["result"] == "pending"), len(results))
    initial_results = [dict(item) for item in results]
    initial_target_index = target_index
    if debug:
        debug_trace.append({
            "prefix": "[SENTENCE DEBUG][TARGET]",
            "target_sentence": str(target_text or ""),
            "target_words": list(matcher.words),
            "current_target_index": target_index,
            "current_target_word": matcher.words[target_index] if target_index < len(matcher.words) else None,
        })
    spoken_index = 0
    while target_index < len(results) and spoken_index < len(spoken_words):
        target_word = matcher.normalize_word(matcher.words[target_index])
        spoken_word = spoken_words[spoken_index]
        current = results[target_index]
        is_exact_match = matcher.words_match(spoken_word, target_word)
        split_match_end = None
        if not is_exact_match:
            joined_tokens = spoken_word
            target_syllables = matcher.split_syllables(target_word)
            max_join_end = min(len(spoken_words), spoken_index + 6)
            for candidate_end in range(spoken_index + 1, max_join_end):
                joined_tokens += spoken_words[candidate_end]
                if joined_tokens == target_word:
                    split_match_end = candidate_end + 1
                    break
                final_token = spoken_words[candidate_end]
                filipino_final_consonant_spelling = (
                    str(language_code or "").lower() == "fil-ph"
                    and len(target_syllables) > 1
                    and candidate_end - spoken_index + 1 <= len(target_syllables) + 1
                    and len(final_token) == 2
                    and final_token[-1] in "aeiou"
                    and joined_tokens[:-1] == target_word
                    and target_word.endswith(final_token[0])
                )
                if filipino_final_consonant_spelling:
                    split_match_end = candidate_end + 1
                    break
                if len(joined_tokens) >= len(target_word):
                    break
        resolved_by_split_tokens = split_match_end is not None
        if debug:
            debug_trace.append({
                "prefix": "[SENTENCE DEBUG][MATCH]",
                "target_index": target_index,
                "target_word": target_word,
                "recognized_index": spoken_index,
                "recognized_word": spoken_word,
                "match": is_exact_match,
                "split_token_reconstruction": resolved_by_split_tokens,
                "recognized_span": spoken_words[spoken_index:split_match_end] if resolved_by_split_tokens else [spoken_word],
                "result_before": str(current.get("result") or "").upper(),
            })
        if is_exact_match or resolved_by_split_tokens:
            was_pending_correction = bool(current.get("recognized"))
            current.update({
                "recognized": " ".join(spoken_words[spoken_index:split_match_end]) if resolved_by_split_tokens else spoken_word,
                "result": "correct",
                "type": "split_token_reconstruction" if resolved_by_split_tokens else ("self_correction" if was_pending_correction else "correct"),
                "recognized_index": spoken_index,
                "correct": True,
                "self_corrected": was_pending_correction,
                "miscue": False,
                "points": 1,
            })
            target_index += 1
            if debug:
                debug_trace[-1].update({
                    "final_result": "CORRECT",
                    "self_corrected": was_pending_correction,
                    "split_token_reconstruction": resolved_by_split_tokens,
                    "points": 1,
                })
                debug_trace.append({
                    "prefix": "[SENTENCE DEBUG][ADVANCE]",
                    "previous_index": target_index - 1,
                    "previous_word": target_word,
                    "new_index": target_index,
                    "new_word": matcher.words[target_index] if target_index < len(matcher.words) else None,
                    "reason": "resolved_split_token_reconstruction" if resolved_by_split_tokens else ("resolved_self_correction" if was_pending_correction else "resolved_correct_word"),
                })
            spoken_index = split_match_end if resolved_by_split_tokens else spoken_index + 1
            continue

        next_target_matches = (
            target_index + 1 < len(results)
            and matcher.words_match(spoken_word, matcher.normalize_word(matcher.words[target_index + 1]))
        )
        if next_target_matches or int(current.get("attempt_count") or 0) >= 1:
            current.update({
                "result": "miscue",
                "type": "omission" if next_target_matches else "substitution",
                "correct": False,
                "self_corrected": False,
                "miscue": True,
                "points": 0,
            })
            target_index += 1
            if debug:
                debug_trace[-1].update({
                    "final_result": "MISCUE",
                    "points": 0,
                    "next_target_matches": next_target_matches,
                })
                debug_trace.append({
                    "prefix": "[SENTENCE DEBUG][ADVANCE]",
                    "previous_index": target_index - 1,
                    "previous_word": target_word,
                    "new_index": target_index,
                    "new_word": matcher.words[target_index] if target_index < len(matcher.words) else None,
                    "reason": "recognized_next_target" if next_target_matches else "uncorrected_repeat_mismatch",
                })
            if not next_target_matches:
                spoken_index += 1
            continue

        current.update({
            "recognized": spoken_word,
            "attempt_count": 1,
        })
        if debug:
            debug_trace[-1].update({
                "final_result": "PENDING",
                "points": 0,
                "reason": "first_mismatch_waiting_for_self_correction",
            })
        spoken_index += 1

    # A following silent recognition chunk confirms that an uncorrected final
    # word was left behind; the first mismatch response itself remains pending.
    if not spoken_words and target_index == len(results) - 1:
        final_result = results[target_index]
        if final_result["result"] == "pending" and int(final_result.get("attempt_count") or 0) >= 1:
            final_result.update({
                "result": "miscue",
                "type": "substitution",
                "correct": False,
                "self_corrected": False,
                "miscue": True,
                "points": 0,
            })

    resolved_count = next((i for i, item in enumerate(results) if item["result"] == "pending"), len(results))
    current_syllable_index = matcher.word_syllable_ranges[resolved_count - 1][1] if resolved_count else 0
    correct_words = sum(int(item.get("points") or 0) for item in results)
    response = {
        "transcript": transcript,
        "matched": correct_words,
        "current_syllable_index": current_syllable_index,
        "current_word_index": resolved_count,
        "correct_word_count": correct_words,
        "syllables": matcher.syllables,
        "word_syllable_ranges": matcher.word_syllable_ranges,
        "words": matcher.words,
        "next_syllable": matcher.syllables[current_syllable_index] if current_syllable_index < len(matcher.syllables) else "",
        "next_word": matcher.words[resolved_count] if resolved_count < len(matcher.words) else "",
        "complete": bool(results) and resolved_count >= len(results),
        "progress": round((resolved_count / len(results)) * 100, 2) if results else 0,
        "word_results": results,
        "miscues": sum(1 for item in results if item["result"] == "miscue"),
    }
    if debug:
        final_target_index = response["current_word_index"]
        debug_trace.append({
            "prefix": "[SENTENCE DEBUG][STATE]",
            "before": {
                "current_target_index": initial_target_index,
                "correct_word_count": sum(int(item.get("points") or 0) for item in initial_results),
                "miscue_count": sum(1 for item in initial_results if item.get("result") == "miscue"),
                "word_results": initial_results,
                "complete": False,
            },
            "after": {
                "current_target_index": final_target_index,
                "correct_word_count": correct_words,
                "miscue_count": response["miscues"],
                "word_results": results,
                "complete": response["complete"],
            },
        })
        if response["complete"]:
            debug_trace.append({
                "prefix": "[SENTENCE DEBUG][COMPLETE]",
                "word_results": results,
                "total_correct_words": correct_words,
                "total_miscues": response["miscues"],
                "final_sentence_score": correct_words,
                "advance_reason": "all_target_words_resolved",
            })
        response["sentence_debug_trace"] = debug_trace
    return response


class ReadingMatcher:
    def __init__(self, target_text, current_syllable_index=0, language_code="en-US", strict_rhyme=False):
        self.target_text = target_text or ""
        self.language_code = language_code or "en-US"
        self.strict_rhyme = bool(strict_rhyme)
        self.words = self.readable_words(self.target_text)
        self.current_syllable_index = max(0, int(current_syllable_index or 0))
        self.current_word_index = 0
        self.syllables = []
        self.word_syllable_ranges = []
        self.build_syllable_index()
        self.current_syllable_index = min(self.current_syllable_index, len(self.syllables))
        self.current_word_index = self.word_index_for_syllable(self.current_syllable_index)

    def build_syllable_index(self):
        for word in self.words:
            start = len(self.syllables)
            word_syllables = self.split_syllables(self.normalize_word(word))
            self.syllables.extend(word_syllables)
            self.word_syllable_ranges.append((start, len(self.syllables)))

    def advance_for_spoken_text(self, transcript):
        spoken_words = self.normalize_spoken_words(transcript)
        if not spoken_words or self.current_word_index >= len(self.words):
            return 0

        new_word_index = self.find_best_word_position(spoken_words)
        if new_word_index <= self.current_word_index:
            return 0

        new_syllable_index = self.word_syllable_ranges[new_word_index - 1][1]
        if new_syllable_index <= self.current_syllable_index:
            return 0

        matched = new_syllable_index - self.current_syllable_index
        self.current_syllable_index = new_syllable_index
        self.current_word_index = new_word_index
        return matched

    def find_best_word_position(self, spoken_words):
        target_index = self.current_word_index
        spoken_index = 0
        while target_index < len(self.words) and spoken_index < len(spoken_words):
            target_word = self.normalize_word(self.words[target_index])
            matched_span = None
            for candidate_index in range(spoken_index, len(spoken_words)):
                if self.words_match(spoken_words[candidate_index], target_word):
                    matched_span = (candidate_index, candidate_index + 1)
                    break
                joined_end = self.filipino_joined_match_end(spoken_words, candidate_index, target_word)
                if joined_end is not None:
                    matched_span = (candidate_index, joined_end)
                    break
            if matched_span is None:
                break
            target_index += 1
            spoken_index = matched_span[1]
        return target_index

    def filipino_joined_match_end(self, spoken_words, start_index, target_word):
        """Match STT output such as ``ka ba yo`` against Filipino ``kabayo``."""
        if str(self.language_code).lower() != "fil-ph":
            return None

        joined = spoken_words[start_index]
        max_parts = min(len(spoken_words), start_index + 6)
        for end_index in range(start_index + 1, max_parts):
            joined += spoken_words[end_index]
            if len(joined) > len(target_word):
                break
            if joined == target_word:
                return end_index + 1
            if (
                len(target_word) >= 4
                and len(joined) == len(target_word)
                and self.edit_distance(joined, target_word, 1) <= 1
            ):
                return end_index + 1
        return None

    def find_best_read_position(self, spoken_words, target_words):
        best_index = self.current_syllable_index
        first_candidate = max(0, self.current_syllable_index - len(spoken_words) - 3)
        last_candidate = self.current_syllable_index

        for target_start in range(first_candidate, last_candidate + 1):
            spoken_index = 0
            target_index = target_start
            while spoken_index < len(spoken_words) and target_index < len(target_words):
                if self.words_match(spoken_words[spoken_index], target_words[target_index]):
                    target_index += 1
                spoken_index += 1
            if target_index > best_index:
                best_index = target_index
        return best_index

    def words_match(self, spoken_word, target_word):
        if spoken_word == target_word:
            return True
        if spoken_word in SPOKEN_VOWELS and target_word in SPOKEN_VOWELS:
            if SPOKEN_VOWELS[spoken_word] == SPOKEN_VOWELS[target_word]:
                return True
        if not self.strict_rhyme and self.number_words_match(spoken_word, target_word):
            return True
        if self.homophones_match(spoken_word, target_word):
            return True
        if self.cv_syllables_sound_match(spoken_word, target_word):
            return True
        return False

    @staticmethod
    @lru_cache(maxsize=4096)
    def pronunciations_for_word(word):
        if not word or not re.fullmatch(r"[a-z]+(?:'[a-z]+)?", word):
            return ()
        return tuple(pronouncing.phones_for_word(word))

    def homophones_match(self, spoken_word, target_word):
        if not str(self.language_code).lower().startswith("en"):
            return False
        spoken_pronunciations = set(self.pronunciations_for_word(spoken_word))
        if not spoken_pronunciations:
            return False
        target_pronunciations = set(self.pronunciations_for_word(target_word))
        return bool(spoken_pronunciations.intersection(target_pronunciations))

    @classmethod
    def normalize_number_token(cls, word):
        normalized = cls.normalize_word(word)
        if normalized.isdigit():
            return str(int(normalized))
        return NUMBER_WORDS.get(normalized)

    @classmethod
    def number_words_match(cls, spoken_word, target_word):
        spoken_number = cls.normalize_number_token(spoken_word)
        target_number = cls.normalize_number_token(target_word)
        return (
            spoken_number is not None
            and target_number is not None
            and spoken_number == target_number
        )

    def word_index_for_syllable(self, syllable_index):
        if syllable_index >= len(self.syllables):
            return len(self.words)
        for word_index, (start, end) in enumerate(self.word_syllable_ranges):
            if start <= syllable_index < end:
                return word_index
        return 0

    def payload(self, matched, transcript):
        next_syllable = ""
        next_word = ""
        if self.current_syllable_index < len(self.syllables):
            next_syllable = self.syllables[self.current_syllable_index]
            if self.current_word_index < len(self.words):
                next_word = self.words[self.current_word_index]
        return {
            "transcript": transcript,
            "formatted_syllables": self.format_syllables_for_text(transcript),
            "matched": matched,
            "current_syllable_index": self.current_syllable_index,
            "current_word_index": self.current_word_index,
            "correct_word_count": self.current_word_index,
            "syllables": self.syllables,
            "word_syllable_ranges": self.word_syllable_ranges,
            "words": self.words,
            "next_syllable": next_syllable,
            "next_word": next_word,
            "complete": bool(self.syllables and self.current_syllable_index >= len(self.syllables)),
            "progress": round((self.current_syllable_index / len(self.syllables)) * 100, 2) if self.syllables else 0,
        }

    @classmethod
    def cv_syllables_sound_match(cls, spoken_word, target_word):
        target = cls.cv_parts(target_word)
        if not target:
            return False
        target_consonant, target_vowel = target
        aliases = VOWEL_SOUND_ALIASES.get(target_vowel, {target_vowel})
        for spoken_variant in cls.spoken_sound_variants(spoken_word):
            spoken = cls.cv_parts(spoken_variant)
            if not spoken:
                continue
            spoken_consonant, spoken_vowel = spoken
            if spoken_consonant == target_consonant and spoken_vowel in aliases:
                return True
            if cls.ending_y_diphthong_match(spoken_variant, target_word):
                return True
        return False

    @staticmethod
    def cv_parts(syllable):
        if not syllable:
            return None
        if len(syllable) < 2:
            return None

        consonant = syllable[:-1]
        vowel = syllable[-1]
        if vowel not in VOWELS:
            return None
        if not consonant or any(char in VOWELS for char in consonant):
            return None
        return consonant, vowel

    @staticmethod
    def ending_y_diphthong_match(spoken_word, target_word):
        if not spoken_word or not target_word:
            return False
        spoken_lower = spoken_word.lower()
        target_lower = target_word.lower()
        if not spoken_lower.endswith("y") and not target_lower.endswith("y"):
            return False
        if len(spoken_lower) < 2 or len(target_lower) < 2:
            return False
        spoken_core = spoken_lower[:-1]
        target_core = target_lower[:-1]
        if not spoken_core or not target_core:
            return False
        return spoken_core[-1] == target_core[-1] and spoken_core[:-1] == target_core[:-1]

    @staticmethod
    def spoken_sound_variants(word):
        variants = {word}
        if len(word) > 1 and word.endswith("y"):
            variants.add(f"{word[:-1]}i")
        return variants

    @staticmethod
    def edit_distance(left, right, max_distance):
        if abs(len(left) - len(right)) > max_distance:
            return max_distance + 1
        previous = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current = [left_index]
            row_min = current[0]
            for right_index, right_char in enumerate(right, start=1):
                cost = 0 if left_char == right_char else 1
                current.append(min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + cost,
                ))
                row_min = min(row_min, current[-1])
            if row_min > max_distance:
                return max_distance + 1
            previous = current
        return previous[-1]

    @staticmethod
    def normalize_word(word):
        return re.sub(r"[^a-z0-9']", "", word.lower())

    @classmethod
    def is_list_marker(cls, word):
        cleaned = word.strip()
        normalized = cls.normalize_word(cleaned)
        if not normalized:
            return False
        if re.fullmatch(r"\(?\d+[\.)]?", cleaned):
            return not re.fullmatch(r"\d+", cleaned)
        return False

    @classmethod
    def readable_words(cls, text):
        words = []
        for part in text.split():
            normalized = cls.normalize_word(part)
            if not normalized:
                continue
            if normalized.isdigit():
                words.append(part)
                continue
            if cls.is_list_marker(part):
                continue
            words.append(part)
        return words

    @classmethod
    def normalize_words(cls, text):
        normalized_words = []
        for part in text.split():
            normalized = cls.normalize_word(part)
            if not normalized:
                continue
            if normalized.isdigit():
                normalized_words.append(normalized)
                continue
            if cls.is_list_marker(part):
                continue
            normalized_words.append(normalized)
        return normalized_words

    @classmethod
    def syllables_for_text(cls, text):
        syllables = []
        for word in cls.normalize_spoken_words(text):
            syllables.extend(cls.split_syllables(word))
        return syllables

    @classmethod
    def format_syllables_for_text(cls, text):
        syllable_words = []
        for word in cls.normalize_spoken_words(text):
            syllables = cls.split_syllables(word)
            if syllables:
                syllable_words.append("-".join(syllables))
        return " / ".join(syllable_words)

    @classmethod
    def normalize_spoken_words(cls, text):
        words = [cls.normalize_spoken_word(word) for word in cls.normalize_words(text)]
        return [word for word in words if word]

    @classmethod
    def normalize_spoken_word(cls, word):
        if word in SPOKEN_VOWELS:
            return word
        vowel_syllable = cls.normalize_spoken_vowel_syllable(word)
        if vowel_syllable:
            return vowel_syllable
        collapsed = cls.collapse_repeated_letters(word)
        if collapsed in SPOKEN_VOWELS:
            return SPOKEN_VOWELS[collapsed]
        return word

    @staticmethod
    def normalize_spoken_vowel_syllable(word):
        # Only attempt vowel-syllable collapsing for short spoken tokens.
        # Longer words (e.g. "blue") can contain vowel clusters that
        # should not be collapsed because it changes the word structure
        # and causes exact matches to fail. Restricting to short tokens
        # preserves matching for common short vowel syllables like
        # "ay", "eh", "oh" while avoiding altering full English words.
        # Only normalize very short tokens (2 letters or fewer).
        # Avoid changing 3-letter words like "cow" or "how" which are
        # valid full words and should remain unchanged.
        if not word or len(word) > 2:
            return ""

        patterns = [
            (r"([^aeiou]+)ah", "a"),
            (r"([^aeiou]+)eh", "e"),
            (r"([^aeiou]+)oh", "o"),
            (r"([^aeiou]+)uh", "u"),
            (r"([^aeiou]+)(ee|ea|ey|ie)", "i"),
            (r"([^aeiou]+)(oo|ew|ue)", "u"),
            (r"([^aeiou]+)(oe|ow|oa)", "o"),
        ]
        for pattern, vowel in patterns:
            match = re.fullmatch(pattern, word)
            if match:
                return f"{match.group(1)}{vowel}"
        return ""

    @staticmethod
    def collapse_repeated_letters(word):
        return re.sub(r"(.)\1+", r"\1", word)

    @classmethod
    def split_syllables(cls, word):
        if not word:
            return []
        if not any(char in VOWELS for char in word):
            return [word]

        syllables = []
        current = ""
        index = 0
        while index < len(word):
            current += word[index]
            if word[index] in VOWELS:
                next_char = word[index + 1] if index + 1 < len(word) else ""
                next_next = word[index + 2] if index + 2 < len(word) else ""
                if not next_char:
                    syllables.append(current)
                    current = ""
                elif next_char in VOWELS:
                    syllables.append(current)
                    current = ""
                elif next_next and next_next in VOWELS:
                    syllables.append(current)
                    current = ""
                elif cls.has_final_consonant_cluster(word, index):
                    syllables.append(current)
                    current = ""
                elif index + 1 == len(word) - 1:
                    current += next_char
                    syllables.append(current)
                    current = ""
                    index += 1
            index += 1

        if current:
            syllables.append(current)
        return syllables

    @staticmethod
    def has_final_consonant_cluster(word, vowel_index):
        tail = word[vowel_index + 1:]
        return len(tail) > 1 and all(char not in VOWELS for char in tail)
