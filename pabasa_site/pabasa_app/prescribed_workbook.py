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


def add(key, page, lesson, number, title, instruction, kind, rows, **config):
    session = 8 if page <= 47 else 9 if page <= 49 else 10 if page <= 51 else 11
    label = f'Lesson {lesson}: Gawain {number}' if lesson else f'Session {session}: Activity {number}'
    item_ids = config.pop('item_ids', None)
    oral_flow = config.pop('oral_flow', kind not in {'drawing', 'fill'})
    items = [dict(id=f'item-{i + 1}', text=text) for i, text in enumerate(
        [text for row in rows for text in row if text]
    )]
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
    [['freezer', 'Felipe'], ['fries', 'Felix'], ['Filipino', 'Ferrer'], ['Fina', 'Faith'], ['Filipiniana', 'Fontana']])


add('aral-l23-g1-n-syllable-builder', 41, 23, '1', 'Big Box: Ñ', BOX, 'builder',
    [['Ni', 'La', 'ña'], ['Cas', 'Bi', 'da'], ['El', 'ño', 'ñan'], ['Cen', 'ta', 'ñe']], review_required=True)
add('aral-l23-g2-n-word-reading', 42, 23, '2', 'Mga salitang may letrang Ññ',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Ññ.', 'reading',
    [['Penafrañcia', 'España'], ['Los Baños'], ['Biñan', 'Cendaña'], ['Castañeda', 'Orduña'], ['Niño'], ['Niña']])
add('aral-l23-g3-j-word-reading', 42, 23, '3', 'Mga salitang may letrang Jj',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Jj.', 'reading',
    [['Jacket', 'Jennifer', 'jam', 'Jeffrey'], ['pajama', 'Jerry', 'Jojo', 'Jonathan']])
add('aral-l23-g4-j-syllabication', 42, 23, '4', 'Pantigin ang mga salita: J',
    'Pantigin ang sumusunod na salita.', 'syllables', [['jacket'], ['pajama'], ['Jonathan'], ['jam'], ['Joselito']],
    syllable_answers=['jack-et', 'pa-ja-ma', 'Jo-na-than', 'jam', 'Jo-se-li-to'])
add('aral-l23-g5-j-word-search', 43, 23, '5', 'Hanapin ang mga salita: J',
    'Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.', 'search',
    [['jacket'], ['pajama'], ['jam'], ['Jonathan'], ['Jennifer']],
    visible_activity_label='GAWAIN 5', grid=['ZJONATHAN','JAMLTYZSI','JACKETERG','BZOPAJAMA','JENNIFERM'], mark_style='circle')
add('aral-l23-g6-q-syllable-builder', 43, 23, '6', 'Big Box: Q',
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salitang.', 'builder',
    [['Que','En','Qui','tos'], ['no','A','Quin','An'], ['ta','ja','na','to'], ['ri','zon','que','ti']],
    visible_activity_label='GAWAIN 6', review_required=True)
add('aral-l23-g7-q-word-reading', 44, 23, '7', 'Mga salitang may letrang Qq',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Qq.', 'reading',
    [['Quisumbing','Quennie','Enriquez','Quintana','Quintos']], visible_activity_label='GAWAIN 7')

add('aral-l24-g1-v-syllable-builder', 44, 24, '1', 'Big Box: V',
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.', 'builder',
    [['lin','sa','van'], ['va','E','la'], ['I','Vi','Vio'], ['le','val','A']], review_required=True)
add('aral-l24-g2-v-word-reading', 44, 24, '2', 'Mga salitang may letrang Vv',
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv.', 'reading',
    [['Vina','vanilla'], ['Vilma','vila'], ['Victor','vinta'], ['Victoria','van'], ['Valdez','visa'], ['Valle','violin'], ['Visayas','volleybal']], column_headers=['V','v'])
add('aral-l24-g3-x-repeat', 45, 24, '3', 'Pakinggan at ulitin: X',
    'Pakinggang mabuti ang mga salitang bibigkasin ng guro pagkatapos ay ulitin ito.', 'reading',
    [['Alex'], ['Felix'], ['x-factor'], ['fixer']], model_first=True)
add('aral-l24-g2-x-pictures', 45, 24, '2', 'Kilalanin ang mga larawan: X',
    'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.', 'reading',
    [['x-ray','fax machine','fox']], model_first=True,
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


def initial_l22_g2_state():
    return {
        'index': 0, 'sequence_index': 0, 'completed_words': [],
        'reading_attempts': 0, 'reading_phase': 'read',
        'last_feedback': '', 'last_transcript': '',
        'completed': False, 'revision': 0,
    }


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


def apply_event(activity, state, event, verified_reading=None):
    """Advance only the current item's required phases; never trust client scores."""
    if activity['activity_key'] == 'aral-l22-g2-c-word-reading':
        return _apply_l22_g2_reading(state, event, verified_reading)
    if activity['activity_key'] == 'aral-l22-g1-c-syllable-builder':
        normalize_l22_c_state(state)
        if state['completed']:
            return state
        return _apply_l22_c_builder(state, event, verified_reading)
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
