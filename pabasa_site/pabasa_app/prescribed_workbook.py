"""ARAL workbook, printed pages 38–52. Visible labels are not identifiers.

Content is transcribed from PDF pages 41–55. Preserve source spelling, case,
layout, and repeated numbering. Open-ended answers require teacher review.
"""
from copy import deepcopy
import json
import re
import unicodedata


ACTIVITIES = {}

# These combinations are validated privately on the server and are never
# included in the learner payload. They use only pieces in Lesson 22's Big Box.
L22_C_ACCEPTED_BUILDS = {
    'cactus': ('cac', 'tus'),
    'Cebu': ('ce', 'bu'),
    'Cagayan': ('ca', 'ga', 'yan'),
    'Cardo': ('Car', 'do'),
    'cabinet': ('ca', 'bi', 'net'),
    'Celeste': ('Ce', 'les', 'te'),
    'com': ('com',),
    'computer': ('com', 'pu', 'ter'),
}

# Reading context for the Cc Big Box. The tile remains the learner-facing
# target; the whole word gives STT enough context to judge hard/soft C sounds.
L22_C_READING_CONTEXTS = {
    'item-1': {'word': 'cactus', 'syllables': ('cac', 'tus'), 'sound': 'hard'},
    'item-2': {'word': 'Cebu', 'syllables': ('ce', 'bu'), 'sound': 'soft'},
    'item-3': {'word': 'Cagayan', 'syllables': ('ca', 'ga', 'yan'), 'sound': 'hard'},
    'item-4': {'word': 'Cebu', 'syllables': ('ce', 'bu'), 'sound': 'soft'},
    'item-5': {'word': 'computer', 'syllables': ('com', 'pu', 'ter'), 'sound': 'hard'},
    'item-6': {'word': 'computer', 'syllables': ('com', 'pu', 'ter'), 'sound': 'hard'},
    'item-7': {'word': 'Cagayan', 'syllables': ('ca', 'ga', 'yan'), 'sound': 'hard'},
    'item-8': {'word': 'cactus', 'syllables': ('cac', 'tus'), 'sound': 'hard'},
    'item-9': {'word': 'computer', 'syllables': ('com', 'pu', 'ter'), 'sound': 'hard'},
    'item-10': {'word': 'Cagayan', 'syllables': ('ca', 'ga', 'yan'), 'sound': 'hard'},
    'item-11': {'word': 'Cardo', 'syllables': ('Car', 'do'), 'sound': 'hard'},
    'item-12': {'word': 'Cardo', 'syllables': ('Car', 'do'), 'sound': 'hard'},
    'item-13': {'word': 'cabinet', 'syllables': ('ca', 'bi', 'net'), 'sound': 'hard'},
    'item-14': {'word': 'cabinet', 'syllables': ('ca', 'bi', 'net'), 'sound': 'hard'},
    'item-15': {'word': 'cabinet', 'syllables': ('ca', 'bi', 'net'), 'sound': 'hard'},
    'item-16': {'word': 'Celeste', 'syllables': ('Ce', 'les', 'te'), 'sound': 'soft'},
    'item-17': {'word': 'Celeste', 'syllables': ('Ce', 'les', 'te'), 'sound': 'soft'},
    'item-18': {'word': 'Celeste', 'syllables': ('Ce', 'les', 'te'), 'sound': 'soft'},
}

# Lesson 22, Gawain 2 is intentionally stored as a single alternating flow.
# The visual columns below are only presentation; this is the authoritative
# learner order and must not be changed to column-major reading.
L22_G2_C_WORDS = (
    'computer', 'Cebu', 'cactus', 'Cita', 'camera', 'Celso', 'cabinet',
    'Vicente', 'Caloocan', 'Celeste', 'Coron', 'Celsa', 'Vic', 'Carlos',
)
L22_G2_C_SOUNDS = ('/k/', '/s/') * 7

L24_G2_V_WORDS = (
    'Vina', 'Vilma', 'Victor', 'Victoria', 'Valdez', 'Valle', 'Visayas',
    'vanilla', 'vila', 'vinta', 'van', 'visa', 'violin', 'volleybal',
)
L24_G2_ACCEPTED_SPEECH = {word.casefold(): {word.casefold()} for word in L24_G2_V_WORDS}

L24_G4_X_WORDS = ('x-ray', 'fax machine', 'fox')
L24_G4_X_ACCEPTED_SPEECH = {
    'x-ray': {'x ray', 'x-ray'},
    'fax machine': {'fax machine'},
    'fox': {'fox'},
}

# Lesson 22 Gawain 2 keeps the workbook spelling as the canonical display
# value while allowing only explicit Filipino STT spellings for pronunciation.
L22_G2_ACCEPTED_SPEECH = {
    'computer': {'computer', 'komputer', 'kompyuter'},
    'cebu': {'cebu', 'sebu'},
    'cactus': {'cactus', 'kaktus'},
    'cita': {'cita', 'sita'},
    'camera': {'camera', 'kamera'},
    'celso': {'celso', 'selso'},
    'cabinet': {'cabinet', 'kabinet'},
    'vicente': {'vicente', 'bisente'},
    'caloocan': {'caloocan', 'kaloocan'},
    'celeste': {'celeste', 'seleste'},
    'coron': {'coron', 'koron'},
    'celsa': {'celsa', 'selsa'},
    'vic': {'vic', 'bik'},
    'carlos': {'carlos', 'karlos'},
}

L22_G6_F_WORDS = (
    'freezer', 'fries', 'Filipino', 'Fina', 'Filipiniana',
    'Felipe', 'Felix', 'Ferrer', 'Faith', 'Fontana',
)
L22_G6_ACCEPTED_SPEECH = {
    'freezer': {'freezer', 'frizer', 'freezer'},
    'fries': {'fries', 'frize', 'frys'},
    'filipino': {'filipino', 'filipina'},
    'fina': {'fina', 'feena', 'fena'},
    'filipiniana': {'filipiniana', 'filipiniana'},
    'felipe': {'felipe', 'felipeh', 'felipay'},
    'felix': {'felix', 'feliks', 'felics'},
    'ferrer': {'ferrer', 'ferer'},
    'faith': {'faith', 'fayth', 'feith'},
    'fontana': {'fontana', 'fontanna'},
}

# Lesson 22 Gawain 4 is the Ff Big Box activity on workbook page 40.  The
# following are the only words approved by the adjacent prescribed F-word
# activity and are intentionally kept private from client-side validation.
L22_G4_F_WORDS = ('freezer', 'fries', 'Fina', 'Filipino', 'Felix')
L22_G4_ACCEPTED_SPEECH = {
    'free': {'free', 'three', 'flee'},
    'fries': {'fries', 'frize', 'frys'},
    'fi': {'fi', 'fie', 'phi'},
    'fe': {'fe', 'fee', 'fay'},
    'na': {'na', 'nah'},
    'li': {'li', 'lee', 'ly'},
    'lix': {'lix', 'licks'},
    'zer': {'zer', 'sir', 'zər'},
    'pe': {'pe', 'pay', 'p'},
}

# Lesson 23 Gawain 1 uses the workbook's Ñ Big Box.  The only target word
# that is both present in the validated Lesson 23 word list and constructible
# from the requested box is Niño.
L23_G1_WORDS = ('Niño',)
L23_G1_ACCEPTED_SPEECH = {
    'ni': {'ni'}, 'la': {'la'}, 'ña': {'ña', 'na'},
    'cas': {'cas', 'kas', 'kass'}, 'bi': {'bi', 'bee'}, 'da': {'da'},
    'el': {'el', 'ell'}, 'ño': {'no', 'nyo'}, 'ñan': {'nan', 'nyan'},
    'cen': {'cen', 'sen'}, 'ta': {'ta'}, 'ñe': {'ne', 'nye'},
}

L23_G2_TARGETS = (
    'Penafrancia España', 'Los Baños', 'Biñan Cendaña',
    'Castañeda Orduña', 'Niño', 'Niña',
)
L23_G2_ACCEPTED_SPEECH = {
    'penafrancia españa': {'penafrancia españa', 'penafrancia espana'},
    'los baños': {'los baños', 'los banos'},
    'biñan cendaña': {'biñan cendaña', 'binan cendana'},
    'castañeda orduña': {'castañeda orduña', 'castaneda orduna'},
    'niño': {'niño', 'nino'},
    'niña': {'niña', 'nina'},
}

# Lesson 23 Gawain 3 keeps the workbook's eight Jj words as the only
# accepted reading targets.  Normalization is deliberately limited to case,
# Unicode compatibility, punctuation, and whitespace.
L23_G3_J_WORDS = ('Jacket', 'Jennifer', 'jam', 'Jeffrey', 'pajama', 'Jerry', 'Jojo', 'Jonathan')
L23_G3_J_ACCEPTED_SPEECH = {word.casefold(): {word.casefold()} for word in L23_G3_J_WORDS}

# Lesson 23 Gawain 7 keeps the workbook's five Qq words as the only reading
# targets.  Matching remains deliberately narrow for these proper names:
# case, Unicode compatibility, punctuation, and whitespace are harmless, but
# unrelated or broad fuzzy matches are never accepted.
L23_G7_Q_WORDS = ('Quisumbing', 'Quennie', 'Enriquez', 'Quintana', 'Quintos')
L23_G7_Q_ACCEPTED_SPEECH = {word.casefold(): {word.casefold()} for word in L23_G7_Q_WORDS}

# Lesson 23 Gawain 6 has no verified answer key in the available workbook
# project sources.  Keep the reading matcher deliberately narrow until the
# canonical word paths are supplied; never fabricate target words here.
L23_G6_CANONICAL_WORDS = ()
L23_G6_ACCEPTED_SPEECH = {
    'que': {'que'}, 'en': {'en'}, 'qui': {'qui'}, 'tos': {'tos'},
    'no': {'no'}, 'a': {'a'}, 'quin': {'quin'}, 'an': {'an'},
    'ta': {'ta'}, 'ja': {'ja'}, 'na': {'na'}, 'to': {'to'},
    'ri': {'ri'}, 'zon': {'zon'}, 'ti': {'ti'},
}

# Lesson 24 Gawain 1's visible Big Box is present in the workbook source, but
# no authoritative answer key or ordered word paths are available in the
# project. Keep this empty rather than accepting guessed combinations.
L24_G1_CANONICAL_WORDS = ()
L24_G1_ACCEPTED_SPEECH = {
    'lin': {'lin'}, 'sa': {'sa'}, 'van': {'van'}, 'va': {'va'},
    'e': {'e'}, 'la': {'la'}, 'i': {'i'}, 'vi': {'vi'}, 'vio': {'vio'},
    'le': {'le'}, 'val': {'val'}, 'a': {'a'},
}


