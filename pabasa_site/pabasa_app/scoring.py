from __future__ import annotations

import re
from typing import Any, Dict, Optional


CRLA_CLASSIFICATIONS = [
    (90, "Reading At Grade Level"),
    (80, "Transitioning Reader"),
    (70, "Developing Reader"),
    (60, "High Emerging Reader"),
    (0, "Low Emerging Reader"),
]

CRLA_TASK1_ITEM_COUNT = 10

PHIL_IRI_CLASSIFICATION_MAP = {
    "Low Emerging Readers": "Frustration",
    "High Emerging Readers": "Frustration",
    "Developing Readers": "Instructional",
    "Transitioning Readers": "Instructional",
    "Readers at Grade Level": "Independent",
}

PABASA_LEVEL_MAP = {
    "Low Emerging Readers": "Novice",
    "High Emerging Readers": "Developing",
    "Developing Readers": "Intermediate",
    "Transitioning Readers": "Advanced",
    "Readers at Grade Level": "Expert Reader",
}

# Kept as compatibility constants for callers that imported these names.  CRLA
# scoring never applies activity multipliers.
OSPS_MULTIPLIERS = {"vowel": 1.0, "word": 1.0, "sentence": 1.0, "paragraph": 1.0}
ADAPTED_READING_LEVEL_MULTIPLIERS = {"vowel": 1.0, "word": 1.0, "sentence": 1.0, "paragraph": 1.0}

