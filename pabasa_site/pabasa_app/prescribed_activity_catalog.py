"""Immutable workbook content for prescribed ARAL activities.

The activity key, rather than a teacher-editable label, identifies the
workbook interaction everywhere it is used.
"""

from copy import deepcopy


LESSON_16_IMAGE_PATHS = {
    'gumamela': 'pabasa_app/images/lesson_16/gumamela.png',
    'banga': 'pabasa_app/images/lesson_16/banga.png',
    'gusali': 'pabasa_app/images/lesson_16/gusali.png',
    'ngiti': 'pabasa_app/images/lesson_16/ngiti.png',
    'gata': 'pabasa_app/images/lesson_16/gata.png',
}


PRESCRIBED_ACTIVITIES = {
    'lesson-16-gawain-1': {
        'activity_key': 'lesson-16-gawain-1',
        'session_number': 6,
        'lesson_number': 16,
        'gawain_number': 1,
        'title': 'Nawawalang Pantig',
        'instruction': 'Bilugan ang nawawalang pantig para sa larawan.',
        'interaction': 'choice',
        'items': [
            {'word': 'gumamela', 'stem': 'mamela', 'choices': ['ga', 'nga', 'gu'], 'answer': 'gu'},
            {'word': 'banga', 'stem': 'nga', 'choices': ['da', 'ba', 'bu'], 'answer': 'ba'},
            {'word': 'gusali', 'stem': 'sali', 'choices': ['gu', 'ngu', 'gi'], 'answer': 'gu'},
            {'word': 'ngiti', 'stem': 'ti', 'choices': ['ngu', 'nge', 'ngi'], 'answer': 'ngi'},
            {'word': 'gata', 'stem': 'ta', 'choices': ['ga', 'gi', 'ngo'], 'answer': 'ga'},
        ],
    },
    'lesson-16-gawain-2': {
        'activity_key': 'lesson-16-gawain-2',
        'session_number': 6,
        'lesson_number': 16,
        'gawain_number': 2,
        'title': 'Punan ang Pantig',
        'instruction': 'Punan ang pantig para mabuo ang ngalan ng mga larawan.',
        'interaction': 'written',
        'items': [
            {'word': 'gumamela', 'stem': 'mamela', 'answer': 'gu'},
            {'word': 'banga', 'stem': 'nga', 'answer': 'ba'},
            {'word': 'gusali', 'stem': 'sali', 'answer': 'gu'},
            {'word': 'ngiti', 'stem': 'ti', 'answer': 'ngi'},
            {'word': 'gata', 'stem': 'ta', 'answer': 'ga'},
        ],
    },
}

# Each saved item points directly to its own workbook image file.  Keeping the
# path beside the item also preserves exact image-to-word ordering on every UI.
for _activity in PRESCRIBED_ACTIVITIES.values():
    for _item in _activity['items']:
        _item['image_path'] = LESSON_16_IMAGE_PATHS[_item['word']]


def prescribed_activity(activity_key):
    """Return a copy so request handling cannot mutate the shared workbook data."""
    activity = PRESCRIBED_ACTIVITIES.get(str(activity_key or '').strip())
    return deepcopy(activity) if activity else None