def normalize_l23_g3_speech(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    text = re.sub(r'[^0-9a-z\s]', ' ', text)
    return ' '.join(text.split())


def l23_g3_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l23_g3_speech(canonical_word)
    heard = normalize_l23_g3_speech(transcript)
    return bool(heard and heard in L23_G3_J_ACCEPTED_SPEECH.get(canonical, {canonical}))


def l23_g7_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l23_g3_speech(canonical_word)
    heard = normalize_l23_g3_speech(transcript)
    return bool(heard and heard in L23_G7_Q_ACCEPTED_SPEECH.get(canonical, {canonical}))


L23_G4_SYLLABLE_ANSWERS = ('jack-et', 'pa-ja-ma', 'Jo-na-than', 'jam', 'Jo-se-li-to')


def normalize_l23_g4_syllables(value):
    text = unicodedata.normalize('NFKC', str(value or '')).strip().casefold()
    text = text.replace('•', '-').replace('·', '-')
    return re.sub(r'\s*-\s*', '-', text)

L22_G3_C_WORD_PATHS = {
    'Carla': [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]],
    'Cagayan': [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [1, 6]],
    'cactus': [[2, 2], [2, 3], [2, 4], [2, 5], [2, 6], [2, 7]],
    'Cardo': [[3, 4], [3, 5], [3, 6], [3, 7], [3, 8]],
    'computer': [[4, 0], [4, 1], [4, 2], [4, 3], [4, 4], [4, 5], [4, 6], [4, 7]],
    'Celeste': [[5, 1], [5, 2], [5, 3], [5, 4], [5, 5], [5, 6], [5, 7]],
    'cabinet': [[6, 2], [6, 3], [6, 4], [6, 5], [6, 6], [6, 7], [6, 8]],
    'Cebu': [[7, 0], [7, 1], [7, 2], [7, 3]],
    'camera': [[8, 3], [8, 4], [8, 5], [8, 6], [8, 7], [8, 8]],
}

# Lesson 22 Gawain 5 is the Ff Big Box on workbook page 40.  These ordered
# paths are the workbook authority for the five horizontal, left-to-right
# answers; client selections are never accepted by letter matching alone.
L22_G5_F_WORD_PATHS = {
    'Fina': [[0, 3], [0, 4], [0, 5], [0, 6]],
    'fries': [[2, 1], [2, 2], [2, 3], [2, 4], [2, 5]],
    'Filipino': [[3, 0], [3, 1], [3, 2], [3, 3], [3, 4], [3, 5], [3, 6], [3, 7]],
    'freezer': [[4, 0], [4, 1], [4, 2], [4, 3], [4, 4], [4, 5], [4, 6]],
    'Felix': [[5, 3], [5, 4], [5, 5], [5, 6], [5, 7]],
}

# Lesson 23 Gawain 5 is the Jj word-search Big Box.  These are the exact
# workbook coordinates; validation must use the path as well as the spelling.
L23_G5_J_WORD_PATHS = {
    'jacket': [[2, 0], [2, 1], [2, 2], [2, 3], [2, 4], [2, 5]],
    'pajama': [[3, 3], [3, 4], [3, 5], [3, 6], [3, 7], [3, 8]],
    'jam': [[1, 0], [1, 1], [1, 2]],
    'Jonathan': [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6], [0, 7], [0, 8]],
    'Jennifer': [[4, 0], [4, 1], [4, 2], [4, 3], [4, 4], [4, 5], [4, 6], [4, 7]],
}


def normalize_l22_g2_speech(value):
    """Normalize one STT result without changing the workbook word."""
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    text = re.sub(r'[^0-9a-z\s]', ' ', text)
    return ' '.join(text.split())


def l22_g2_pronunciation_match(canonical_word, transcript):
    """Match an explicit accepted speech form for the current word only."""
    canonical = normalize_l22_g2_speech(canonical_word)
    heard = normalize_l22_g2_speech(transcript)
    accepted = L22_G2_ACCEPTED_SPEECH.get(canonical, {canonical})
    return bool(heard and heard in accepted)


def normalize_l24_g2_speech(value):
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(value or '').casefold()))


def l24_g2_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l24_g2_speech(canonical_word)
    heard = normalize_l24_g2_speech(transcript)
    accepted = {normalize_l24_g2_speech(item) for item in L24_G2_ACCEPTED_SPEECH.get(str(canonical_word).casefold(), {canonical})}
    return bool(heard and heard in accepted)


