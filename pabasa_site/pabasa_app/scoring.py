from __future__ import annotations

import re
from typing import Any, Dict, Optional


CRLA_CLASSIFICATIONS = [
    (90, "Readers at Grade Level"),
    (80, "Transitioning Readers"),
    (70, "Developing Readers"),
    (60, "High Emerging Readers"),
    (0, "Low Emerging Readers"),
]

OSPS_MULTIPLIERS = {
    "vowel": 0.85,
    "word": 0.90,
    "sentence": 0.95,
    "paragraph": 1.00,
}

ADAPTED_READING_LEVEL_MULTIPLIERS = {
    "vowel": 0.85,
    "word": 0.90,
    "sentence": 0.95,
    "paragraph": 1.00,
}

ADAPTED_READING_LEVEL_DISCLAIMER = (
    "Great job completing your reading assessment! Your results show your current reading performance. "
    "Keep practicing to improve your reading skills."
)


def normalize_assessment_type(assessment_type: Any) -> str:
    normalized_type = str(assessment_type or "").strip().lower()
    if not normalized_type:
        return ""

    aliases = {
        "vowel": "vowel",
        "vowels": "vowel",
        "vc": "vowel",
        "cv": "vowel",
        "vowel-consonant": "vowel",
        "vowel_consonant": "vowel",
        "consonant-vowel": "vowel",
        "consonant_vowel": "vowel",
        "vowel consonant": "vowel",
    }
    if normalized_type in aliases:
        return aliases[normalized_type]
    if normalized_type.startswith("vowel"):
        return "vowel"
    if normalized_type in {"word", "sentence", "paragraph"}:
        return normalized_type
    return normalized_type


def clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return round(max(0.0, min(100.0, numeric)), 2)


def calculate_fluency_score(ratio: Any, accuracy: Any) -> float:
    adjusted_ratio = max(0.0, min(1.0, float(ratio or 0)))
    normalized_accuracy = clamp_score(accuracy)
    if normalized_accuracy >= 95:
        adjusted_ratio = min(1.0, adjusted_ratio + 0.18)
    elif normalized_accuracy >= 90:
        adjusted_ratio = min(1.0, adjusted_ratio + 0.14)
    elif normalized_accuracy >= 80:
        adjusted_ratio = min(1.0, adjusted_ratio + 0.08)
    elif normalized_accuracy >= 70:
        adjusted_ratio = min(1.0, adjusted_ratio + 0.04)

    if adjusted_ratio <= 0.0:
        return 0.0
    if adjusted_ratio >= 1.0:
        return 100.0
    if adjusted_ratio >= 0.85:
        return 95.0
    if adjusted_ratio >= 0.70:
        return 90.0
    if adjusted_ratio >= 0.55:
        return 80.0
    if adjusted_ratio >= 0.40:
        return 70.0
    if adjusted_ratio >= 0.30:
        return 60.0
    if adjusted_ratio >= 0.20:
        return 52.0
    if adjusted_ratio >= 0.10:
        return 45.0
    return 35.0


def crla_classification(total_score: Any) -> str:
    score = clamp_score(total_score)
    for threshold, label in CRLA_CLASSIFICATIONS:
        if score >= threshold:
            return label
    return CRLA_CLASSIFICATIONS[-1][1]


def osps_multiplier(assessment_type: Any) -> float:
    normalized_type = normalize_assessment_type(assessment_type)
    if normalized_type == "vowel":
        return OSPS_MULTIPLIERS["vowel"]
    if normalized_type == "sentence":
        return OSPS_MULTIPLIERS["sentence"]
    if normalized_type == "paragraph":
        return OSPS_MULTIPLIERS["paragraph"]
    return OSPS_MULTIPLIERS["word"]


def performance_interpretation(total_score: Any) -> str:
    score = clamp_score(total_score)
    if score >= 85:
        return "At Grade Level"
    if score >= 70:
        return "Approaching Grade Level"
    if score >= 55:
        return "Developing"
    if score >= 40:
        return "Needs Support"
    return "Needs Intensive Support"


def normalize_adapted_level_score(level_score: Any) -> float:
    try:
        numeric = float(level_score)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric > 1:
        numeric = numeric / 100.0
    return round(max(0.0, min(1.0, numeric)), 2)


def adapted_reading_level_label(level_score: Any) -> str:
    score = normalize_adapted_level_score(level_score)
    if score >= 0.85:
        return "Readers at Grade Level"
    if score >= 0.70:
        return "Transitioning Readers"
    if score >= 0.55:
        return "Developing Readers"
    if score >= 0.40:
        return "High Emerging Readers"
    return "Low Emerging Readers"


