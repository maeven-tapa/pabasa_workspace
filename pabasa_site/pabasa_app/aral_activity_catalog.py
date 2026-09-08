"""Canonical ARAL activity identities and reporting competencies."""

from collections import OrderedDict


COMPETENCIES = (
    "Oral Language",
    "Phonics",
    "Phonological Awareness",
    "Fluency",
    "Vocabulary",
    "Reading Comprehension",
)

# These identifiers mirror the activity_type/activity_slug/activity_key values
# already used by the activity implementations.
ACTIVITIES = OrderedDict([
    ("letter_sound_matching", {
        "name": "Letter & Sound Matching",
        "identifiers": ("letter_sound_matching",),
        "competencies": ("Phonics",),
    }),
    ("sound_detective", {
        "name": "Sound Detective",
        "identifiers": ("sound_detective",),
        "competencies": ("Phonological Awareness",),
    }),
    ("letter-sound-correspondence", {
        "name": "Match the Letter to Its Sound",
        "identifiers": ("letter-sound-correspondence", "letter_sound_correspondence"),
        "competencies": ("Phonics",),
    }),
    ("clap_count_syllables", {
        "name": "Clap & Count Syllables",
        "identifiers": ("clap_count_syllables",),
        "competencies": ("Phonological Awareness",),
    }),
    ("syllable_blending", {
        "name": "Syllable Blending",
        "identifiers": ("syllable_blending",),
        "competencies": ("Phonological Awareness",),
    }),
    ("picture_word_matching", {
        "name": "Picture-Word Matching",
        "identifiers": ("picture_word_matching",),
        "competencies": ("Phonics", "Vocabulary"),
    }),
    ("word-decoding", {
        "name": "Decode the Word",
        "identifiers": ("word-decoding", "word_decoding"),
        "competencies": ("Phonics",),
    }),
    ("phrase_reading", {
        "name": "Phrase Reading Practice",
        "identifiers": ("phrase_reading",),
        "competencies": ("Fluency",),
    }),
    ("sentence_reading", {
        "name": "Sentence Reading Practice",
        "identifiers": ("sentence_reading", "sentence_reading_practice"),
        "competencies": ("Fluency",),
    }),
    ("word_meaning_match", {
        "name": "Word Meaning Match",
        "identifiers": ("word_meaning_match",),
        "competencies": ("Vocabulary",),
    }),
    ("fluency_reading", {
        "name": "Fluency Reading",
        "identifiers": ("fluency_reading",),
        "competencies": ("Fluency",),
    }),
    ("story_reading", {
        "name": "Story Reading",
        "identifiers": ("story_reading",),
        "competencies": ("Fluency", "Reading Comprehension"),
    }),
    ("five_w_story_questions", {
        "name": "5W's Story Questions",
        "identifiers": ("five_w_story_questions", "5w_story_questions"),
        "competencies": ("Oral Language", "Reading Comprehension"),
    }),
    ("retell_story", {
        "name": "Retell the Story",
        "identifiers": ("retell_story",),
        "competencies": ("Oral Language", "Reading Comprehension"),
    }),
    ("story_response", {
        "name": "Story Response",
        "identifiers": ("story_response",),
        "competencies": ("Oral Language", "Reading Comprehension"),
    }),
])

IDENTIFIER_TO_ACTIVITY = {
    identifier: activity_id
    for activity_id, definition in ACTIVITIES.items()
    for identifier in definition["identifiers"]
}
TITLE_TO_ACTIVITY = {
    definition["name"].casefold(): activity_id
    for activity_id, definition in ACTIVITIES.items()
}


def resolve_activity(content):
    """Return ``(activity_id, definition)`` for saved material content."""
    if not isinstance(content, dict):
        return None, None

    values = (
        content.get("activity_key"),
        content.get("activity_slug"),
        content.get("activity_type"),
        content.get("template_title"),
        content.get("template_type"),
        content.get("template_activity_name"),
    )
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        activity_id = IDENTIFIER_TO_ACTIVITY.get(normalized)
        if activity_id:
            return activity_id, ACTIVITIES[activity_id]
        activity_id = TITLE_TO_ACTIVITY.get(normalized.casefold())
        if activity_id:
            return activity_id, ACTIVITIES[activity_id]
    return None, None


def activity_is_template(content):
    activity_id, _ = resolve_activity(content)
    return activity_id is not None