def normalize_l24_g4_speech(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    text = re.sub(r'[^a-z\s-]', ' ', text)
    return ' '.join(text.replace('-', ' ').split())


def l24_g4_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l24_g4_speech(canonical_word)
    heard = normalize_l24_g4_speech(transcript)
    accepted = {normalize_l24_g4_speech(item) for item in L24_G4_X_ACCEPTED_SPEECH.get(str(canonical_word).casefold(), {canonical})}
    return bool(heard and heard in accepted)


def l22_g6_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l22_g2_speech(canonical_word)
    heard = normalize_l22_g2_speech(transcript)
    accepted = L22_G6_ACCEPTED_SPEECH.get(canonical, {canonical})
    return bool(heard and heard in accepted)


def normalize_l22_g4_speech(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    text = re.sub(r'[^0-9a-z\s]', ' ', text)
    return ' '.join(text.split())


def l22_g4_pronunciation_match(canonical_word, transcript):
    canonical = normalize_l22_g4_speech(canonical_word)
    heard = normalize_l22_g4_speech(transcript)
    accepted = L22_G4_ACCEPTED_SPEECH.get(canonical, {canonical})
    return bool(heard and heard in accepted)


def add(key, page, lesson, number, title, instruction, kind, rows, **config):
    session = 8 if page <= 47 else 9 if page <= 49 else 10 if page <= 51 else 11
    label = f'Lesson {lesson}: Gawain {number}' if lesson else f'Session {session}: Activity {number}'
    item_ids = config.pop('item_ids', None)
    reading_words = config.pop('reading_words', None)
    oral_flow = config.pop('oral_flow', kind not in {'drawing', 'fill'})
    source_words = reading_words if reading_words is not None else [text for row in rows for text in row if text]
    items = [dict(id=f'item-{i + 1}', text=text) for i, text in enumerate(source_words)]
    if item_ids:
        for item, item_id in zip(items, item_ids):
            item['id'] = item_id
    ACTIVITIES[key] = dict(
        activity_key=key, session=session, session_key=f'session-{session}', lesson=lesson, activity_number=number,
        display_label=label, title=title, instruction=instruction,
        printed_page=page, pdf_page=page + 3, interaction_type=kind,
        language='Filipino' if session == 8 else 'English', rows=rows, items=items,
        template_title='ARAL Workbook', template_type='ARAL Workbook',
        template_source='template', activity_type='prescribed_workbook',
        randomize_order=False, oral_flow=oral_flow,
        reading_attempt_limit=3, read_aloud_limit=3, **config,
    )
    if reading_words is not None:
        ACTIVITIES[key]['reading_words'] = list(reading_words)


BOX = 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.'
add('aral-l22-g1-c-syllable-builder', 38, 22, '1', 'Letrang Cc', BOX, 'builder',
    [['cac', 'ce', 'ca'], ['bu', 'com', 'pu'], ['ga', 'tus', 'ter'],
     ['yan', 'Car', 'do'], ['bi', 'ca', 'net'], ['te', 'Ce', 'les']],
    bigbox_cells=[
        [['item-1'], ['item-2'], ['item-3']],
        [['item-4'], ['item-5'], ['item-6']],
        [['item-7'], ['item-8'], ['item-9']],
        [['item-10'], ['item-11'], ['item-12']],
        [['item-13'], ['item-14'], ['item-15']],
        [['item-16'], ['item-17'], ['item-18']],
    ],
    reading_contexts=L22_C_READING_CONTEXTS,
    oral_flow=False, review_required=True, progress_total=1)
add('aral-l22-g2-c-word-reading', 38, 22, '2', 'Mga salitang may letrang C',
    'Basahin ang mga salitang nagtataglay ng hiram na letrang C na may tunog na /k/ at /s/.',
    'reading', [['computer', 'Cebu'], ['cactus', 'Cita'], ['camera', 'Celso'],
                ['cabinet', 'Vicente'], ['Caloocan', 'Celeste'], ['Coron', 'Celsa'], ['Vic', 'Carlos']],
    column_headers=['C = /k/', 'C = /s/'])
add('aral-l22-g3-c-word-search', 39, 22, '3', 'Hanapin ang mga salita: C',
    'Hanapin at kulayan ng paboritong kulay ang sumusunod na salita sa ibaba.', 'search',
    [['computer'], ['Cagayan'], ['camera'], ['cabinet'], ['Cebu'], ['cactus'], ['Cardo'], ['Celeste'], ['Carla']],
    item_labels=['1.', '2.', '3.', '4.', '5.', '3.', '5.', '7.', '8.'],
    grid=['CARLAMREA', 'CAGAYANMS', 'ABCACTUSP', 'NAMHCARDO', 'COMPUTERD', 'OCELESTEM', 'STCABINET', 'CEBUBRTDM', 'ABDCAMERA'],
    mark_style='color')
add('aral-l22-g4-f-syllable-builder', 40, 22, '4', 'Big Box: F',
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng salita mula rito.',
    'builder', [['free', 'fries', 'Fi'], ['Fe', 'na', 'li'], ['lix', 'zer', 'pe']], review_required=True)
add('aral-l22-g5-f-word-search', 40, 22, '5', 'Hanapin ang mga salita: F',
    'Hanapin at bilugan sa loob ng Big Box ang mga salita sa ibaba.', 'search',
    [['freezer'], ['fries'], ['Fina'], ['Filipino'], ['Felix']],
    grid=['MTGFINAE', 'FELIPEGR', 'MFRIESMD', 'FILIPINO', 'FREEZERH', 'SADFELIX'], mark_style='circle')
add('aral-l22-g6-f-word-reading', 41, 22, '6', 'Mga salitang may letrang Ff',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ff.', 'reading',
    [['freezer', 'Felipe'], ['fries', 'Felix'], ['Filipino', 'Ferrer'], ['Fina', 'Faith'], ['Filipiniana', 'Fontana']],
    reading_words=L22_G6_F_WORDS, column_headers=['', ''])


add('aral-l23-g1-n-syllable-builder', 41, 23, '1', 'Big Box: Ñ', BOX, 'builder',
    [['Ni', 'La', 'ña'], ['Cas', 'Bi', 'da'], ['El', 'ño', 'ñan'], ['Cen', 'ta', 'ñe']],
    bigbox_cells=[
        [['item-1'], ['item-2'], ['item-3']],
        [['item-4'], ['item-5'], ['item-6']],
        [['item-7'], ['item-8'], ['item-9']],
        [['item-10'], ['item-11'], ['item-12']],
    ], review_required=True, specialized_builder=True, progress_total=1)
add('aral-l23-g2-n-word-reading', 42, 23, '2', 'Mga salitang may letrang Ññ',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ññ.', 'reading',
    [[word] for word in L23_G2_TARGETS], reading_words=L23_G2_TARGETS)
add('aral-l23-g3-j-word-reading', 42, 23, '3', 'Mga salitang may letrang Jj',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Jj.', 'reading',
    [['Jacket', 'Jennifer', 'jam', 'Jeffrey'], ['pajama', 'Jerry', 'Jojo', 'Jonathan']])
add('aral-l23-g4-j-syllabication', 42, 23, '4', 'Pantigin ang mga salita: J',
    'Pantigin ang sumusunod na salita.', 'syllables', [['jacket'], ['pajama'], ['Jonathan'], ['jam'], ['Joselito']],
    syllable_answers=['jack-et', 'pa-ja-ma', 'Jo-na-than', 'jam', 'Jo-se-li-to'], oral_flow=False)
add('aral-l23-g5-j-word-search', 43, 23, '5', 'Hanapin ang mga salita: J',
    'Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.', 'search',
    [['jacket'], ['pajama'], ['jam'], ['Jonathan'], ['Jennifer']],
    visible_activity_label='GAWAIN 5', grid=[
        ['Z','J','O','N','A','T','H','A','N'],
        ['J','A','M','L','T','Y','Z','S','I'],
        ['J','A','C','K','E','T','E','R','G'],
        ['B','Z','O','P','A','J','A','M','A'],
        ['J','E','N','N','I','F','E','R','M'],
    ], mark_style='circle')
add('aral-l23-g6-q-syllable-builder', 43, 23, '6', 'Big Box: Q',
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salitang.', 'builder',
    [['Que','En','Qui','tos'], ['no','A','Quin','An'], ['ta','ja','na','to'], ['ri','zon','que','ti']],
    visible_activity_label='GAWAIN 6', review_required=True, specialized_builder=True,
    progress_total=16, bigbox_cells=[
        [['item-1'], ['item-2'], ['item-3'], ['item-4']],
        [['item-5'], ['item-6'], ['item-7'], ['item-8']],
        [['item-9'], ['item-10'], ['item-11'], ['item-12']],
        [['item-13'], ['item-14'], ['item-15'], ['item-16']],
    ], canonical_answer_source='Not found in available project/workbook sources.')
add('aral-l23-g7-q-word-reading', 44, 23, '7', 'Mga salitang may letrang Qq',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Qq.', 'reading',
    [['Quisumbing','Quennie','Enriquez','Quintana','Quintos']], visible_activity_label='GAWAIN 7')

add('aral-l24-g1-v-syllable-builder', 44, 24, '1', 'Big Box: V',
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.', 'builder',
    [['lin','sa','van'], ['va','E','la'], ['I','Vi','Vio'], ['le','val','A']],
    item_ids=['r1c1','r1c2','r1c3','r2c1','r2c2','r2c3','r3c1','r3c2','r3c3','r4c1','r4c2','r4c3'],
    bigbox_cells=[
        [['r1c1'], ['r1c2'], ['r1c3']],
        [['r2c1'], ['r2c2'], ['r2c3']],
        [['r3c1'], ['r3c2'], ['r3c3']],
        [['r4c1'], ['r4c2'], ['r4c3']],
    ], review_required=True, specialized_builder=True, progress_total=12,
    canonical_answer_source='Not found in available authoritative workbook/project sources.')
add('aral-l24-g2-v-word-reading', 44, 24, '2', 'Mga salitang may letrang Vv',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv.', 'reading',
    [['Vina','vanilla'], ['Vilma','vila'], ['Victor','vinta'], ['Victoria','van'], ['Valdez','visa'], ['Valle','violin'], ['Visayas','volleybal']], column_headers=['V','v'], reading_words=L24_G2_V_WORDS)
add('aral-l24-g3-x-repeat', 45, 24, '3', 'Pakinggan at ulitin: X',
    'Pakinggang mabuti ang mga salitang bibigkasin ng guro pagkatapos ay ulitin ito.', 'reading',
    [['Alex'], ['Felix'], ['x-factor'], ['fixer']], model_first=True)
add('aral-l24-g4-x-pictures', 45, 24, '4', 'Kilalanin at Basahin',
    'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.', 'reading',
    [['x-ray','fax machine','fox']],
    images={f'item-{i+1}':f'/static/pabasa_app/images/aral_workbook/{name}.png' for i,name in enumerate(['x-ray','fax-machine','fox'])})
add('aral-l24-g3-x-word-reading', 45, 24, '3', 'Mga salitang may letrang Xx',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Xx.', 'reading',
    [['Alex','Xylophone'], ['Alexis','Saxophone'], ['Alexander',''], ['Dixon',''], ['mixer',''], ['Felix','']],
    column_headers=['/X/= ks','/X/=s'])
add('aral-l24-g4-x-syllable-builder', 46, 24, '4', 'Big Box: X', BOX, 'builder',
    [['A','Fe','xe'], ['xy','phone','sax'], ['rox','lex','o'], ['lix','lo','phone']], review_required=True)
add('aral-l24-g5-z-syllabication', 46, 24, '5', 'Pantigin ang mga salita: Z',
    'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo.', 'syllables',
    [['Zandra'], ['Gomez'], ['Zamora'], ['zipper'], ['Zarate'], ['Legazpi'], ['Zoren'], ['zebra'], ['Mendoza']],
    worked_example='1. zigzag = zig•zag', item_labels=[f'{i}.' for i in range(2,11)],
    syllable_answers=['Zan-dra', 'Go-mez', 'Za-mo-ra', 'zip-per', 'Za-ra-te', 'Le-gaz-pi', 'Zo-ren', 'ze-bra', 'Men-do-za'])
add('aral-l24-g6-z-word-search', 47, 24, '6', 'Hanapin ang mga salita: Z',
    'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.', 'search',
    [['zipper'], ['zoo'], ['zebra'], ['zigzag'], ['Perez'], ['Rizal'], ['Zamora'], ['Zam'], ['Zoren'], ['Zeny']],
    grid=['ZAMORATYZ','AAKLTYZSI','MNZIPPERG','BZOOP EBIZ'.replace(' ',''),'AER TERRJA'.replace(' ',''),'LNEYRTAHG','EYNKEDBKL','SMRIZALUK'], mark_style='circle')
add('aral-l24-g7-z-word-reading', 47, 24, '7', 'Mga salitang may letrang Zz',
    'Basahin ang mga salita sa ibaba na may hiram na letrang Zz.', 'reading',
    [['zigzag','Gomez','Zoren'], ['Zandra','Zarate','Legazpi'], ['Zamora','Zaragosa','Zabala'],
     ['Zandro','Zapote','Zambales'], ['Lazaro','Zonrox','Gonzales'], ['Perez','Lopez','Mendoza'],
     ['Rizal','Luzon','Hernandez'], ['Dizon','Zeny','']], visible_activity_label='GAWAIN 7')

add('aral-s9-a1-family-drawing', 48, None, '1', 'My family',
    'Draw a picture of your family. Under your drawing, write the sentence “This is my family.”',
    'drawing', [['This is my family.']], review_required=True, expected_writing=['This is my family.'])
add('aral-s9-a2-helping-drawing', 49, None, '2', 'Helping at home',
    'Draw and color a situation at home where you helped someone. Under your drawing, write the courteous word you used: “Please” / “Sorry” / “Thank you” / “You’re welcome.”',
    'drawing', [['Please / Sorry / Thank you / You’re welcome.']], review_required=True,
    expected_writing=['Please','Sorry','Thank you','You’re welcome.'])
def get_activity(key):
    a = deepcopy(ACTIVITIES.get(key))
    if a and a['interaction_type'] == 'search':
        a['correct_answer_data'] = {i['id']: search_paths(a, i['text']) for i in a['items']}
    return a


def search_paths(activity, text):
    grid = activity['grid']
    word = text.casefold()
    paths = []
    for y, row in enumerate(grid):
        for x in range(len(row)):
            for dy, dx in ((0, 1), (1, 0), (1, 1), (-1, 1), (0, -1), (-1, 0), (-1, -1), (1, -1)):
                path = [[y + i * dy, x + i * dx] for i in range(len(word))]
                if all(0 <= r < len(grid) and 0 <= c < len(grid[r]) for r, c in path):
                    if ''.join(grid[r][c] for r, c in path).casefold() == word:
                        paths.append(path)
    return paths


def initial_state():
    return dict(index=0, oral={}, answers={}, draft={}, completed=False, revision=0)


def initial_l23_g1_state():
    return {
        'index': 0, 'read_aloud_started': False, 'read_aloud_completed': False,
        'reading_attempts': 0, 'reading_phase': 'read',
        'pronunciation_help_played': False, 'last_feedback': '',
        'last_transcript': '', 'found_words': [], 'pending_words': [],
        'draft': {'builder': []}, 'completed': False, 'revision': 0,
    }


def initial_l24_g1_state():
    return {
        'index': 0, 'read_aloud_started': False, 'read_aloud_completed': False,
        'reading_attempts': 0, 'reading_phase': 'read',
        'pronunciation_help_played': False, 'last_feedback': '',
        'last_transcript': '', 'found_words': [], 'pending_words': [],
        'draft': {'builder': []}, 'completed': False, 'revision': 0,
    }


def initial_l22_g2_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


def initial_l22_g6_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


def initial_l24_g2_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


def initial_l24_g4_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


def initial_l23_g2_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


def initial_l23_g3_state():
    return {
        'index': 0, 'completed_words': [], 'reading_attempts': 0,
        'last_feedback': '', 'last_transcript': '', 'completed': False,
        'revision': 0, 'draft': {},
    }


def initial_l23_g7_state():
    return {
        'index': 0, 'completed_words': [], 'reading_attempts': 0,
        'last_feedback': '', 'last_transcript': '', 'completed': False,
        'revision': 0, 'draft': {},
    }


def normalize_l23_g3_state(state):
    total = len(L23_G3_J_WORDS)
    completed_words = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    state['completed_words'] = sorted({int(i) for i in completed_words if str(i).isdigit() and 0 <= int(i) < total})
    state['index'] = max(0, min(total, int(state.get('index') or len(state['completed_words']))))
    state['index'] = max(state['index'], len(state['completed_words']))
    state['reading_attempts'] = max(0, int(state.get('reading_attempts') or 0))
    state.setdefault('last_feedback', '')
    state.setdefault('last_transcript', '')
    state.setdefault('draft', {})
    state['completed'] = bool(state.get('completed')) and state['index'] >= total
    if state['index'] >= total or len(state['completed_words']) >= total:
        state['index'] = total
        state['completed_words'] = list(range(total))
        state['completed'] = True
    return state


def normalize_l23_g7_state(state):
    total = len(L23_G7_Q_WORDS)
    if not isinstance(state, dict):
        state = initial_l23_g7_state()
    completed_words = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    state['completed_words'] = sorted({int(i) for i in completed_words if str(i).isdigit() and 0 <= int(i) < total})
    state['index'] = max(0, min(total, int(state.get('index') or len(state['completed_words']))))
    state['index'] = max(state['index'], len(state['completed_words']))
    state['reading_attempts'] = max(0, int(state.get('reading_attempts') or 0))
    state.setdefault('last_feedback', '')
    state.setdefault('last_transcript', '')
    state.setdefault('draft', {})
    if len(state['completed_words']) >= total or state['index'] >= total:
        state['index'] = total
        state['completed_words'] = list(range(total))
        state['completed'] = True
    else:
        state['completed'] = False
    state['revision'] = max(0, int(state.get('revision') or 0))
    return state


def initial_l23_g4_state():
    return {
        'index': 0, 'answers': {}, 'draft': {'text': ''},
        'last_feedback': '', 'completed': False, 'revision': 0,
    }


def normalize_l23_g4_state(state):
    total = len(L23_G4_SYLLABLE_ANSWERS)
    answers = state.get('answers') if isinstance(state.get('answers'), dict) else {}
    state['answers'] = {str(k): str(v) for k, v in answers.items() if str(k).isdigit() and 0 <= int(k) < total}
    state['index'] = max(0, min(total, int(state.get('index') or len(state['answers']))))
    state['index'] = max(state['index'], len(state['answers']))
    draft = state.get('draft') if isinstance(state.get('draft'), dict) else {}
    state['draft'] = {'text': str(draft.get('text') or '')}
    state.setdefault('last_feedback', '')
    state['completed'] = bool(state.get('completed')) and state['index'] >= total
    if state['index'] >= total or len(state['answers']) >= total:
        state['index'] = total
        state['completed'] = True
    return state


def _apply_l23_g3_reading(state, event, verified_reading):
    normalize_l23_g3_state(state)
    if state['completed']:
        return state
    action = event.get('action')
    if action == 'reading_started':
        state['last_feedback'] = 'Handa ka na.'
        return state
    if action == 'reading':
        action = 'reading_attempt'
    if action != 'reading_attempt':
        raise ValueError('Unknown action.')
    if event.get('item_index') is not None and int(event.get('item_index')) != state['index']:
        raise ValueError('Ito ay hindi na ang kasalukuyang salita.')
    state['last_transcript'] = str(event.get('transcript') or '').strip()
    if verified_reading is None:
        state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
        return state
    if verified_reading:
        index = state['index']
        if index not in state['completed_words']:
            state['completed_words'].append(index)
        state['completed_words'].sort()
        state['index'] = min(len(L23_G3_J_WORDS), index + 1)
        state['reading_attempts'] = 0
        state['completed'] = state['index'] >= len(L23_G3_J_WORDS)
        state['last_feedback'] = 'Mahusay!' if state['completed'] else 'Mahusay!'
    else:
        state['reading_attempts'] = min(99, state['reading_attempts'] + 1)
        state['last_feedback'] = 'Subukan Muli.'
    return state


def _apply_l23_g7_reading(state, event, verified_reading):
    normalize_l23_g7_state(state)
    if state['completed']:
        return state
    action = event.get('action')
    if action == 'reading':
        action = 'reading_attempt'
    if action == 'reading_started':
        state['last_feedback'] = 'Handa ka na.'
        return state
    if action != 'reading_attempt':
        raise ValueError('Unknown action.')
    index = state['index']
    if event.get('item_index') is not None and int(event.get('item_index')) != index:
        raise ValueError('Ito ay hindi na ang kasalukuyang salita.')
    state['last_transcript'] = str(event.get('transcript') or '').strip()
    if verified_reading is None:
        state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
        return state
    if verified_reading:
        if index not in state['completed_words']:
            state['completed_words'].append(index)
        state['completed_words'].sort()
        state['index'] = min(len(L23_G7_Q_WORDS), index + 1)
        state['reading_attempts'] = 0
        state['completed'] = len(state['completed_words']) == len(L23_G7_Q_WORDS)
        state['last_feedback'] = 'Mahusay!'
    else:
        state['reading_attempts'] = min(99, state['reading_attempts'] + 1)
        state['last_feedback'] = 'Subukan Muli.'
    return state


def _apply_l23_g4_syllabication(state, event):
    normalize_l23_g4_state(state)
    if state['completed']:
        return state
    action = event.get('action')
    if action == 'draft':
        draft = event.get('draft') if isinstance(event.get('draft'), dict) else {}
        state['draft'] = {'text': str(draft.get('text') or '')[:500]}
        return state
    if action != 'answer':
        raise ValueError('Unknown action.')
    index = state['index']
    if index >= len(L23_G4_SYLLABLE_ANSWERS):
        return state
    answer = event.get('answer') if isinstance(event.get('answer'), dict) else {}
    text = str(answer.get('text') or '').strip()
    if not text:
        raise ValueError('Isulat muna ang sagot.')
    state['draft'] = {'text': text}
    if normalize_l23_g4_syllables(text) != normalize_l23_g4_syllables(L23_G4_SYLLABLE_ANSWERS[index]):
        state['last_feedback'] = 'Subukan Muli.'
        return state
    state['answers'][str(index)] = text
    state['index'] += 1
    state['draft'] = {'text': ''}
    state['last_feedback'] = 'Mahusay!'
    if state['index'] >= len(L23_G4_SYLLABLE_ANSWERS):
        state['completed'] = True
    return state


def initial_l22_g3_state():
    return {'found_words': {}, 'last_feedback': '', 'completed': False, 'revision': 0}


def initial_l22_g5_state():
    return {'found_words': {}, 'last_feedback': '', 'completed': False, 'revision': 0}


def initial_l23_g5_state():
    return {'found_words': {}, 'last_feedback': '', 'completed': False, 'revision': 0}


def normalize_l23_g1_state(state):
    if not isinstance(state, dict):
        state = initial_l23_g1_state()
    count = len(ACTIVITIES['aral-l23-g1-n-syllable-builder']['items'])
    state['index'] = max(0, min(count, int(state.get('index', 0) or 0)))
    state['read_aloud_started'] = bool(state.get('read_aloud_started'))
    state['read_aloud_completed'] = bool(state.get('read_aloud_completed')) or state['index'] >= count
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['pronunciation_help_played'] = bool(state.get('pronunciation_help_played'))
    state['found_words'] = [w for w in state.get('found_words', []) if w in L23_G1_WORDS]
    state['found_words'] = list(dict.fromkeys(state['found_words']))
    draft = state.get('draft') if isinstance(state.get('draft'), dict) else {}
    allowed = {item['id'] for item in ACTIVITIES['aral-l23-g1-n-syllable-builder']['items']}
    state['draft'] = {'builder': [x for x in draft.get('builder', []) if x in allowed]}
    state['pending_words'] = state.get('pending_words') if isinstance(state.get('pending_words'), list) else []
    if state['read_aloud_completed']:
        state['index'] = count
        state['reading_phase'] = 'complete'
    state['completed'] = bool(state.get('completed')) and state['read_aloud_completed'] and len(state['found_words']) == len(L23_G1_WORDS)
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def l23_g1_pronunciation_match(expected, transcript):
    canonical = unicodedata.normalize('NFKC', str(expected or '')).casefold()
    heard = unicodedata.normalize('NFKC', str(transcript or '')).casefold()
    canonical = re.sub(r'[^a-zñ\s]', ' ', canonical).strip()
    heard_words = [re.sub(r'[^a-zñ]', '', word) for word in heard.split()]
    accepted = L23_G1_ACCEPTED_SPEECH.get(canonical, {canonical})
    return bool(heard_words and any(word in accepted for word in heard_words))


def normalize_l24_g1_speech(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^a-z\s]', ' ', text).split())


def l24_g1_pronunciation_match(expected, transcript):
    canonical = normalize_l24_g1_speech(expected)
    heard = normalize_l24_g1_speech(transcript)
    return bool(heard and heard in L24_G1_ACCEPTED_SPEECH.get(canonical, {canonical}))


def normalize_l24_g1_state(state):
    if not isinstance(state, dict):
        state = initial_l24_g1_state()
    count = len(ACTIVITIES['aral-l24-g1-v-syllable-builder']['items'])
    state['index'] = max(0, min(count, int(state.get('index', 0) or 0)))
    state['read_aloud_started'] = bool(state.get('read_aloud_started'))
    state['read_aloud_completed'] = bool(state.get('read_aloud_completed')) or state['index'] >= count
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['pronunciation_help_played'] = bool(state.get('pronunciation_help_played'))
    state['found_words'] = [w for w in state.get('found_words', []) if w in L24_G1_CANONICAL_WORDS]
    state['found_words'] = list(dict.fromkeys(state['found_words']))
    draft = state.get('draft') if isinstance(state.get('draft'), dict) else {}
    allowed = {item['id'] for item in ACTIVITIES['aral-l24-g1-v-syllable-builder']['items']}
    state['draft'] = {'builder': [x for x in draft.get('builder', []) if x in allowed]}
    state['pending_words'] = state.get('pending_words') if isinstance(state.get('pending_words'), list) else []
    if state['read_aloud_completed']:
        state['index'] = count
        state['reading_phase'] = 'complete'
    state['completed'] = bool(state.get('completed')) and state['read_aloud_completed'] and len(state['found_words']) == len(L24_G1_CANONICAL_WORDS)
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def initial_l23_g6_state():
    return {
        'index': 0, 'read_aloud_started': False, 'read_aloud_completed': False,
        'reading_attempts': 0, 'reading_phase': 'read',
        'pronunciation_help_played': False, 'last_feedback': '',
        'last_transcript': '', 'found_words': [], 'pending_words': [],
        'draft': {'builder': []}, 'completed': False, 'revision': 0,
    }


def normalize_l23_g6_speech(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^a-z\s]', ' ', text).split())


def l23_g6_pronunciation_match(expected, transcript):
    canonical = normalize_l23_g6_speech(expected)
    heard = normalize_l23_g6_speech(transcript)
    return bool(heard and heard in L23_G6_ACCEPTED_SPEECH.get(canonical, {canonical}))


def normalize_l23_g6_state(state):
    if not isinstance(state, dict):
        state = initial_l23_g6_state()
    count = len(ACTIVITIES['aral-l23-g6-q-syllable-builder']['items'])
    state['index'] = max(0, min(count, int(state.get('index', 0) or 0)))
    state['read_aloud_started'] = bool(state.get('read_aloud_started'))
    state['read_aloud_completed'] = bool(state.get('read_aloud_completed')) or state['index'] >= count
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['pronunciation_help_played'] = bool(state.get('pronunciation_help_played'))
    state['found_words'] = []
    state['pending_words'] = state.get('pending_words') if isinstance(state.get('pending_words'), list) else []
    draft = state.get('draft') if isinstance(state.get('draft'), dict) else {}
    allowed = {item['id'] for item in ACTIVITIES['aral-l23-g6-q-syllable-builder']['items']}
    state['draft'] = {'builder': [x for x in draft.get('builder', []) if x in allowed]}
    if state['read_aloud_completed']:
        state['index'] = count
        state['reading_phase'] = 'complete'
    state['completed'] = False
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def _l23_g6_word_for_parts(parts):
    activity = ACTIVITIES['aral-l23-g6-q-syllable-builder']
    pieces = {item['id']: item['text'] for item in activity['items']}
    if not isinstance(parts, list) or not 1 <= len(parts) <= len(pieces) or any(p not in pieces for p in parts):
        return None
    formed = ''.join(pieces[p] for p in parts)
    return next((word for word in L23_G6_CANONICAL_WORDS if formed.casefold() == word.casefold()), None)


def _apply_l23_g6_builder(state, event, verified_reading):
    normalize_l23_g6_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l23_g6_state()); return state
    if action == 'draft':
        draft = event.get('draft', {})
        parts = draft.get('builder', []) if isinstance(draft, dict) else []
        allowed = {item['id'] for item in ACTIVITIES['aral-l23-g6-q-syllable-builder']['items']}
        if not isinstance(parts, list) or len(parts) > len(allowed) or any(part not in allowed for part in parts):
            raise ValueError('Hindi wastong mga pantig.')
        if parts and not state['read_aloud_completed']:
            raise ValueError('Basahin muna ang lahat ng pantig.')
        state['draft'] = {'builder': parts}; state['last_feedback'] = ''; return state
    if action == 'reading_started':
        if state['read_aloud_completed']: raise ValueError('Natapos na ang pagbasa.')
        state.update(read_aloud_started=True, reading_phase='read', last_feedback='', last_transcript=''); return state
    if action == 'reading_syllable_attempt':
        if not state['read_aloud_started']: raise ValueError('Simulan muna ang pagbasa.')
        if state['reading_phase'] != 'read': raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        if event.get('item_index') is not None and int(event.get('item_index')) != state['index']:
            raise ValueError('Ito ay hindi na ang kasalukuyang pantig.')
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            state['index'] = min(len(ACTIVITIES['aral-l23-g6-q-syllable-builder']['items']), state['index'] + 1)
            state['reading_attempts'] = 0; state['last_feedback'] = 'Tama!'
            if state['index'] >= len(ACTIVITIES['aral-l23-g6-q-syllable-builder']['items']):
                state.update(read_aloud_completed=True, reading_phase='complete')
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1); state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3:
                state['reading_phase'] = 'help'; state['pronunciation_help_played'] = False
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help': raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['pronunciation_help_played'] = True; state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help' or not state['pronunciation_help_played']: raise ValueError('Pakinggan muna ang tamang pagbigkas.')
        state.update(reading_phase='read', reading_attempts=0, pronunciation_help_played=False, last_transcript='', last_feedback=''); return state
    if action == 'build_word':
        if not state['read_aloud_completed']: raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        parts = event.get('parts')
        if _l23_g6_word_for_parts(parts) is None:
            state['last_feedback'] = 'Subukan muli. Hindi pa matiyak ang salitang ito.'; state['draft'] = {'builder': []}; return state
        raise ValueError('Bumuo ng ibang salita.')
    if action == 'finish':
        raise ValueError('Canonical word-building answer key could not be verified from the available workbook/project sources.')
    raise ValueError('Unknown action.')


