"""System-owned content for the Syllable Blending activity."""

import random


FILIPINO = [
    [('ma', 'so', 'maso'), ('mi', 'sa', 'misa'), ('a', 'so', 'aso'), ('mi', 'so', 'miso'), ('ma', 'is', 'mais')],
    [('ba', 'ta', 'bata'), ('pa', 'so', 'paso'), ('sa', 'ma', 'sama'), ('la', 'ro', 'laro'), ('ta', 'yo', 'tayo')],
    [('ba', 'hay', 'bahay'), ('ka', 'ma', 'kama'), ('su', 'su', 'susu'), ('pa', 'ko', 'pako'), ('ba', 'so', 'baso')],
    [('gu', 'ro', 'guro'), ('li', 'bro', 'libro'), ('me', 'sa', 'mesa'), ('pe', 'ra', 'pera'), ('pa', 'per', 'paper')],
    [('pu', 'sa', 'pusa'), ('a', 'so', 'aso'), ('ma', 'ma', 'mama'), ('pa', 'pa', 'papa'), ('ba', 'so', 'baso')],
]

ENGLISH = [
    [('sun', 'set', 'sunset'), ('rain', 'bow', 'rainbow'), ('bed', 'room', 'bedroom'), ('foot', 'ball', 'football'), ('play', 'ground', 'playground')],
    [('pic', 'nic', 'picnic'), ('nap', 'kin', 'napkin'), ('kit', 'ten', 'kitten'), ('mon', 'key', 'monkey'), ('pen', 'cil', 'pencil')],
    [('ta', 'ble', 'table'), ('win', 'dow', 'window'), ('bas', 'ket', 'basket'), ('rab', 'bit', 'rabbit'), ('mu', 'sic', 'music')],
    [('teach', 'er', 'teacher'), ('stu', 'dent', 'student'), ('pa', 'per', 'paper'), ('pen', 'cil', 'pencil'), ('Sun', 'day', 'Sunday')],
    [('ro', 'bot', 'robot'), ('hel', 'met', 'helmet'), ('flow', 'er', 'flower'), ('rain', 'coat', 'raincoat'), ('sun', 'shine', 'sunshine')],
]

FILIPINO_BIG_BOX = [
    FILIPINO[0], FILIPINO[1], FILIPINO[2],
    [('gu', 'ro', 'guro'), ('li', 'bro', 'libro'), ('me', 'sa', 'mesa'), ('pe', 'ra', 'pera'), ('ba', 'ta', 'bata')],
    FILIPINO[4],
]
ENGLISH_BIG_BOX = ENGLISH

SET_NAMES = {
    'Filipino': ['Basic Words', 'Familiar Words', 'Everyday Words', 'School/Familiar Words', 'Mixed Practice'],
    'English': ['Compound Words', 'Common Words', 'Everyday Words', 'School/Home', 'Mixed Practice'],
}

INSTRUCTIONS = {
    'Filipino': {
        'syllable_combination': 'Pagsamahin ang mga pantig upang makabuo ng salita.',
        'big_box': 'Basahin ang mga pantig sa loob ng Big Box at bumuo ng mga salita mula rito.',
    },
    'English': {
        'syllable_combination': 'Combine the syllables to form a complete word.',
        'big_box': 'Read the syllables inside the Big Box and build words from them.',
    },
}


def normalize_format(value):
    normalized = str(value or '').strip().lower().replace('-', '_').replace(' ', '_')
    return 'big_box' if 'big_box' in normalized or 'word_build' in normalized else 'syllable_combination'


def activity_catalog():
    """Return all 20 teacher-selectable activity choices."""
    catalog = {'Filipino': {}, 'English': {}}
    for language in catalog:
        for activity_format in ('syllable_combination', 'big_box'):
            catalog[language][activity_format] = [
                build_activity(language, activity_format, index) for index in range(5)
            ]
    return catalog


def build_activity(language='Filipino', activity_format='syllable_combination', set_index=None):
    """Build one immutable five-item set; only presentation order is randomized later."""
    language = 'English' if str(language).strip().lower().startswith('eng') else 'Filipino'
    activity_format = normalize_format(activity_format)
    if activity_format == 'big_box':
        sets = ENGLISH_BIG_BOX if language == 'English' else FILIPINO_BIG_BOX
    else:
        sets = ENGLISH if language == 'English' else FILIPINO
    if set_index is None:
        set_index = random.SystemRandom().randrange(len(sets))
    set_index = max(0, min(int(set_index), len(sets) - 1))
    source = sets[set_index]
    pool = list(dict.fromkeys(part for first, second, _ in source for part in (first, second)))
    items = [{'syllables': [first, second], 'answer': answer} for first, second, answer in source]
    return {
        'activity_type': 'syllable_blending',
        'activity_format': activity_format,
        'language': language,
        'set_number': set_index + 1,
        'activity_name': SET_NAMES[language][set_index],
        'activity_id': f"{language.lower()}_{activity_format}_{set_index + 1:02d}",
        'instruction': INSTRUCTIONS[language][activity_format],
        'items': items,
        'syllable_pool': pool,
    }
