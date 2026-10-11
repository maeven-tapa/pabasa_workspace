"""Continuation state for the four prescribed sentence reading activities."""

from .lesson26_reading import analyze_sentence_continuation


ACTIVITY_KEYS = frozenset({
    'lesson-29-gawain-1', 'lesson-30-gawain-2',
    'lesson-31-gawain-2', 'lesson-31-gawain-3',
})


def continue_sentence(activity, key, old, data, aliases):
    request_id = str(data.get('request_id', ''))[:96]
    previous_request = old.get('sentence_request') or {}
    if request_id and request_id == previous_request.get('id'):
        return dict(old), previous_request['reading'], previous_request['prompt']
    story = key == 'lesson-30-gawain-2'
    index_key = 'current_line' if story else 'current_item'
    items = activity['lines'] if story else activity['items']
    index = int(old.get(index_key, 0))
    phase = 'reading' if story else ('sentence_reading' if key == 'lesson-29-gawain-1'
                                     else 'reading_sentence')
    if (old.get('phase', 'reading' if story else '') != phase
            or index < 0 or index >= len(items) or int(data.get('item_index', -1)) != index):
        raise ValueError('Read the current completed sentence first.')
    item = items[index]
    text = item if story else (f"{item['before']}{item['answer']}{item['after']}"
                              if key == 'lesson-29-gawain-1' else item['sentence'])
    heard = str(data.get('heard', '')).strip()
    if not heard:
        raise ValueError('No speech detected. Please try again.')
    result = analyze_sentence_continuation(
        text, int(old.get('sentence_syllable_index', 0)), heard, 'en-PH', aliases,
    )
    saved = dict(old)
    saved.update(activity_key=key, **{index_key: index, 'phase': phase})
    saved['sentence_syllable_index'] = result['current_syllable_index']
    saved['sentence_word_index'] = result['current_word_index']
    attempt_key = 'attempts' if story or key == 'lesson-31-gawain-3' else 'sentence_attempts'
    advanced = result['current_syllable_index'] > int(old.get('sentence_syllable_index', 0))
    prompt = advanced and not result['reading_mismatch'] and not result['complete']
    if result['complete']:
        saved[index_key] = index + 1
        saved['completed_items'] = index + 1
        saved[attempt_key] = saved['sentence_syllable_index'] = saved['sentence_word_index'] = 0
        saved['phase'] = 'complete' if index + 1 == len(items) else {
            'lesson-29-gawain-1': 'answering', 'lesson-30-gawain-2': 'reading',
            'lesson-31-gawain-2': 'sentence_listen', 'lesson-31-gawain-3': 'reading_words',
        }[key]
        if key == 'lesson-29-gawain-1':
            saved.update(attempts=0, hint_length=0, hint='', help_visible=False, help_word='')
        elif key == 'lesson-31-gawain-2':
            saved.update(choice_attempts=0, placed_word='')
        elif key == 'lesson-31-gawain-3':
            saved.update(word_index=0, placements=[])
    elif not prompt:
        saved[attempt_key] = int(old.get(attempt_key, 0)) + 1
    saved['state_version'] = int(old.get('state_version', 0)) + 1
    if request_id:
        saved['sentence_request'] = {'id': request_id, 'reading': result, 'prompt': prompt}
    return saved, result, prompt