def normalize_l23_g2_speech(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^a-zñ\s]', ' ', text).split())


def l23_g2_pronunciation_match(expected, transcript):
    canonical = normalize_l23_g2_speech(expected)
    heard = normalize_l23_g2_speech(transcript)
    return bool(heard and heard in L23_G2_ACCEPTED_SPEECH.get(canonical, {canonical}))


def initial_l22_g4_state():
    return {
        'reading_index': 0, 'completed_reading': [], 'reading_attempts': 0,
        'reading_phase': 'read', 'last_feedback': '', 'last_transcript': '',
        'draft': [], 'built_words': [], 'completed': False, 'revision': 0,
    }


def normalize_l22_g3_state(state):
    """Keep only legitimate Lesson 22 Gawain 3 word selections and colors."""
    if not isinstance(state, dict):
        state = initial_l22_g3_state()
    found = state.get('found_words') if isinstance(state.get('found_words'), dict) else {}
    clean = {}
    for word, entry in found.items():
        if word not in L22_G3_C_WORD_PATHS or not isinstance(entry, dict):
            continue
        color = str(entry.get('color') or '')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            continue
        path = entry.get('path')
        if path != L22_G3_C_WORD_PATHS[word]:
            continue
        clean[word] = {'path': L22_G3_C_WORD_PATHS[word], 'color': color}
    state['found_words'] = clean
    state['completed'] = bool(state.get('completed')) and len(clean) == len(L22_G3_C_WORD_PATHS)
    if len(clean) == len(L22_G3_C_WORD_PATHS):
        state['completed'] = True
    state.setdefault('last_feedback', '')
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def normalize_l22_g5_state(state):
    """Restore only unique, canonical Gawain 5 coordinate selections."""
    if not isinstance(state, dict):
        state = initial_l22_g5_state()
    found = state.get('found_words') if isinstance(state.get('found_words'), dict) else {}
    clean = {}
    for word, entry in found.items():
        if word not in L22_G5_F_WORD_PATHS or not isinstance(entry, dict):
            continue
        color = str(entry.get('color') or '')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = '#b6e6c3'
        if entry.get('path') != L22_G5_F_WORD_PATHS[word]:
            continue
        clean[word] = {'path': L22_G5_F_WORD_PATHS[word], 'color': color}
    state['found_words'] = clean
    state['completed'] = len(clean) == len(L22_G5_F_WORD_PATHS)
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def normalize_l23_g5_state(state):
    """Restore only unique, canonical Lesson 23 Gawain 5 selections."""
    if not isinstance(state, dict):
        state = initial_l23_g5_state()
    found = state.get('found_words') if isinstance(state.get('found_words'), dict) else {}
    clean = {}
    for word, entry in found.items():
        if word not in L23_G5_J_WORD_PATHS or not isinstance(entry, dict):
            continue
        if entry.get('path') != L23_G5_J_WORD_PATHS[word]:
            continue
        color = str(entry.get('color') or '')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = '#b6e6c3'
        clean[word] = {'path': L23_G5_J_WORD_PATHS[word], 'color': color}
    state['found_words'] = clean
    state['completed'] = len(clean) == len(L23_G5_J_WORD_PATHS)
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def normalize_l22_g4_state(state):
    """Normalize Gawain 4 without restoring transient microphone state."""
    if not isinstance(state, dict):
        state = initial_l22_g4_state()
    completed = state.get('completed_reading') if isinstance(state.get('completed_reading'), list) else []
    state['completed_reading'] = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < 9})
    # The reading gate is contiguous: the next target is derived from the
    # successfully completed entries, never from a client-supplied index.
    state['reading_index'] = min(9, len(state['completed_reading']))
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    allowed = {item['id'] for item in ACTIVITIES['aral-l22-g4-f-syllable-builder']['items']}
    draft = state.get('draft') if isinstance(state.get('draft'), list) else []
    state['draft'] = [str(x) for x in draft if str(x) in allowed]
    built = state.get('built_words') if isinstance(state.get('built_words'), list) else []
    state['built_words'] = []
    for word in built:
        if word in L22_G4_F_WORDS and word not in state['built_words']:
            state['built_words'].append(word)
    if len(state['completed_reading']) == 9:
        state['reading_index'] = 9
        state['reading_phase'] = 'complete'
    state['completed'] = len(state['completed_reading']) == 9 and len(state['built_words']) == len(L22_G4_F_WORDS)
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def _l22_g4_word_for_parts(parts):
    activity = ACTIVITIES['aral-l22-g4-f-syllable-builder']
    piece_by_id = {item['id']: item['text'] for item in activity['items']}
    if not isinstance(parts, list) or not 1 <= len(parts) <= 12 or any(part not in piece_by_id for part in parts):
        return None
    formed = ''.join(piece_by_id[part] for part in parts)
    return next((word for word in L22_G4_F_WORDS if formed.casefold() == word.casefold()), None)