def adapted_reading_level_from_attempts(attempts: Optional[list[Dict[str, Any]]]) -> Dict[str, Any]:
    level_scores = []
    for attempt in attempts or []:
        if not isinstance(attempt, dict):
            continue
        assessment_type = normalize_assessment_type(attempt.get("assessment_type") or attempt.get("type") or attempt.get("mode") or "")
        total_score = attempt.get("overall_raw_score")
        if total_score is None:
            total_score = attempt.get("raw_total_score")
        if total_score is None:
            total_score = attempt.get("total_score")
        if total_score is None:
            continue
        multiplier = ADAPTED_READING_LEVEL_MULTIPLIERS.get(assessment_type)
        if multiplier is None:
            continue
        level_scores.append(normalize_adapted_level_score(total_score) * multiplier)

    if not level_scores:
        return {
            "adapted_level_score": None,
            "adapted_reading_level": "Low Emerging Readers",
            "adapted_reading_level_disclaimer": ADAPTED_READING_LEVEL_DISCLAIMER,
        }

    average_level_score = round(sum(level_scores) / len(level_scores), 2)
    return {
        "adapted_level_score": average_level_score,
        "adapted_reading_level": adapted_reading_level_label(average_level_score),
        "adapted_reading_level_disclaimer": ADAPTED_READING_LEVEL_DISCLAIMER,
    }


def calculate_time_score(correct_words: Any, duration_seconds: Any, assessment_type: Any) -> float:
    word_count = _coerce_int(correct_words) or 0
    duration = _coerce_float(duration_seconds) or 0.0

    if word_count <= 0 or duration <= 0:
        return 0.0

    normalized_type = normalize_assessment_type(assessment_type)
    target_wpm = {"vowel": 30, "word": 45, "sentence": 65, "paragraph": 85}.get(normalized_type, 45)
    if target_wpm <= 0:
        return 0.0

    minutes = max(duration / 60.0, 1.0 / 60.0)
    wpm = word_count / minutes
    pace_ratio = max(0.0, min(1.0, wpm / target_wpm))
    return clamp_score(pace_ratio * 100.0)


