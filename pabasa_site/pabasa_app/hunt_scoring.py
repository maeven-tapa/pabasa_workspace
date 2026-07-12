import re
import unicodedata


def normalize_speech(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def classify_speech(transcript, target, confidence=None):
    exact = normalize_speech(transcript) == normalize_speech(target)
    usable = isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1
    if not usable:
        return ("Excellent", 2) if exact else ("Weak", 0)
    if exact and confidence >= 0.8:
        return "Excellent", 2
    if exact and confidence >= 0.5:
        return "Mixed", 1
    return "Weak", 0


def stars_for_points(points):
    points = max(0, min(10, int(points or 0)))
    return 3 if points >= 8 else 2 if points >= 5 else 1