def _apply_l22_g4_builder(state, event, verified_reading):
    normalize_l22_g4_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l22_g4_state()); return state
    if state['completed']:
        return state
    if action == 'reading_started':
        if state['reading_index'] >= 9: raise ValueError('Natapos na ang pagbasa.')
        state['reading_phase'] = 'read'; state['last_feedback'] = ''; return state
    if action == 'reading_attempt':
        if state['reading_phase'] != 'read': raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        index = state['reading_index']
        transcript = str(event.get('transcript') or '').strip()
        state['last_transcript'] = transcript
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            if index not in state['completed_reading']: state['completed_reading'].append(index)
            state['completed_reading'].sort(); state['reading_index'] = min(9, index + 1)
            state['reading_attempts'] = 0; state['reading_phase'] = 'complete' if state['reading_index'] >= 9 else 'read'
            state['last_feedback'] = 'Tama!'
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1)
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3: state['reading_phase'] = 'help'
        normalize_l22_g4_state(state); return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help': raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help': raise ValueError('Hindi pa kailangan ang pag-ulit.')
        state.update(reading_phase='read', reading_attempts=0, last_feedback='', last_transcript=''); return state
    if action == 'draft':
        parts = event.get('parts')
        allowed = {item['id'] for item in ACTIVITIES['aral-l22-g4-f-syllable-builder']['items']}
        if not isinstance(parts, list) or len(parts) > 12 or any(str(part) not in allowed for part in parts):
            raise ValueError('Gumamit ng mga pantig sa Big Box.')
        if state['reading_index'] < 9: raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        state['draft'] = [str(part) for part in parts]; state['last_feedback'] = ''; return state
    if action == 'build_word':
        if state['reading_index'] < 9: raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        parts = event.get('parts')
        word = _l22_g4_word_for_parts(parts)
        if word is None: state['last_feedback'] = 'Subukan muli.'; return state
        if word in state['built_words']: state['last_feedback'] = 'Nabuo mo na ang salitang ito.'; return state
        state['built_words'].append(word); state['draft'] = []; state['last_feedback'] = 'Tama!'
        normalize_l22_g4_state(state); return state
    raise ValueError('Unknown action.')


def _apply_l22_g3_word_search(state, event):
    normalize_l22_g3_state(state)
    if event.get('action') == 'restart':
        state.clear()
        state.update(initial_l22_g3_state())
        return state
    if state['completed']:
        return state
    if event.get('action') != 'select_word':
        raise ValueError('Unknown action.')
    word = str(event.get('word') or '')
    path = event.get('path')
    color = str(event.get('color') or '')
    if word not in L22_G3_C_WORD_PATHS or path != L22_G3_C_WORD_PATHS[word]:
        state['last_feedback'] = 'Subukan muli.'
        return state
    if word in state['found_words']:
        state['last_feedback'] = 'Nahanap mo na ang salitang ito.'
        return state
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = '#b6e6c3'
    state['found_words'][word] = {'path': L22_G3_C_WORD_PATHS[word], 'color': color}
    state['last_feedback'] = f'Tama! Nahanap mo ang {word}.'
    if len(state['found_words']) == len(L22_G3_C_WORD_PATHS):
        state['completed'] = True
        state['last_feedback'] = 'Magaling! Nahanap mo ang lahat ng salita!'
    return state


def _apply_l22_g5_word_search(state, event):
    normalize_l22_g5_state(state)
    if event.get('action') == 'restart':
        state.clear()
        state.update(initial_l22_g5_state())
        return state
    if state['completed']:
        return state
    if event.get('action') != 'select_word':
        raise ValueError('Unknown action.')
    word = str(event.get('word') or '')
    path = event.get('path')
    if word not in L22_G5_F_WORD_PATHS or path != L22_G5_F_WORD_PATHS[word]:
        state['last_feedback'] = 'Subukan muli.'
        return state
    if word in state['found_words']:
        state['last_feedback'] = 'Nahanap mo na ang salitang ito.'
        return state
    color = str(event.get('color') or '')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = '#b6e6c3'
    state['found_words'][word] = {'path': L22_G5_F_WORD_PATHS[word], 'color': color}
    state['last_feedback'] = f'Tama! Nahanap mo ang {word}.'
    if len(state['found_words']) == len(L22_G5_F_WORD_PATHS):
        state['completed'] = True
        state['last_feedback'] = 'Magaling! Nahanap mo ang lahat ng salita!'
    return state


