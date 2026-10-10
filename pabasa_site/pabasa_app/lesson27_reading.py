"""Word-by-word continuation for Lesson 27 verses, independent of CRLA scoring."""

from .reading_stt import ReadingMatcher


def analyze_verse_reading(target_text, current_syllable_index, transcript, language_code):
    matcher = ReadingMatcher(
        target_text, current_syllable_index, language_code,
        pronunciation_aliases={'loved': {'love'}},
    )
    spoken = matcher.normalize_spoken_words(transcript)
    previous_word = matcher.current_word_index
    previous_cursor = matcher.current_syllable_index
    # A learner may resume at the next word or reread the verse from the start.
    # Stop at the first mismatch; later words cannot hide a misread word.
    candidates = []
    for start in {0, previous_word}:
        index = start
        mismatch = False
        for word in spoken:
            if index >= len(matcher.words) or not matcher.words_match(
                word, matcher.normalize_word(matcher.words[index])
            ):
                mismatch = True
                break
            index += 1
        candidates.append((index, not mismatch))
    index, clean = max(candidates)
    matcher.current_word_index = max(previous_word, index)
    matcher.current_syllable_index = (
        matcher.word_syllable_ranges[matcher.current_word_index - 1][1]
        if matcher.current_word_index else 0
    )
    result = matcher.payload(matcher.current_syllable_index - previous_cursor, transcript)
    result['reading_mismatch'] = not clean
    result['complete'] = result['complete'] and clean and bool(spoken)
    return result
