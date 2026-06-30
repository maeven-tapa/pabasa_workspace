import base64
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


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
    "a": {"a", "ah"},
    "e": {"e", "eh"},
    "i": {"i", "e", "ee", "y"},
    "o": {"o", "oh", "ow"},
    "u": {"u", "oo", "ew"},
}


def language_code_for(language="", mode=""):
    value = f"{language} {mode}".lower()
    if any(marker in value for marker in ("fil", "tagalog", "marungko")):
        return "fil-PH"
    return "en-US"


def phrase_hints_for(language="", mode=""):
    return MARUNGKO_PHRASE_HINTS if language_code_for(language, mode) == "fil-PH" else []


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

    v1_model = model or ("latest_short" if language_code == "en-US" else "")
    if v1_model == "chirp_3":
        v1_model = "latest_short" if language_code == "en-US" else ""
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


def transcribe_audio_bytes_v2_chirp3(audio_bytes, language_code, project_id, location, credentials_file):
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
    response = client.recognize(request=request)
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

    raise RuntimeError(
        f"Google service account file was not found: {credentials_path}. "
        "Set GOOGLE_STT_SERVICE_ACCOUNT_JSON_B64 on hosting."
    )


def transcribe_audio_bytes_v1(audio_bytes, api_key, language_code, phrase_hints, model, mime_type):
    config = {
        "languageCode": language_code,
        "enableAutomaticPunctuation": language_code == "en-US",
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
    )


def _post_google_stt(url, payload, label):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
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
        raise RuntimeError(f"{label} HTTP {exc.code}: {error_message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while contacting {label}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned an invalid response.") from exc

    if not result.get("results"):
        return ""
    alternatives = result["results"][0].get("alternatives", [])
    if not alternatives:
        return ""
    return alternatives[0].get("transcript", "").strip()


def analyze_reading(target_text, current_syllable_index=0, transcript=""):
    matcher = ReadingMatcher(target_text, current_syllable_index)
    matched = matcher.advance_for_spoken_text(transcript)
    return matcher.payload(matched, transcript)


class ReadingMatcher:
    def __init__(self, target_text, current_syllable_index=0):
        self.target_text = target_text or ""
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
            matched_at = -1
            for candidate_index in range(spoken_index, len(spoken_words)):
                if self.words_match(spoken_words[candidate_index], target_word):
                    matched_at = candidate_index
                    break
            if matched_at == -1:
                break
            target_index += 1
            spoken_index = matched_at + 1
        return target_index

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
        if self.cv_syllables_sound_match(spoken_word, target_word):
            return True
        longer = max(len(spoken_word), len(target_word))
        if longer <= 3:
            return False
        if not spoken_word or not target_word or spoken_word[0] != target_word[0]:
            return False
        allowed_distance = 1 if longer <= 5 else 2
        return self.edit_distance(spoken_word, target_word, allowed_distance) <= allowed_distance

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
        return False

    @staticmethod
    def cv_parts(syllable):
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
        return bool(
            re.fullmatch(r"\d+[\.)]?", cleaned)
            or re.fullmatch(r"\(?\d+[\.)]", cleaned)
            or re.fullmatch(r"\d+", normalized)
        )

    @classmethod
    def readable_words(cls, text):
        words = []
        for part in text.split():
            normalized = cls.normalize_word(part)
            if not normalized or cls.is_list_marker(part):
                continue
            words.append(part)
        return words

    @classmethod
    def normalize_words(cls, text):
        return [
            cls.normalize_word(part)
            for part in text.split()
            if cls.normalize_word(part) and not cls.is_list_marker(part)
        ]

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
        vowel_syllable = cls.normalize_spoken_vowel_syllable(word)
        if vowel_syllable:
            return vowel_syllable
        collapsed = cls.collapse_repeated_letters(word)
        if collapsed in SPOKEN_VOWELS:
            return SPOKEN_VOWELS[collapsed]
        return word

    @staticmethod
    def normalize_spoken_vowel_syllable(word):
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