def _apply_l23_g5_word_search(state, event):
    normalize_l23_g5_state(state)
    if event.get('action') == 'restart':
        state.clear(); state.update(initial_l23_g5_state()); return state
    if state['completed']:
        return state
    if event.get('action') != 'select_word':
        raise ValueError('Unknown action.')
    word = str(event.get('word') or '')
    path = event.get('path')
    if word not in L23_G5_J_WORD_PATHS or path != L23_G5_J_WORD_PATHS[word]:
        state['last_feedback'] = 'Subukan Muli.'
        return state
    if word in state['found_words']:
        state['last_feedback'] = 'Nahanap mo na ito.'
        return state
    color = str(event.get('color') or '')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = '#b6e6c3'
    state['found_words'][word] = {'path': L23_G5_J_WORD_PATHS[word], 'color': color}
    state['last_feedback'] = 'Mahusay!'
    if len(state['found_words']) == len(L23_G5_J_WORD_PATHS):
        state['completed'] = True
        state['last_feedback'] = 'Magaling! Nahanap mo ang lahat ng salita!'
    return state


def normalize_l22_g2_state(state):
    """Keep Gawain 2 progress contiguous and safe to resume after navigation."""
    if not isinstance(state, dict):
        state = initial_l22_g2_state()
    completed = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    completed = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < len(L22_G2_C_WORDS)})
    expected = list(range(len(completed)))
    completed = completed if completed == expected else expected
    state['completed_words'] = completed
    state['sequence_index'] = max(0, min(len(L22_G2_C_WORDS), int(state.get('sequence_index', len(completed)) or 0)))
    state['index'] = state['sequence_index']
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help'} else 'read'
    state.setdefault('last_feedback', '')
    state.setdefault('last_transcript', '')
    state['completed'] = bool(state.get('completed')) or len(completed) == len(L22_G2_C_WORDS)
    if state['completed']:
        state['sequence_index'] = state['index'] = len(L22_G2_C_WORDS)
        state['reading_phase'] = 'complete'
    return state


def _apply_l22_g2_reading(state, event, verified_reading):
    normalize_l22_g2_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear()
        state.update(initial_l22_g2_state())
        return state
    if state['completed']:
        return state
    if action == 'reading_started':
        state['reading_phase'] = 'read'
        state['last_feedback'] = ''
        return state
    if action == 'reading_attempt':
        if state['reading_phase'] != 'read':
            raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        transcript = str(event.get('transcript') or '').strip()
        state['last_transcript'] = transcript
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
            return state
        if verified_reading:
            state['completed_words'].append(state['sequence_index'])
            state['sequence_index'] += 1
            state['index'] = state['sequence_index']
            state['reading_attempts'] = 0
            state['reading_phase'] = 'complete' if state['sequence_index'] >= len(L22_G2_C_WORDS) else 'read'
            state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 2.' if state['reading_phase'] == 'complete' else 'Tama!'
            state['completed'] = state['reading_phase'] == 'complete'
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1)
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3:
                state['reading_phase'] = 'help'
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help':
            raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['last_feedback'] = ''
        return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help':
            raise ValueError('Hindi pa kailangan ang pag-ulit.')
        state.update(reading_phase='read', reading_attempts=0, last_feedback='', last_transcript='')
        return state
    raise ValueError('Unknown action.')


def normalize_l23_g2_state(state):
    if not isinstance(state, dict):
        state = initial_l23_g2_state()
    completed = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    completed = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < len(L23_G2_TARGETS)})
    expected = list(range(len(completed)))
    state['completed_words'] = completed if completed == expected else expected
    state['sequence_index'] = max(0, min(len(L23_G2_TARGETS), int(state.get('sequence_index', len(completed)) or 0)))
    state['index'] = state['sequence_index']
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['completed'] = bool(state.get('completed')) or len(completed) == len(L23_G2_TARGETS)
    if state['completed']:
        state['sequence_index'] = state['index'] = len(L23_G2_TARGETS)
        state['reading_phase'] = 'complete'
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def _apply_l23_g2_reading(state, event, verified_reading):
    normalize_l23_g2_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l23_g2_state()); return state
    if state['completed']:
        return state
    if action == 'reading_started':
        state['reading_phase'] = 'read'; state['last_feedback'] = ''; return state
    if action == 'reading_attempt':
        if state['reading_phase'] != 'read':
            raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            index = state['sequence_index']
            if index not in state['completed_words']:
                state['completed_words'].append(index)
            state['completed_words'].sort()
            state['sequence_index'] = state['index'] = min(len(L23_G2_TARGETS), index + 1)
            state['reading_attempts'] = 0
            state['completed'] = state['sequence_index'] >= len(L23_G2_TARGETS)
            state['reading_phase'] = 'complete' if state['completed'] else 'read'
            state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 2.' if state['completed'] else 'Tama!'
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1)
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3: state['reading_phase'] = 'help'
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help':
            raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help':
            raise ValueError('Hindi pa kailangan ang pag-ulit.')
        state.update(reading_phase='read', reading_attempts=0, last_feedback='', last_transcript=''); return state
    raise ValueError('Unknown action.')


def normalize_l22_g6_state(state):
    """Keep Gawain 6 progress contiguous and clear transient recorder state."""
    if not isinstance(state, dict):
        state = initial_l22_g6_state()
    completed = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    completed = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < len(L22_G6_F_WORDS)})
    expected = list(range(len(completed)))
    state['completed_words'] = completed if completed == expected else expected
    state['sequence_index'] = max(0, min(len(L22_G6_F_WORDS), int(state.get('sequence_index', len(state['completed_words'])) or 0)))
    state['index'] = state['sequence_index']
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['completed'] = bool(state.get('completed')) or len(state['completed_words']) == len(L22_G6_F_WORDS)
    if state['completed']:
        state['sequence_index'] = state['index'] = len(L22_G6_F_WORDS)
        state['reading_phase'] = 'complete'
    return state


def normalize_l24_g2_state(state):
    if not isinstance(state, dict):
        state = initial_l24_g2_state()
    completed = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    completed = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < len(L24_G2_V_WORDS)})
    expected = list(range(len(completed)))
    state['completed_words'] = completed if completed == expected else expected
    state['sequence_index'] = max(0, min(len(L24_G2_V_WORDS), int(state.get('sequence_index', len(completed)) or 0)))
    state['index'] = state['sequence_index']
    state['reading_attempts'] = max(0, min(3, int(state.get('reading_attempts', 0) or 0)))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'help', 'complete'} else 'read'
    state['last_feedback'] = str(state.get('last_feedback') or '')
    state['last_transcript'] = str(state.get('last_transcript') or '')
    state['completed'] = bool(state.get('completed')) or len(completed) == len(L24_G2_V_WORDS)
    if state['completed']:
        state['sequence_index'] = state['index'] = len(L24_G2_V_WORDS)
        state['reading_phase'] = 'complete'
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def _apply_l24_g2_reading(state, event, verified_reading):
    normalize_l24_g2_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l24_g2_state()); return state
    if state['completed']:
        return state
    if action == 'reading_started':
        state['reading_phase'] = 'read'; state['last_feedback'] = ''; return state
    if action == 'reading_attempt':
        if state['reading_phase'] != 'read':
            raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        if event.get('item_index') is not None and int(event['item_index']) != state['sequence_index']:
            return state
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            index = state['sequence_index']
            if index not in state['completed_words']:
                state['completed_words'].append(index)
            state['completed_words'].sort()
            state['sequence_index'] = state['index'] = min(len(L24_G2_V_WORDS), index + 1)
            state['reading_attempts'] = 0
            state['completed'] = state['sequence_index'] >= len(L24_G2_V_WORDS)
            state['reading_phase'] = 'complete' if state['completed'] else 'read'
            state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 2.' if state['completed'] else 'Tama!'
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1)
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3: state['reading_phase'] = 'help'
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help':
            raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help': raise ValueError('Hindi pa kailangan ang pag-ulit.')
        state.update(reading_phase='read', reading_attempts=0, last_feedback='', last_transcript=''); return state
    raise ValueError('Unknown action.')


def normalize_l24_g4_state(state):
    total = len(L24_G4_X_WORDS)
    completed = state.get('completed_words') if isinstance(state.get('completed_words'), list) else []
    state['completed_words'] = sorted({int(i) for i in completed if str(i).isdigit() and 0 <= int(i) < total})
    state['index'] = max(0, min(total, int(state.get('index') or len(state['completed_words']))))
    state['index'] = max(state['index'], len(state['completed_words']))
    state['sequence_index'] = state['index']
    state['reading_attempts'] = max(0, int(state.get('reading_attempts') or 0))
    state['reading_phase'] = state.get('reading_phase') if state.get('reading_phase') in {'read', 'complete'} else 'read'
    state.setdefault('last_feedback', '')
    state.setdefault('last_transcript', '')
    state['completed'] = bool(state.get('completed')) or state['index'] >= total
    if state['completed']:
        state['index'] = state['sequence_index'] = total
        state['completed_words'] = list(range(total))
        state['reading_phase'] = 'complete'
    state['revision'] = max(0, int(state.get('revision', 0) or 0))
    return state


def _apply_l24_g4_reading(state, event, verified_reading):
    normalize_l24_g4_state(state)
    if state['completed']:
        return state
    action = event.get('action')
    if action == 'reading_started':
        state['last_feedback'] = 'Handa ka na.'
        return state
    if action not in {'reading', 'reading_attempt'}:
        raise ValueError('Unknown action.')
    index = state['index']
    if event.get('item_index') is not None and int(event['item_index']) != index:
        return state
    state['last_transcript'] = str(event.get('transcript') or '').strip()
    if verified_reading is None:
        state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
        return state
    if verified_reading:
        if index not in state['completed_words']:
            state['completed_words'].append(index)
            state['completed_words'].sort()
        state['index'] = state['sequence_index'] = min(len(L24_G4_X_WORDS), index + 1)
        state['reading_attempts'] = 0
        state['completed'] = state['index'] >= len(L24_G4_X_WORDS)
        state['reading_phase'] = 'complete' if state['completed'] else 'read'
        state['last_feedback'] = 'Magaling! Natapos mo ang gawain.' if state['completed'] else 'Tama! Magaling!'
    else:
        state['reading_attempts'] += 1
        state['last_feedback'] = 'Subukan muli.'
    return state


