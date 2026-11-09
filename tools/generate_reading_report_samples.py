"""Generate illustrative parent PDFs without reading or writing student records."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def sample_reports():
    """Stable synthetic content for presentation and pagination review."""
    stamp = '2026-11-06T10:00:00+08:00'
    base = {
        'student_name': 'Sample Learner', 'student_id': 'SAMPLE-001',
        'grade_level': 'Grade 2', 'section': 'Rizal', 'teacher_name': 'Sample Teacher',
        'school_year': '2026-2027', 'course_name': 'Reading Development',
        'crla': {'available': False, 'message': 'An official completed CRLA result is not available.'},
        'crla_history': {'rows': [], 'message': 'No verified official student CRLA assessment results are available for this school year.'},
        'aral_activities': [], 'workbook': {'school_year': '2026-2027', 'rows': []},
        'competencies': [{'name': name, 'activities': []} for name in (
            'Oral Language', 'Phonics', 'Phonological Awareness', 'Fluency',
            'Vocabulary', 'Reading Comprehension')],
        'recent_progress': [], 'recommendations': [],
    }
    typical = deepcopy(base)
    typical['crla'] = {
        'available': True, 'assessment_period': 'Midline', 'assessment_phase': 'midtest',
        'reading_profile': 'Transitioning Reader', 'completed_at': stamp,
        'total_score': 24, 'accuracy': 87.5, 'wpm': 46.2,
        'part2_results': {'story_number': 2, 'passage_accuracy_percent': 87.5,
                         'comprehension_correct': 4, 'part1_total_score': 24},
    }
    typical['crla_history'] = {'school_year': '2026-2027', 'rows': [
        {'period': 'BoSY', 'completed_at': '2026-07-06T10:00:00+08:00',
         'classification': 'Developing Reader', 'accuracy': 72.5, 'wpm': 32,
         'comprehension': '2/5 correct'},
        {'period': 'Midline', 'completed_at': stamp, 'classification': 'Transitioning Reader',
         'accuracy': 87.5, 'wpm': 46.2, 'comprehension': '4/5 correct'},
    ]}
    typical['aral_activities'] = [
        {'activity_id': 'word_meaning_match', 'activity_name': 'Word Meaning Match', 'assigned_weeks': [2], 'completed_at': stamp,
         'score': 80, 'accuracy': 80, 'correct_items': 8, 'total_items': 10},
        {'activity_id': 'fluency_reading', 'activity_name': 'Fluency Reading', 'assigned_weeks': [3, 4], 'completed_at': stamp,
         'score': 86, 'accuracy': 86, 'wpm': 44, 'correct_items': 43, 'total_items': 50,
         'automated_speech_analysis': True},
        {'activity_id': 'story_response', 'activity_name': 'Story Response', 'assigned_weeks': [4], 'completed_at': stamp,
         'score': 4},
    ]
    typical['workbook'] = {'school_year': '2026-2027', 'completed_count': 2,
        'ongoing_count': 1, 'other_count': 1, 'unverified_count': 0, 'rows': [
        {'session': 1, 'lesson': 1, 'gawain': 1, 'title': 'Letter and sound practice',
         'period': '2026-2027 / Term 2', 'completion_status': 'Completed',
         'items': '5/5 items', 'completion_percent': 100,
         'results': ['Teacher score: 4/5 reviewed recording items'], 'review_status': '5 teacher checked'},
        {'session': 2, 'lesson': 4, 'gawain': 2, 'title': 'Letrang Mm at Ss',
         'period': '2026-2027 / Term 2', 'completion_status': 'Completed',
         'items': '6/6 items', 'completion_percent': 100,
         'results': ['Submitted answers: 6/6 correct'], 'review_status': 'Teacher checked'},
        {'session': 5, 'lesson': 14, 'gawain': 4, 'title': 'Guided oral reading',
         'period': '2026-2027 / Term 2', 'completion_status': 'Ongoing',
         'items': '2/6 items', 'completion_percent': 33.3, 'results': [],
         'review_status': '2 pending teacher review'},
        {'session': 9, 'lesson': '', 'gawain': 1, 'title': 'My family',
         'period': '2026-2027 / Term 2', 'completion_status': 'Submitted; awaiting teacher review',
         'items': '1/1 items', 'completion_percent': 100, 'results': [],
         'review_status': 'Pending teacher review'},
    ]}
    for report in (base, typical):
        report['workbook'].update(school_calendar_id=1, current_term=2)
    for index, row in enumerate(typical['workbook']['rows']):
        row.update(activity_key=f'sample-workbook-{index}', school_calendar_id=1,
                   term=2, period_verified=True, completed=index < 2)
        row['evidence'] = {'completion_recorded': True, 'pending_review': index == 3,
                           'recordings': []}
    typical['workbook']['rows'][2]['evidence']['recordings'] = [
        {'teacher_reviewed': False, 'status': 'submitted'} for _index in range(2)]
    for activity in typical['aral_activities']:
        activity['supplementary_skill_activity'] = True
    from pabasa_app.aral_activity_catalog import ACTIVITIES
    for competency in typical['competencies']:
        competency['activities'] = [{'activity_name': activity['activity_name']} for activity in typical['aral_activities']
            if competency['name'] in ACTIVITIES[activity['activity_id']]['competencies']]
    typical['recent_progress'] = [
        {'activity_name': 'Fluency Reading', 'completed_at': stamp, 'accuracy': 86,
         'wpm': 44, 'miscues': 7, 'automated_speech_analysis': True},
        {'activity_name': 'Word Meaning Match', 'completed_at': stamp, 'accuracy': 80},
    ]
    for activity in typical['recent_progress']:
        activity['supplementary_skill_activity'] = True
    typical['recommendations'] = [
        'Practice the items needing support in Session 1, Lesson 1, Gawain 1 with teacher guidance.',
        'Continue Session 5, Lesson 14, Gawain 4 and review the results with the teacher.',
        'Review submitted work in Session 9, Gawain 1 (My family) with the teacher; evaluation is pending.',
    ]
    from pabasa_app.reading_progress_reports import _recommendations
    base['recommendation_details'] = _recommendations(base['crla'], [], base['workbook'])
    base['recommendations'] = [item['text'] for item in base['recommendation_details']]
    typical['recommendation_details'] = [
        {'code': code, 'text': text} for code, text in zip(('P2', 'P1', 'P1'), typical['recommendations'])]
    extended = deepcopy(typical)
    extended['student_name'] = 'Sample Learner With a Deliberately Long Name for Layout Verification'
    extended['teacher_name'] = 'Sample Teacher With a Longer Recorded Professional Name'
    extended['crla_history']['rows'].append({
        'period': 'EoSY', 'completed_at': stamp, 'classification': 'Reading At Grade Level',
        'accuracy': None, 'wpm': None, 'comprehension': 'Not recorded'})
    extended['aral_activities'] = [dict(typical['aral_activities'][i % 3],
        activity_name=f"{typical['aral_activities'][i % 3]['activity_name']} - practice set {i+1}") for i in range(12)]
    extended['workbook']['rows'] = []
    for i in range(28):
        row = dict(typical['workbook']['rows'][i % 4])
        row['title'] += f' - recorded workbook activity {i+1}'
        term = i // 10 + 1
        row.update(activity_key=f'sample-workbook-{i}', term=term,
                   period=f'2026-2027 / Term {term}')
        if i == 27:
            row.update(period='School year unverified / Term unverified', completion_percent=None,
                       items='3 items recorded; required total unverified',
                       school_calendar_id=None, term=None, period_verified=False)
        extended['workbook']['rows'].append(row)
    extended['workbook'].update(completed_count=14, ongoing_count=7, other_count=7, unverified_count=1)
    extended['recent_progress'] = [dict(typical['recent_progress'][i % 2],
        activity_name=f'Reading activity {i+1}',
        completed_at=(datetime.fromisoformat(stamp) - timedelta(days=i)).isoformat()) for i in range(10)]
    extended['recommendations'] = typical['recommendations'] * 3
    extended['recommendation_details'] = typical['recommendation_details'] * 3
    grade_level = deepcopy(base)
    grade_level['crla'] = {
        'available': True, 'assessment_period': 'Midline', 'reading_profile': 'Reading At Grade Level',
        'completed_at': stamp, 'total_score': None, 'accuracy': None, 'wpm': None, 'part2_results': {},
    }
    from pabasa_app.reading_report_details import SINGLE_CRLA_PERIOD_NOTICE
    grade_level['crla_history'] = {'school_year': '2026-2027', 'rows': [{
        'period': 'Midline', 'completed_at': stamp, 'classification': 'Reading At Grade Level',
        'accuracy': None, 'wpm': None, 'comprehension': 'Not recorded'}],
        'message': SINGLE_CRLA_PERIOD_NOTICE}
    grade_level['recommendation_details'] = _recommendations(grade_level['crla'], [], grade_level['workbook'])
    grade_level['recommendations'] = [item['text'] for item in grade_level['recommendation_details']]
    note = ('Please continue short, enjoyable reading sessions at home. Invite your child to explain '
            'the story in their own words, and discuss any challenging items with the teacher. ')
    return {
        'empty': (base, ''),
        'typical': (typical, 'Thank you for supporting regular reading at home. Please review pending workbook submissions with the teacher.'),
        'extended': (extended, note * 14),
        'grade-level': (grade_level, ''),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/pdf')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'pabasa_site'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    from pabasa_app.views import _build_reading_report_pdf
    from pypdf import PdfReader
    from io import BytesIO
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, (report, note) in sample_reports().items():
        content = _build_reading_report_pdf(report, message=note)
        path = args.output_dir / f'pabasa-parent-report-{name}.pdf'
        path.write_bytes(content)
        print(f'{name}: {len(PdfReader(BytesIO(content)).pages)} pages -> {path.resolve()}')


if __name__ == '__main__':
    main()
