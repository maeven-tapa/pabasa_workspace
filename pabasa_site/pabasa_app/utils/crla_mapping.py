"""Cell mappings for the official Grade 2 Tagalog CRLA workbook."""

SHEET_NAME = "G2 MT Reading Scoresheet"
STUDENT_START_ROW = 11
STUDENT_END_ROW = 110

SCHOOL_CELLS = {
    "assessment_type": "C3",
    "school_id": "C4",
    "school_name": "C5",
    "teacher": "C6",
    "male_enrollment": "D6",
    "female_enrollment": "E6",
    "section": "C8",
}

STUDENT_COLUMNS = {
    "lrn": "B",
    "learner_name": "C",
    "sex": "D",
    "assessment_date": "E",
    "task_1_score": "F",
    "task_2l_score": "G",
    "task_2h_score": "H",
    "part_1_total": "I",
    "part_1_reading_level": "J",
    "story_number": "K",
    "miscues": "L",
    "total_words_read": "M",
    "reading_minutes": "N",
    "reading_seconds": "O",
    "words_per_minute": "P",
    "correct_words_percentage": "Q",
    "comprehension_score": "R",
    "learner_experience_rating": "S",
    "observation_level": "T",
    "reading_profile": "U",
    "remarks": "V",
}

# Result cells are populated by the exporter from persisted assessment data.
FORMULA_COLUMNS = frozenset({"I", "J", "P", "Q"})
