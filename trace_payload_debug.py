import os, json, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from pabasa_app.reading_stt import align_story_transcript, ReadingMatcher

target = 'Ako ang pinakamabilis tumakbo, sabi ni Kuneho. "Wala nang bibilis pa sa akin!"'
recognized = 'sa be ni kuneho'
result = align_story_transcript(target, recognized, 'fil-PH')
matcher = ReadingMatcher(target, 0, 'fil-PH')
record = {
    'words': matcher.words,
    'current_word_index': matcher.current_word_index,
    'current_word': matcher.words[matcher.current_word_index],
    'word_results': result.get('word_results', []),
    'matching_current_target': next((item for item in result.get('word_results', []) if item.get('expected_index') == matcher.current_word_index), None),
    'miscue_entries': [item for item in result.get('word_results', []) if item.get('result') == 'miscue'],
}
with open('trace_payload_debug_result.json', 'w', encoding='utf-8') as fh:
    json.dump(record, fh, ensure_ascii=False, indent=2)
print('RESULT_WRITTEN')
print(json.dumps(record, ensure_ascii=False, indent=2))
sys.stdout.flush()