def _apply_l22_g6_reading(state, event, verified_reading):
    normalize_l22_g6_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l22_g6_state()); return state
    if state['completed']:
        return state
    if action == 'reading_started':
        state['reading_phase'] = 'read'; state['last_feedback'] = ''; return state
    if action == 'reading_attempt':
        if state['reading_phase'] != 'read':
            raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
            return state
        if verified_reading:
            index = state['sequence_index']
            if index not in state['completed_words']:
                state['completed_words'].append(index)
            state['completed_words'].sort()
            state['sequence_index'] = state['index'] = min(len(L22_G6_F_WORDS), index + 1)
            state['reading_attempts'] = 0
            state['completed'] = state['sequence_index'] >= len(L22_G6_F_WORDS)
            state['reading_phase'] = 'complete' if state['completed'] else 'read'
            state['last_feedback'] = 'Tama!' if not state['completed'] else 'Magaling!'
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1)
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3: state['reading_phase'] = 'help'
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help':
            raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help':
            raise ValueError('Hindi pa kailangan ang pag-ulit.')
        state.update(reading_phase='read', reading_attempts=0, last_feedback='', last_transcript=''); return state
    raise ValueError('Unknown action.')


def _oral(state, item, model_first=False):
    return state['oral'].setdefault(item['id'], dict(passed=False, attempts=0, listens=0, phase='model' if model_first else 'read'))


def _l22_c_word_for_parts(parts):
    activity = ACTIVITIES['aral-l22-g1-c-syllable-builder']
    piece_by_id = {item['id']: item['text'] for item in activity['items']}
    if not isinstance(parts, list) or not 1 <= len(parts) <= 15 or any(part not in piece_by_id for part in parts):
        return None
    formed = tuple(piece_by_id[part] for part in parts)
    return next((word for word, pieces in L22_C_ACCEPTED_BUILDS.items() if formed == pieces), None)


def _normalize_l22_c_parts(parts):
    """Convert the legacy co + m selection into the current single com tile."""
    if not isinstance(parts, list):
        return parts
    normalized = []
    for part in parts:
        if part == 'item-19' and normalized[-1:] == ['item-5']:
            continue
        normalized.append(part)
    return normalized


def normalize_l22_c_state(state):
    """Upgrade saved pre-specialized Gawain 1 state without trusting old word answers."""
    legacy_index = int(state.get('index') or 0)
    oral = state.get('oral') if isinstance(state.get('oral'), dict) else {}
    item_count = len(ACTIVITIES['aral-l22-g1-c-syllable-builder']['items'])
    legacy_read = legacy_index > item_count or legacy_index >= item_count and bool(state.get('read_aloud_completed'))
    if 'read_aloud_completed' not in state:
        state['read_aloud_completed'] = legacy_read
    if 'read_aloud_started' not in state:
        state['read_aloud_started'] = legacy_read or legacy_index > 0 or bool(oral)
    if 'found_words' not in state:
        state['found_words'] = []
        saved_words = state.get('answers', {}).get('item-18', [])
        if not saved_words and isinstance(state.get('draft'), dict):
            saved_words = state['draft'].get('words', [])
        if isinstance(saved_words, list):
            for parts in saved_words:
                word = _l22_c_word_for_parts(_normalize_l22_c_parts(parts))
                if word and word.casefold() not in {str(existing).casefold() for existing in state['found_words']}:
                    state['found_words'].append(word)
    state.setdefault('last_feedback', '')
    state.setdefault('last_transcript', '')
    state.setdefault('pending_words', [])
    state.setdefault('reading_attempts', 0)
    state.setdefault('read_aloud_listens', 0)
    state.setdefault('reading_phase', 'complete' if state.get('read_aloud_completed') else 'read')
    state.setdefault('pronunciation_help_played', False)
    if state.get('reading_phase') == 'listen':
        state['reading_phase'] = 'help'
        state['pronunciation_help_played'] = bool(state.get('read_aloud_listens'))
    if isinstance(state.get('draft'), dict) and isinstance(state['draft'].get('builder'), list):
        state['draft']['builder'] = _normalize_l22_c_parts(state['draft']['builder'])
    if state.get('read_aloud_completed'):
        state['index'] = item_count
    if state.get('completed') and (not state['read_aloud_completed'] or not state['found_words']):
        state['completed'] = False
        state['index'] = 0
    elif state.get('completed'):
        state['index'] = 1
    return state


def _l23_g1_word_for_parts(parts):
    activity = ACTIVITIES['aral-l23-g1-n-syllable-builder']
    pieces = {item['id']: item['text'] for item in activity['items']}
    if not isinstance(parts, list) or not 1 <= len(parts) <= 12 or any(p not in pieces for p in parts):
        return None
    formed = ''.join(pieces[p] for p in parts)
    return next((word for word in L23_G1_WORDS if formed.casefold() == word.casefold()), None)


def _apply_l23_g1_builder(state, event, verified_reading):
    normalize_l23_g1_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l23_g1_state()); return state
    if state['completed']:
        return state
    if action == 'draft':
        draft = event.get('draft', {})
        if not isinstance(draft, dict) or len(json.dumps(draft)) > 350000:
            raise ValueError('Hindi na-save ang iyong sagot. Subukan muli.')
        parts = draft.get('builder', [])
        allowed = {item['id'] for item in ACTIVITIES['aral-l23-g1-n-syllable-builder']['items']}
        if not isinstance(parts, list) or len(parts) > 12 or any(part not in allowed for part in parts):
            raise ValueError('Hindi wastong mga pantig.')
        if parts and not state['read_aloud_completed']:
            raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        state['draft'] = {'builder': parts}; state['last_feedback'] = ''; return state
    if action == 'reading_started':
        if state['read_aloud_completed']: raise ValueError('Natapos na ang pagbasa.')
        state.update(read_aloud_started=True, reading_phase='read', last_feedback='', last_transcript=''); return state
    if action == 'reading_syllable_attempt':
        if not state['read_aloud_started']: raise ValueError('Simulan muna ang pagbasa.')
        if state['reading_phase'] != 'read': raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            state['index'] += 1; state['reading_attempts'] = 0; state['last_feedback'] = 'Tama!'
            if state['index'] >= len(ACTIVITIES['aral-l23-g1-n-syllable-builder']['items']):
                state.update(index=12, read_aloud_completed=True, reading_phase='complete')
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1); state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3:
                state['reading_phase'] = 'help'; state['pronunciation_help_played'] = False
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help': raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['pronunciation_help_played'] = True; state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help' or not state['pronunciation_help_played']: raise ValueError('Pakinggan muna ang tamang pagbigkas.')
        state.update(reading_phase='read', reading_attempts=0, pronunciation_help_played=False, last_transcript='', last_feedback=''); return state
    if action == 'build_word':
        if not state['read_aloud_completed']: raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        parts = event.get('parts')
        accepted = _l23_g1_word_for_parts(parts)
        if accepted is None:
            state['last_feedback'] = 'Subukan muli.'; state['draft'] = {'builder': []}; return state
        if accepted in state['found_words']: raise ValueError('Bumuo ng ibang salita.')
        state['found_words'].append(accepted); state['draft'] = {'builder': []}; state['last_feedback'] = 'Tama!'; return state
    if action == 'finish':
        if not state['read_aloud_completed'] or len(state['found_words']) != len(L23_G1_WORDS):
            raise ValueError('Bumuo muna ng lahat ng wastong salita.')
        state['completed'] = True; state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 1.'; return state
    raise ValueError('Unknown action.')


def _apply_l24_g1_builder(state, event, verified_reading):
    normalize_l24_g1_state(state)
    action = event.get('action')
    if action == 'restart':
        state.clear(); state.update(initial_l24_g1_state()); return state
    if state['completed']:
        return state
    if action == 'draft':
        draft = event.get('draft', {})
        if not isinstance(draft, dict) or len(json.dumps(draft)) > 350000:
            raise ValueError('Hindi na-save ang iyong sagot. Subukan muli.')
        parts = draft.get('builder', [])
        allowed = {item['id'] for item in ACTIVITIES['aral-l24-g1-v-syllable-builder']['items']}
        if not isinstance(parts, list) or len(parts) > 12 or any(part not in allowed for part in parts):
            raise ValueError('Hindi wastong mga pantig.')
        if parts and not state['read_aloud_completed']:
            raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        state['draft'] = {'builder': parts}; state['last_feedback'] = ''; return state
    if action == 'reading_started':
        if state['read_aloud_completed']: raise ValueError('Natapos na ang pagbasa.')
        state.update(read_aloud_started=True, reading_phase='read', last_feedback='', last_transcript=''); return state
    if action == 'reading_syllable_attempt':
        if not state['read_aloud_started']: raise ValueError('Simulan muna ang pagbasa.')
        if state['reading_phase'] != 'read': raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        expected_index = state['index']
        if event.get('item_index') is not None and int(event['item_index']) != expected_index:
            return state
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'; return state
        if verified_reading:
            state['index'] = min(len(ACTIVITIES['aral-l24-g1-v-syllable-builder']['items']), expected_index + 1)
            state['reading_attempts'] = 0; state['last_feedback'] = 'Tama!'
            if state['index'] >= len(ACTIVITIES['aral-l24-g1-v-syllable-builder']['items']):
                state.update(read_aloud_completed=True, reading_phase='complete')
        else:
            state['reading_attempts'] = min(3, state['reading_attempts'] + 1); state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3:
                state['reading_phase'] = 'help'; state['pronunciation_help_played'] = False
        return state
    if action == 'read_aloud':
        if state['reading_phase'] != 'help': raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['pronunciation_help_played'] = True; state['last_feedback'] = ''; return state
    if action == 'retry_reading':
        if state['reading_phase'] != 'help' or not state['pronunciation_help_played']: raise ValueError('Pakinggan muna ang tamang pagbigkas.')
        state.update(reading_phase='read', reading_attempts=0, pronunciation_help_played=False, last_transcript='', last_feedback=''); return state
    if action == 'build_word':
        if not state['read_aloud_completed']: raise ValueError('Basahin muna ang lahat ng nasa Big Box.')
        state['last_feedback'] = 'Hindi pa available ang opisyal na sagot. Subukan muli.'
        state['draft'] = {'builder': []}
        return state
    if action == 'finish':
        if not state['read_aloud_completed'] or len(state['found_words']) != len(L24_G1_CANONICAL_WORDS):
            raise ValueError('Hindi pa nabe-verify ang mga wastong salita.')
        state['completed'] = True; state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 1.'; return state
    raise ValueError('Unknown action.')


