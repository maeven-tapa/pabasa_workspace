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
    'lesson7-gawain4b': {
        'activity_key': 'lesson7-gawain4b', 'session_key': 'session-3', 'session_number': 3,
        'lesson_number': 7, 'gawain_number': '4B', 'title': 'GAWAIN 4B: Letrang Ii at Oo',
        'instruction': 'I-type ang i kung ang larawan ay nagsisimula sa titik /i/. I-type ang o kung ang larawan ay nagsisimula sa titik /o/.',
        'interaction': 'oral_then_written', 'items': [
            {'word': 'orasan', 'answer': 'o', 'image_path': 'pabasa_app/images/letrang_o_4b/orasan.png'},
            {'word': 'ilog', 'answer': 'i', 'image_path': 'pabasa_app/images/letrang_o_4b/ilog.png'},
            {'word': 'ibon', 'answer': 'i', 'image_path': 'pabasa_app/images/letrang_o_4b/ibon.png'},
            {'word': 'okra', 'answer': 'o', 'image_path': 'pabasa_app/images/letrang_o_4b/okra.png'},
            {'word': 'oso', 'answer': 'o', 'image_path': 'pabasa_app/images/letrang_o_4b/oso.png'},
            {'word': 'ilaw', 'answer': 'i', 'image_path': 'pabasa_app/images/letrang_o_4b/ilaw.png'},
        ],
    },
    'lesson-26-gawain-1': {
        'activity_key': 'lesson-26-gawain-1', 'session_number': 10, 'lesson_number': 26,
        'gawain_number': 1, 'title': 'Word Search', 'title_fil': 'Hanap-Salita',
        'instruction': 'Read the word on the left, then find it in the grid. Words may be placed horizontally, vertically, or diagonally.',
        'interaction': 'word_search', 'total_items': 5,
        'grid': [['c','a','t','h'], ['t','o','p','m'], ['a','t','a','a'], ['x','p','a','t'], ['h','a','t','f']],
        'words': ['mat', 'top', 'tax', 'hat', 'cat'],
        'items': [{'word': word, 'image_path': 'pabasa_app/images/sound_detective/detective_bg.png'} for word in ['mat', 'top', 'tax', 'hat', 'cat']],
    },
    'lesson-13-gawain-1': {
        'activity_key': 'lesson-13-gawain-1',
        'session_number': 5,
        'lesson_number': 13,
        'gawain_number': 1,
        'title': 'Sabihin ang tunog ng mga letra',
        'instruction': 'Sabihin ang tunog ng mga letra sa ibaba. Lagyan ng tsek (✓) kung tama ang pagkakabigay ng tunog ng mag-aaral.',
        'competencies': ['Phonics', 'Phonological Awareness'],
        'interaction': 'teacher_letter_sound_check',
        'items': [
            {'letter': 'L', 'word': 'liyon', 'image_path': 'pabasa_app/images/alpabetong_pilipino/liyon.png'},
            {'letter': 'l', 'word': 'liyon', 'image_path': 'pabasa_app/images/alpabetong_pilipino/liyon.png'},
            {'letter': 'K', 'word': 'keso', 'image_path': 'pabasa_app/images/alpabetong_pilipino/cheese.png'},
            {'letter': 'k', 'word': 'keso', 'image_path': 'pabasa_app/images/alpabetong_pilipino/cheese.png'},
        ],
    },
    'session-4-gawain-1': {'activity_key': 'session-4-gawain-1', 'session_number': 4, 'lesson_number': '10, 11, at 12', 'gawain_number': 1, 'title': 'Gawain 1: Tunog ng mga Letra', 'instruction': 'Piliin ang tamang tunog para sa bawat letra.', 'route_name': 'session_4_gawain_1_page', 'total_items': 4, 'interaction': 'letter_sound', 'items': [{'word': 'Tunog ng mga Letra', 'image_path': 'pabasa_app/images/sound_detective/detective_bg.png'}]},
    'session-4-gawain-2': {'activity_key': 'session-4-gawain-2', 'session_number': 4, 'lesson_number': '10, 11, at 12', 'gawain_number': 2, 'title': 'Gawain 2: Pagsamahin ang mga Tunog', 'instruction': 'Pagsamahin ang mga tunog upang mabuo ang salita.', 'route_name': 'session_4_gawain_2_page', 'total_items': 4, 'interaction': 'syllable_blending', 'items': [{'word': 'Pagsamahin ang mga Tunog', 'image_path': 'pabasa_app/images/sound_detective/detective_bg.png'}]},
    'session-4-gawain-3': {'activity_key': 'session-4-gawain-3', 'session_number': 4, 'lesson_number': '10, 11, at 12', 'gawain_number': 3, 'title': 'Gawain 3: I-Decode ang mga Salita', 'instruction': 'Basahin at i-decode ang bawat salita.', 'route_name': 'session_4_gawain_3_page', 'total_items': 9, 'interaction': 'word_decoding', 'items': [{'word': 'I-Decode ang mga Salita', 'image_path': 'pabasa_app/images/word-decoding-bg.jpg'}]},
    'session-4-gawain-4': {'activity_key': 'session-4-gawain-4', 'session_number': 4, 'lesson_number': '10, 11, at 12', 'gawain_number': 4, 'title': 'Gawain 4: I-Decode ang mga Pangungusap', 'instruction': 'Basahin at i-decode ang bawat pangungusap.', 'route_name': 'session_4_gawain_4_page', 'total_items': 4, 'interaction': 'sentence_decoding', 'items': [{'word': 'I-Decode ang mga Pangungusap', 'image_path': 'pabasa_app/images/word-decoding-bg.jpg'}]},
    'lesson7-gawain4a': {
        'activity_key': 'lesson7-gawain4a', 'session_key': 'session-3', 'session_number': 3,
        'lesson_number': 7, 'gawain_number': '4A', 'title': 'GAWAIN 4A: Letrang Oo',
        'instruction': 'I-drag ang parisukat sa MALAKING O. I-drag ang bilog sa maliit na o.',
        'interaction': 'shape_stamp',
        'cells': [
            {'id': 'r1c1', 'letter': 'O', 'answer': 'square'}, {'id': 'r1c2', 'letter': 'a', 'answer': None}, {'id': 'r1c3', 'letter': 'o', 'answer': 'circle'},
            {'id': 'r2c1', 'letter': 'S', 'answer': None}, {'id': 'r2c2', 'letter': 'M', 'answer': None}, {'id': 'r2c3', 'letter': 'M', 'answer': None},
            {'id': 'r3c1', 'letter': 'O', 'answer': 'square'}, {'id': 'r3c2', 'letter': 'I', 'answer': None}, {'id': 'r3c3', 'letter': 'O', 'answer': 'square'},
            {'id': 'r4c1', 'letter': 's', 'answer': None}, {'id': 'r4c2', 'letter': 'o', 'answer': 'circle'}, {'id': 'r4c3', 'letter': 'A', 'answer': None},
        ],
        'answer_mapping': {'r1c1': 'square', 'r1c3': 'circle', 'r3c1': 'square', 'r3c3': 'square', 'r4c2': 'circle'},
    },
    'lesson7-gawain4': {
        'activity_key': 'lesson7-gawain4', 'session_number': 3, 'lesson_number': 7,
        'gawain_number': 4, 'title': 'GAWAIN 4: Letrang Oo', 'instruction': 'Magsanay Magsulat',
        'interaction': 'handwriting',
        'items': [
            {'word': 'Oo', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_o/orasan.png'},
            {'word': 'Oo', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_o/orasan.png'},
            {'word': 'Oo', 'stem': '', 'answer': '', 'image_path': 'pabasa_app/images/letrang_o/orasan.png'},
        ],
    },
    'lesson7-gawain3': {
        'activity_key': 'lesson7-gawain3', 'session_number': 3, 'lesson_number': 7,
        'gawain_number': 3, 'title': 'Gawain 3: Letrang Oo',
        'instruction': 'Ikahon ang larawang may unang tunog na nasa unang kolum.',
        'interaction': 'target_picture_selection_with_oral_reading',
        'targets': [
            {'letter': 'O', 'items': [{'word': 'ulap', 'image_path': 'pabasa_app/images/letrang_o/ulap.png'}, {'word': 'orasan', 'image_path': 'pabasa_app/images/letrang_o/orasan.png'}, {'word': 'ulan', 'image_path': 'pabasa_app/images/letrang_o/ulan.png'}], 'answer': 1},
            {'letter': 'I', 'items': [{'word': 'ilaw', 'image_path': 'pabasa_app/images/letrang_o/ilaw.png'}, {'word': 'elepante', 'image_path': 'pabasa_app/images/letrang_o/elepante.png'}, {'word': 'elesi', 'image_path': 'pabasa_app/images/letrang_o/elesi.png'}], 'answer': 0},
            {'letter': 'M', 'items': [{'word': 'manok', 'image_path': 'pabasa_app/images/letrang_o/manok.png'}, {'word': 'durian', 'image_path': 'pabasa_app/images/letrang_o/durian.png'}, {'word': 'ngipin', 'image_path': 'pabasa_app/images/letrang_o/ngipin.png'}], 'answer': 0},
            {'letter': 'S', 'items': [{'word': 'kandila', 'image_path': 'pabasa_app/images/letrang_o/kandila.png'}, {'word': 'pamaypay', 'image_path': 'pabasa_app/images/letrang_o/pamaypay.png'}, {'word': 'sandok', 'image_path': 'pabasa_app/images/letrang_o/sandok.png'}], 'answer': 2},
            {'letter': 'A', 'items': [{'word': 'isa', 'image_path': 'pabasa_app/images/letrang_o/isa.png'}, {'word': 'apoy', 'image_path': 'pabasa_app/images/letrang_o/apoy.png'}, {'word': 'okra', 'image_path': 'pabasa_app/images/letrang_o/okra.png'}], 'answer': 1},
        ],
        'items': [
            {'word': 'ulap', 'image_path': 'pabasa_app/images/letrang_o/ulap.png'},
            {'word': 'ilaw', 'image_path': 'pabasa_app/images/letrang_o/ilaw.png'},
            {'word': 'manok', 'image_path': 'pabasa_app/images/letrang_o/manok.png'},
            {'word': 'kandila', 'image_path': 'pabasa_app/images/letrang_o/kandila.png'},
            {'word': 'isa', 'image_path': 'pabasa_app/images/letrang_o/isa.png'},
        ],
    },
    'lesson7-gawain2b': {
        'activity_key': 'lesson7-gawain2b', 'session_number': 3, 'lesson_number': 7,
        'gawain_number': '2B', 'title': 'Gawain 2B: Letrang Ii',
        'instruction': 'Bilugan ang larawang nagsisimula sa titik Ii.',
        'interaction': 'picture_selection_with_oral_reading',
        'items': [
            {'word': 'ilog', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/ilog.png', 'target': True},
            {'word': 'ipis', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/ipis.png', 'target': True},
            {'word': 'ibon', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/ibon.png', 'target': True},
            {'word': 'atis', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/atis.png', 'target': False},
            {'word': 'mais', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/mais.png', 'target': False},
            {'word': 'mangga', 'image_path': 'pabasa_app/images/letrang_i/letrang_i_3/mangga.png', 'target': False},
        ],
    },
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
    for _item in _activity.get('items', []):
        if _item['word'] in LESSON_16_IMAGE_PATHS:
            _item['image_path'] = LESSON_16_IMAGE_PATHS[_item['word']]


def prescribed_activity(activity_key):
    """Return a copy so request handling cannot mutate the shared workbook data."""
    activity = PRESCRIBED_ACTIVITIES.get(str(activity_key or '').strip())
    return deepcopy(activity) if activity else None
