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
    # These filenames are intentional placeholders.  The Lesson 16 Gawain 3
    # workbook images can be added later without changing its activity data.
    'sanga': 'pabasa_app/images/lesson_16/sanga.png',
    'goma': 'pabasa_app/images/lesson_16/goma.png',
    'bunga': 'pabasa_app/images/lesson_16/bunga.png',
    'panga': 'pabasa_app/images/lesson_16/panga.png',
    'gamot': 'pabasa_app/images/lesson_16/gamot.png',
}


PRESCRIBED_ACTIVITIES = {
    'lesson7-gawain2a': {
        'activity_key': 'lesson7-gawain2a', 'session_number': 3, 'lesson_number': 7,
        'gawain_number': '2A', 'title': 'Gawain 2A: Letrang Ii',
        'instruction': 'Isulat ang i sa kahon ng bagay na nagsisimula sa /i/.',
        'interaction': 'picture_handwriting_with_oral_reading',
        'items': [
            {'word': 'ilaw', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/ilaw.png', 'target': True},
            {'word': 'itlog', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/itlog.png', 'target': True},
            {'word': 'isa', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/isa.png', 'target': True},
            {'word': 'bahay', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/bahay.png', 'target': False},
            {'word': 'bola', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/bola.png', 'target': False},
            {'word': 'suklay', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_2/suklay.png', 'target': False},
        ],
    },
    'lesson7-gawain2c': {
        'activity_key': 'lesson7-gawain2c',
        'session_number': 3,
        'lesson_number': 7,
        'gawain_number': '2C',
        'title': 'GAWAIN 2: Letrang Ii',
        'instruction': 'Magsanay Magsulat',
        'interaction': 'handwriting',
        'items': [{'word': 'Ii', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_i/ilaw.png'}, {'word': 'Ii', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_i/itlog.png'}, {'word': 'Ii', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_i/ilong.png'}],
    },
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
    'lesson-16-gawain-3': {
        'activity_key': 'lesson-16-gawain-3',
        'session_number': 6,
        'lesson_number': 16,
        'gawain_number': 3,
        'title': 'Ikabit ang Wastong Salita',
        'instruction': 'Ikabit ang wastong salita para sa mga larawan.',
        'interaction': 'picture_word_match',
        # The word-bank order follows the numbered workbook list.  The image
        # order follows the right-hand illustration column in the worksheet.
        'word_bank': ['panga', 'gamot', 'sanga', 'bunga', 'goma'],
        'items': [
            {'id': 'picture-1', 'word': 'sanga'},
            {'id': 'picture-2', 'word': 'goma'},
            {'id': 'picture-3', 'word': 'bunga'},
            {'id': 'picture-4', 'word': 'panga'},
            {'id': 'picture-5', 'word': 'gamot'},
        ],
    },
}

# Each saved item points directly to its own workbook image file.  Keeping the
# path beside the item also preserves exact image-to-word ordering on every UI.
for _activity in PRESCRIBED_ACTIVITIES.values():
    for _item in _activity['items']:
        if _item['word'] in LESSON_16_IMAGE_PATHS:
            _item['image_path'] = LESSON_16_IMAGE_PATHS[_item['word']]


def prescribed_activity(activity_key):
    """Return a copy so request handling cannot mutate the shared workbook data."""
    activity = PRESCRIBED_ACTIVITIES.get(str(activity_key or '').strip())
    return deepcopy(activity) if activity else None