def apply_event(activity, state, event, verified_reading=None):
    """Advance only the current item's required phases; never trust client scores."""
    if activity['activity_key'] in {'aral-l22-g6-f-word-reading', 'aral-l23-g2-n-word-reading'} and event.get('action') == 'reading':
        event = dict(event, action='reading_attempt')
    if activity['activity_key'] == 'aral-l22-g2-c-word-reading':
        return _apply_l22_g2_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l22-g6-f-word-reading':
        return _apply_l22_g6_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l24-g2-v-word-reading':
        return _apply_l24_g2_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l24-g4-x-pictures':
        return _apply_l24_g4_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g2-n-word-reading':
        return _apply_l23_g2_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g3-j-word-reading':
        return _apply_l23_g3_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g7-q-word-reading':
        return _apply_l23_g7_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g4-j-syllabication':
        return _apply_l23_g4_syllabication(state, event)
    if activity['activity_key'] == 'aral-l22-g3-c-word-search':
        return _apply_l22_g3_word_search(state, event)
    if activity['activity_key'] == 'aral-l22-g5-f-word-search':
        return _apply_l22_g5_word_search(state, event)
    if activity['activity_key'] == 'aral-l23-g5-j-word-search':
        return _apply_l23_g5_word_search(state, event)
    # Keep the legacy generic state shape usable by older workbook tests and
    # imported draft states; persisted learner progress uses reading_index and
    # therefore always takes the complete specialized flow below.
    if activity['activity_key'] == 'aral-l22-g4-f-syllable-builder' and 'reading_index' in state:
        return _apply_l22_g4_builder(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l22-g1-c-syllable-builder':
        normalize_l22_c_state(state)
        if state['completed']:
            return state
        return _apply_l22_c_builder(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g1-n-syllable-builder':
        return _apply_l23_g1_builder(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l24-g1-v-syllable-builder':
        return _apply_l24_g1_builder(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l23-g6-q-syllable-builder':
        return _apply_l23_g6_builder(state, event, verified_reading)
    if state['completed']:
        return state
    items = activity['items']
    index = state['index']
    action = event.get('action')
    item = items[index] if index < len(items) else None
    if action == 'draft':
        draft = event.get('draft', {})
        if not isinstance(draft, dict) or len(json.dumps(draft)) > 350000:
            raise ValueError('Invalid draft.')
        state['draft'] = draft
        return state
    if action == 'finish':
        if index != len(items):
            raise ValueError('Complete every required part first.')
        state['completed'] = True
        return state
    if item is None:
        raise ValueError('All items have been submitted.')
    oral = _oral(state, item, activity.get('model_first', False))
    if action == 'reading':
        if not activity['oral_flow'] or oral['phase'] != 'read' or oral['passed']:
            raise ValueError('Reading is not available in this phase.')
        if verified_reading is None:
            raise ValueError('A verified recording is required.')
        if verified_reading:
            oral['passed'] = True
        else:
            oral['attempts'] += 1
            if oral['attempts'] == 3:
                oral.update(phase='listen', listens=0)
    elif action == 'model_listened':
        if not activity.get('model_first') or oral['phase'] != 'model':
            raise ValueError('Listen to the model at the start of this item.')
        oral.update(phase='read', model_heard=True)
    elif action == 'listened':
        if oral['phase'] != 'listen':
            raise ValueError('Read Aloud is not available in this phase.')
        oral['listens'] += 1
        if oral['listens'] == 3:
            oral.update(phase='read', attempts=0, listens=0)
    elif action == 'answer':
        if activity['oral_flow'] and not oral['passed']:
            raise ValueError('Read this item first.')
        kind = activity['interaction_type']
        answer = event.get('answer')
        if kind == 'search':
            if answer not in search_paths(activity, item['text']):
                raise ValueError('Select the complete word in a straight line.')
            color = state['draft'].get('color', '#b6e6c3')
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(color)):
                color = '#b6e6c3'
            state.setdefault('mark_colors', {})[item['id']] = color
        elif kind == 'builder':
            # The oral portion traverses the exact grid; the open word-building
            # portion is saved separately at the last syllable.
            if index == len(items) - 1:
                if not isinstance(answer, list) or not 1 <= len(answer) <= 30:
                    raise ValueError('Build at least one word from the Big Box.')
                pool = {i['id']: i['text'] for i in items}
                if any(not isinstance(word, list) or not 1 <= len(word) <= 15
                       or any(part not in pool for part in word) for word in answer):
                    raise ValueError('Use the syllables in the Big Box.')
        elif kind in {'syllables', 'fill', 'drawing'}:
            if not isinstance(answer, dict) or len(json.dumps(answer)) > 350000:
                raise ValueError('Invalid written answer.')
            if kind == 'fill':
                choices = answer.get('blanks')
                if (not isinstance(choices, list) or len(choices) != activity['blanks'][index]
                        or any(c not in activity['options'] for c in choices)):
                    raise ValueError('Choose a word for every blank.')
                answer['text'] = ' / '.join(choices)
            if not isinstance(answer.get('text'), str) or not answer['text'].strip():
                raise ValueError('Write your answer first.')
            if kind == 'syllables':
                compact = re.sub(r'[\s•.\-·]+', '', answer['text']).casefold()
                expected = re.sub(r'[\s•.\-·]+', '', activity['syllable_answers'][index]).casefold()
                if compact != expected:
                    raise ValueError('Use all the letters of the given word, in order.')
            if kind == 'drawing':
                strokes = answer.get('strokes')
                if not isinstance(strokes, list) or not 1 <= len(strokes) <= 1000:
                    raise ValueError('Draw your picture first.')
                for stroke in strokes:
                    if (not isinstance(stroke, dict) or not re.fullmatch(r'#[0-9a-fA-F]{6}', str(stroke.get('color')))
                            or not isinstance(stroke.get('points'), list) or not 2 <= len(stroke['points']) <= 3000
                            or any(not isinstance(p, list) or len(p) != 2 or any(type(n) not in (int, float) or not 0 <= n <= 900 for n in p) for p in stroke['points'])):
                        raise ValueError('Invalid drawing. Please redraw the affected stroke.')
                norm = lambda value: re.sub(r'[.\s]+$', '', value.strip()).replace('’', "'").casefold()
                if norm(answer['text']) not in [norm(x) for x in activity['expected_writing']]:
                    raise ValueError('Use the sentence or courteous words in the instruction.')
        state['answers'][item['id']] = answer
        state['index'] += 1
        state['draft'] = {}
    else:
        raise ValueError('Unknown action.')
    return state


def _apply_l22_c_builder(state, event, verified_reading):
    """Persist the reading gate and validated word attempts for Lesson 22 Gawain 1."""
    action = event.get('action')
    state.setdefault('read_aloud_started', False)
    state.setdefault('read_aloud_completed', False)
    state.setdefault('found_words', [])
    state.setdefault('pending_words', [])
    state.setdefault('last_feedback', '')

    if action == 'draft':
        draft = event.get('draft', {})
        if not isinstance(draft, dict) or len(json.dumps(draft)) > 350000:
            raise ValueError('Hindi na-save ang iyong sagot. Subukan muli.')
        parts = _normalize_l22_c_parts(draft.get('builder', []))
        allowed_ids = {item['id'] for item in ACTIVITIES[
            'aral-l22-g1-c-syllable-builder']['items']}
        if (not isinstance(parts, list) or len(parts) > 15
                or any(part not in allowed_ids for part in parts)):
            raise ValueError('Hindi wastong mga pantig.')
        if parts and not state['read_aloud_completed']:
            raise ValueError('Basahin muna ang mga pantig.')
        state['draft'] = {'builder': parts}
        state['last_feedback'] = ''
        return state
    if action == 'reading_started':
        if state['read_aloud_completed']:
            raise ValueError('Natapos na ang pagbasa.')
        state['read_aloud_started'] = True
        state['reading_phase'] = 'read'
        state['last_transcript'] = ''
        return state
    if action == 'reading_attempt':
        # Keep the pre-specialized event compatible with saved/test clients.
        if not state['read_aloud_started']:
            raise ValueError('Simulan muna ang pagbasa.')
        if verified_reading is not True:
            raise ValueError('Hindi nakuha ang pagbasa. Subukan muli.')
        state['read_aloud_completed'] = True
        state['index'] = len(ACTIVITIES['aral-l22-g1-c-syllable-builder']['items'])
        state['reading_phase'] = 'complete'
        state['last_feedback'] = ''
        return state
    if action == 'reading_syllable_attempt':
        if not state['read_aloud_started']:
            raise ValueError('Simulan muna ang pagbasa.')
        if state.get('reading_phase') != 'read':
            raise ValueError('Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.')
        state['last_transcript'] = str(event.get('transcript') or '').strip()
        if verified_reading is None:
            state['last_feedback'] = 'Hindi ko malinaw na narinig. Subukan muli.'
            return state
        if verified_reading is True:
            item_count = len(ACTIVITIES['aral-l22-g1-c-syllable-builder']['items'])
            state['index'] = min(item_count, int(state.get('index', 0)) + 1)
            state['reading_attempts'] = 0
            state['last_feedback'] = 'Tama!'
            if state['index'] >= item_count:
                state['read_aloud_completed'] = True
                state['reading_phase'] = 'complete'
        else:
            state['reading_attempts'] = int(state.get('reading_attempts', 0)) + 1
            state['last_feedback'] = 'Subukan muli.'
            if state['reading_attempts'] >= 3:
                state['reading_phase'] = 'help'
                state['pronunciation_help_played'] = False
        return state
    if action == 'read_aloud':
        if state.get('reading_phase') != 'help':
            raise ValueError('Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.')
        state['pronunciation_help_played'] = True
        state['last_feedback'] = ''
        return state
    if action == 'retry_reading':
        if state.get('reading_phase') != 'help' or not state.get('pronunciation_help_played'):
            raise ValueError('Pakinggan muna ang tamang pagbigkas.')
        state['reading_phase'] = 'read'
        state['reading_attempts'] = 0
        state['pronunciation_help_played'] = False
        state['last_transcript'] = ''
        state['last_feedback'] = ''
        return state
    if action == 'build_word':
        if not state['read_aloud_completed']:
            raise ValueError('Basahin muna ang mga pantig.')
        parts = _normalize_l22_c_parts(event.get('parts'))
        activity = ACTIVITIES['aral-l22-g1-c-syllable-builder']
        piece_by_id = {item['id']: item['text'] for item in activity['items']}
        if (not isinstance(parts, list) or not 1 <= len(parts) <= 15
                or any(part not in piece_by_id for part in parts)):
            raise ValueError('Gumamit ng mga pantig sa Big Box.')
        accepted = _l22_c_word_for_parts(parts)
        if accepted is None:
            candidate = ''.join(piece_by_id[part] for part in parts)
            pending = state['pending_words']
            if len(pending) >= 30:
                raise ValueError('Subukan muli.')
            if candidate.casefold() not in {str(word.get('word', '')).casefold() for word in pending}:
                pending.append({'word': candidate, 'parts': list(parts)})
            state['last_feedback'] = 'Subukan muli. Hindi pa matiyak ang salitang ito.'
            return state
        found = {str(word).casefold() for word in state['found_words']}
        if accepted.casefold() in found:
            raise ValueError('Bumuo ng ibang salita.')
        state['found_words'].append(accepted)
        state['draft'] = {'builder': []}
        state['last_feedback'] = 'Tama!'
        return state
    if action == 'finish':
        if not state['read_aloud_completed']:
            raise ValueError('Tapusin muna ang pagbasa.')
        if not state['found_words']:
            raise ValueError('Bumuo muna ng kahit isang wastong salita.')
        state['completed'] = True
        state['index'] = 1
        state['last_feedback'] = 'Magaling! Natapos mo ang Gawain 1.'
        return state
    raise ValueError('Unknown action.')