def build_assessment_score_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    raw = data.get("scores") if isinstance(data.get("scores"), dict) else data
    assessment_type = normalize_assessment_type(
        data.get("assessment_type") or data.get("type") or data.get("mode") or
        raw.get("assessment_type") or raw.get("type") or raw.get("mode") or
        ""
    )

    raw_metrics = data.get("raw_metrics") if isinstance(data.get("raw_metrics"), dict) else None
    if raw_metrics is None:
        raw_metrics = {}

    payload = raw if isinstance(raw, dict) else {}
    correct_words = _coerce_int(data.get("correct_words"))
    if correct_words is None:
        correct_words = _coerce_int(payload.get("correct_words", raw_metrics.get("correct_words")))
    incorrect_words = _coerce_int(data.get("incorrect_words"))
    if incorrect_words is None:
        incorrect_words = _coerce_int(payload.get("incorrect_words", raw_metrics.get("incorrect_words")))
    skipped_words = _coerce_int(data.get("skipped_words"))
    if skipped_words is None:
        skipped_words = _coerce_int(payload.get("skipped_words", raw_metrics.get("skipped_words")))
    correct_words = correct_words or 0
    incorrect_words = incorrect_words or 0
    skipped_words = skipped_words or 0
    target_word_count = _coerce_int(data.get("target_word_count"))
    if target_word_count is None:
        target_word_count = _coerce_int(payload.get("target_word_count", raw_metrics.get("target_word_count")))
    duration_seconds = _coerce_float(data.get("duration_seconds"))
    if duration_seconds is None:
        duration_seconds = _coerce_float(payload.get("duration_seconds", raw_metrics.get("duration_seconds")))
    pronunciation_score = _coerce_float(data.get("pronunciation_score"))
    if pronunciation_score is None:
        pronunciation_score = _coerce_float(payload.get("pronunciation_score", raw_metrics.get("pronunciation_score")))
    if pronunciation_score is None:
        pronunciation_score = _coerce_float(payload.get("pronunciation", raw_metrics.get("pronunciation")))
    if pronunciation_score is None:
        pronunciation_score = _coerce_float((payload.get("pronunciation_metrics") or {}).get("score"))
    if pronunciation_score is None:
        pronunciation_score = _coerce_float((raw_metrics.get("pronunciation_metrics") or {}).get("score"))
    fluency_score = _coerce_float(data.get("fluency_score"))
    if fluency_score is None:
        fluency_score = _coerce_float(payload.get("fluency_score", raw_metrics.get("fluency_score")))
    if fluency_score is None:
        fluency_score = _coerce_float(payload.get("fluency", raw_metrics.get("fluency")))
    if fluency_score is None:
        fluency_score = _coerce_float((payload.get("fluency_metrics") or {}).get("score"))
    if fluency_score is None:
        fluency_score = _coerce_float((raw_metrics.get("fluency_metrics") or {}).get("score"))

    if target_word_count is None:
        target_word_count = max(0, correct_words + incorrect_words + skipped_words)
    accuracy = _coerce_float(data.get("accuracy"))
    if accuracy is None:
        accuracy = _coerce_float(payload.get("accuracy", raw_metrics.get("accuracy")))
    if accuracy is None:
        accuracy_denominator = max(1, target_word_count or (correct_words + incorrect_words + skipped_words))
        accuracy = round((correct_words / accuracy_denominator) * 100, 2) if accuracy_denominator else 0.0
    else:
        accuracy = clamp_score(accuracy)

    completely_skipped = (
        (correct_words or 0) <= 0
        and (incorrect_words or 0) <= 0
        and (skipped_words or 0) <= 0
        and not str(payload.get("transcript", raw.get("transcript", raw_metrics.get("transcript", ""))) or "").strip()
        and not bool(payload.get("speech_recognition_used", raw.get("speech_recognition_used", raw_metrics.get("speech_recognition_used", False))))
    )

    if completely_skipped:
        fluency_score = 0.0
    elif fluency_score is None:
        try:
            wpm = round(max(0.0, float(correct_words / max(duration_seconds / 60.0, 1.0 / 60.0))), 2)
        except (TypeError, ValueError):
            wpm = 0.0
        target_wpm = {"vowel": 30, "word": 45, "sentence": 65, "paragraph": 85}.get(assessment_type, 45)
        ratio = (wpm / target_wpm) if target_wpm else 0
        fluency_score = calculate_fluency_score(ratio, accuracy)

    if pronunciation_score is None:
        pronunciation_score = 0.0

    if duration_seconds is None:
        duration_seconds = _coerce_float(raw.get("duration_seconds", raw_metrics.get("duration_seconds"))) or 0.0

    derived_time_score = calculate_time_score(correct_words, duration_seconds, assessment_type)
    incoming_time_score = payload.get("time_score", raw.get("time_score", raw.get("time")))
    if incoming_time_score is None:
        time_score_value = derived_time_score
    else:
        try:
            incoming_time_score = clamp_score(incoming_time_score)
        except (TypeError, ValueError):
            incoming_time_score = None
        time_score_value = derived_time_score if derived_time_score > 0 else (incoming_time_score if incoming_time_score is not None else 0.0)

    overall_raw_score = int(round(
        (clamp_score(accuracy) * 0.70)
        + (clamp_score(fluency_score) * 0.15)
        + (clamp_score(pronunciation_score) * 0.10)
        + (time_score_value * 0.05)
    ))
    multiplier = osps_multiplier(assessment_type)
    final_score = int(round(overall_raw_score * multiplier))
    classification = payload.get("crla_classification") or payload.get("classification") or crla_classification(final_score)
    performance_interpretation_value = payload.get("performance_interpretation") or performance_interpretation(final_score)
    adapted_level_payload = adapted_reading_level_from_attempts([
        {"overall_raw_score": overall_raw_score, "assessment_type": assessment_type}
    ])

    return {
        "accuracy": accuracy,
        "fluency_score": fluency_score,
        "pronunciation_score": pronunciation_score,
        "time_score": time_score_value,
        "overall_raw_score": overall_raw_score,
        "final_score": final_score,
        "total_score": final_score,
        "osps_multiplier": multiplier,
        "crla_classification": classification,
        "classification": classification,
        "performance_interpretation": performance_interpretation_value,
        "wpm": round(max(0.0, float(correct_words / max(duration_seconds / 60.0, 1.0 / 60.0))) if duration_seconds else 0.0, 2),
        "duration_seconds": round(max(0.0, duration_seconds), 2),
        "word_count": correct_words,
        "target_word_count": target_word_count,
        "transcript": str(payload.get("transcript", raw.get("transcript", raw_metrics.get("transcript", ""))))[:5000],
        "speech_recognition_used": bool(payload.get("speech_recognition_used", raw.get("speech_recognition_used", raw_metrics.get("speech_recognition_used", False)))),
        "needs_manual_review": bool(payload.get("needs_manual_review", raw.get("needs_manual_review", raw_metrics.get("needs_manual_review", False)))),
        "passed": final_score >= 75,
        "remarks": payload.get("remarks") or (
            "Speech recognition unavailable; review recording manually."
            if payload.get("needs_manual_review", raw.get("needs_manual_review", raw_metrics.get("needs_manual_review", False)))
            else f"CRLA classification: {classification}."
        ),
        "adapted_level_score": adapted_level_payload.get("adapted_level_score"),
        "adapted_reading_level": adapted_level_payload.get("adapted_reading_level"),
        "adapted_reading_level_disclaimer": adapted_level_payload.get("adapted_reading_level_disclaimer"),
    }


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