ADAPTED_READING_LEVEL_DISCLAIMER = (
    "Great job completing your reading assessment!"
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
        "para": "paragraph",
        "story": "paragraph",
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


def crla_task1_next_task(correct_words: Any) -> str:
    """Return the official Part 1 branch after the ten-word task."""
    score = _coerce_int(correct_words) or 0
    return "Task 2L / Rhymes" if score <= 6 else "Task 2H / Sentences"


def crla_part1_total(task1_score: Any, task2l_score: Any = None, task2h_score: Any = None) -> int:
    """Sum Task 1 and exactly one applicable Task 2 raw correct count."""
    task1 = max(0, _coerce_int(task1_score) or 0)
    task2l = _coerce_int(task2l_score)
    task2h = _coerce_int(task2h_score)
    if task2l is not None and task2h is not None:
        raise ValueError("Only one of Task 2L or Task 2H may apply to a CRLA Part 1 result.")
    task2 = task2l if task2l is not None else task2h
    return task1 + max(0, task2 or 0)


def crla_part1_classification(part1_total_score: Any) -> str:
    """Return the initial CRLA level from the raw Part 1 total."""
    total = max(0, _coerce_int(part1_total_score) or 0)
    if total <= 10:
        return "Full Refresher"
    if total <= 16:
        return "Moderate Refresher"
    if total <= 26:
        return "Light Refresher"
    if total <= 30:
        return "Grade Ready"
    return "NOT AVAILABLE"


def crla_part2_profile(total_story_words: Any, words_read: Any, miscues: Any,
                       duration_seconds: Any, comprehension_correct: Any) -> Dict[str, Any]:
    """Derive CRLA Part 2 evidence and classification without weighting it."""
    total_words = max(0, _coerce_int(total_story_words) or 0)
    read = max(0, _coerce_int(words_read) or 0)
    error_count = max(0, _coerce_int(miscues) or 0)
    duration = max(0.0, _coerce_float(duration_seconds) or 0.0)
    correct_words = max(0, min(read, read - error_count))
    passage_accuracy_percent = round((correct_words / total_words) * 100, 2) if total_words else None
    words_read_percent = round((min(read, total_words) / total_words) * 100, 2) if total_words else 0.0
    wpm = round(correct_words / (duration / 60.0), 2) if duration else 0.0
    answers = _coerce_int(comprehension_correct)
    reading_band = None
    if passage_accuracy_percent is not None:
        reading_band = (0 if passage_accuracy_percent < 25 else 1 if passage_accuracy_percent <= 50
                        else 2 if passage_accuracy_percent <= 75 else 3)
    comprehension_band = None if answers is None else (0 if answers <= 0 else 1 if answers <= 2 else 2 if answers <= 4 else 3)
    classification = "NOT AVAILABLE"
    if passage_accuracy_percent is not None and answers is not None:
        if passage_accuracy_percent < 25 and answers == 0:
            classification = "Low Emerging Reader"
        elif 26 <= passage_accuracy_percent <= 50 and 1 <= answers <= 2:
            classification = "High Emerging Reader"
        elif 51 <= passage_accuracy_percent <= 75 and 3 <= answers <= 4:
            classification = "Developing Reader"
        elif 76 <= passage_accuracy_percent < 100 and 5 <= answers <= 6:
            classification = "Transitioning Reader"
        elif passage_accuracy_percent == 100 and answers >= 5:
            classification = "Reading At Grade Level"
    final_band = min(reading_band, comprehension_band) if reading_band is not None and comprehension_band is not None else None
    return {
        "total_story_words": total_words, "words_read": read, "miscues": error_count,
        "duration_seconds": duration, "wpm": wpm, "correct_word_percent": passage_accuracy_percent,
        "passage_accuracy_percent": passage_accuracy_percent, "words_read_percent": words_read_percent,
        "comprehension_correct": answers, "classification": classification,
        "reading_band": reading_band, "comprehension_band": comprehension_band,
        "final_part2_band": final_band,
    }


def normalize_crla_score_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the raw CRLA audit fields stable across browser and server stages."""
    source = data if isinstance(data, dict) else {}
    aliases = {
        "task1_total_words": ("task1_total_words", "target_word_count"),
        # A story's generic correct_words is its passage aggregate, not Task 1.
        "task1_correct_words": ("task1_correct_words", "task1_score"),
        "task1_score": ("task1_score", "task1_correct_words"),
        "task2_type": ("task2_type",), "task2_score": ("task2_score",),
        "part1_total_score": ("part1_total_score",), "story_number": ("story_number",),
        "story_total_words": ("story_total_words", "total_story_words"),
        "words_read": ("words_read", "total_words_read"), "miscues": ("miscues",),
        "duration_seconds": ("duration_seconds",), "wpm": ("wpm",),
        "comprehension_total": ("comprehension_total", "total_questions"),
        "comprehension_correct": ("comprehension_correct", "correct_answers"),
        "passage_accuracy_percent": ("passage_accuracy_percent", "story_read_percent"),
        "crla_classification": ("crla_classification", "classification"),
    }
    normalized = {}
    for key, keys in aliases.items():
        value = next((source.get(alias) for alias in keys if source.get(alias) not in (None, "")), None)
        normalized[key] = value
    return normalized


def normalize_classification_label(value: Any) -> Optional[str]:
    text = str(value or '').strip().lower().replace('_', ' ').replace('-', ' ')
    if not text:
        return None
    if 'pending' in text:
        return None
    if 'low' in text and 'emerging' in text:
        return 'Low Emerging Readers'
    if 'high' in text and 'emerging' in text:
        return 'High Emerging Readers'
    if 'develop' in text:
        return 'Developing Readers'
    if 'transition' in text:
        return 'Transitioning Readers'
    if 'grade' in text or 'ready' in text or text in {'g', 'gr'}:
        return 'Readers at Grade Level'
    return None


def derive_classification_equivalents(crla_label: Any) -> dict[str, str]:
    normalized_crla = normalize_classification_label(crla_label)
    if not normalized_crla:
        return {
            'crla_reading_classification': 'Not yet available',
            'phil_iri_classification': 'Not yet available',
            'pabasa_level': 'Not yet available',
        }
    return {
        'crla_reading_classification': normalized_crla,
        'phil_iri_classification': PHIL_IRI_CLASSIFICATION_MAP.get(normalized_crla, 'Not yet available'),
        'pabasa_level': PABASA_LEVEL_MAP.get(normalized_crla, 'Not yet available'),
    }


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
        if assessment_type not in ADAPTED_READING_LEVEL_MULTIPLIERS:
            continue
        level_scores.append(normalize_adapted_level_score(total_score))

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
    crla_score_data = data.get("crla_score_data")
    if not isinstance(crla_score_data, dict):
        crla_score_data = payload.get("crla_score_data")
    crla_input = dict(payload) if isinstance(payload, dict) else {}
    crla_input.update(data)
    if isinstance(crla_score_data, dict):
        crla_input.update(crla_score_data)
    is_crla_attempt = bool(crla_score_data)
    crla_score_data = normalize_crla_score_data(crla_input) if is_crla_attempt else {}
    if is_crla_attempt:
        crla_score_data["task1_total_words"] = CRLA_TASK1_ITEM_COUNT
    correct_items = _coerce_int(data.get("correct_items"))
    if correct_items is None:
        correct_items = _coerce_int(payload.get("correct_items", raw_metrics.get("correct_items")))
    items_completed = _coerce_int(data.get("items_completed"))
    if items_completed is None:
        items_completed = _coerce_int(payload.get("items_completed", raw_metrics.get("items_completed")))
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

    # CRLA Part 1 is a count of correct responses.  A completed word task is
    # Task 1 (0-10); sentence/rhyme scores are likewise raw correct-item
    # counts.  When the reader supplies an accumulated Part 1 total, that is
    # the authoritative score.  Part 2 retains its independent profile.
    if assessment_type == "word":
        task_score = max(0, correct_words)
    else:
        task_score = max(0, correct_items if correct_items is not None else correct_words)
    part1_total = _coerce_int(data.get("part1_total_score"))
    if part1_total is None:
        part1_total = _coerce_int(payload.get("part1_total_score"))
    if part1_total is None and is_crla_attempt:
        part1_total = _coerce_int(crla_score_data.get("part1_total_score"))
    if part1_total is None and is_crla_attempt and crla_score_data.get("task2_score") is not None:
        part1_total = crla_part1_total(
            crla_score_data.get("task1_score"),
            crla_score_data.get("task2_score") if "l" in str(crla_score_data.get("task2_type") or "").lower() else None,
            crla_score_data.get("task2_score") if "h" in str(crla_score_data.get("task2_type") or "").lower() else None,
        )
    if part1_total is not None and assessment_type != "paragraph":
        overall_raw_score = max(0, part1_total)
    elif assessment_type in {"word", "sentence", "vowel"}:
        overall_raw_score = task_score
    else:
        overall_raw_score = max(0, correct_words)
    final_score = overall_raw_score
    if part1_total is not None:
        classification = crla_part1_classification(final_score)
    elif assessment_type == "paragraph":
        total_story_words = crla_score_data.get("story_total_words") or data.get("total_story_words", payload.get("total_story_words", target_word_count))
        words_read = crla_score_data.get("words_read") or data.get("words_read", payload.get("words_read", correct_words + incorrect_words))
        miscues = crla_score_data.get("miscues") if crla_score_data.get("miscues") is not None else data.get("miscues", payload.get("miscues", incorrect_words))
        comprehension = crla_score_data.get("comprehension_correct")
        if comprehension is None:
            comprehension = data.get("correct_answers", payload.get("correct_answers"))
        part2_profile = crla_part2_profile(total_story_words, words_read, miscues, duration_seconds, comprehension)
        classification = part2_profile["classification"]
    elif is_crla_attempt:
        # A Task 1-only record must not be assigned a generic percentage-based
        # reader classification before its applicable Task 2 is completed.
        classification = ""
    else:
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
        "crla_task_score": task_score,
        "part1_total_score": part1_total,
        "crla_score_data": crla_score_data,
        "final_score": final_score,
        "total_score": final_score,
        "osps_multiplier": 1.0,
        "crla_classification": classification,
        "classification": classification,
        "performance_interpretation": performance_interpretation_value,
        "wpm": round(max(0.0, float(correct_words / max(duration_seconds / 60.0, 1.0 / 60.0))) if duration_seconds else 0.0, 2),
        "duration_seconds": round(max(0.0, duration_seconds), 2),
        "word_count": correct_words,
        "target_word_count": target_word_count,
        "correct_items": max(0, correct_items or 0),
        "items_completed": max(0, items_completed or 0),
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


def _part2_classification(reading_percent: Any, correct_answers: Any) -> str:
    try:
        percent = float(reading_percent)
        answers = int(float(correct_answers))
    except (TypeError, ValueError):
        return "High Emerging Reader"
    reading_band = 0 if percent <= 25 else 1 if percent <= 50 else 2 if percent <= 75 else 3
    comprehension_band = 0 if answers <= 0 else 1 if answers <= 2 else 2 if answers <= 4 else 3
    return ("High Emerging Reader", "Developing Reader", "Transitioning Reader", "Reading at Grade Level")[min(reading_band, comprehension_band)]
