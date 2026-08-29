import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from pabasa_app.reading_stt import align_story_transcript, ReadingMatcher

target = 'Ako ang pinakamabilis tumakbo, sabi ni Kuneho. "Wala nang bibilis pa sa akin!"'
recognized = 'sa be ni kuneho'
result = align_story_transcript(target, recognized, 'fil-PH')
matcher = ReadingMatcher(target, 0, 'fil-PH')
print('WORDS=' + json.dumps(matcher.words, ensure_ascii=False))
print('CURRENT_WORD_INDEX=' + str(matcher.current_word_index))
print('CURRENT_WORD=' + json.dumps(matcher.words[matcher.current_word_index], ensure_ascii=False))
print('WORD_RESULTS=' + json.dumps(result.get('word_results', []), ensure_ascii=False, indent=2))
matching = next((item for item in result.get('word_results', []) if item.get('expected_index') == matcher.current_word_index), None)
print('MATCHING_CURRENT_TARGET=' + json.dumps(matching, ensure_ascii=False))
print('MISCUE_ENTRIES=' + json.dumps([item for item in result.get('word_results', []) if item.get('result') == 'miscue'], ensure_ascii=False))
