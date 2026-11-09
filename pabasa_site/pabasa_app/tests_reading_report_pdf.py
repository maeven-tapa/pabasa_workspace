"""Content retention and pagination tests for the presentation-only renderer."""

from copy import deepcopy
import importlib.util
from io import BytesIO
from pathlib import Path
import re

from django.test import SimpleTestCase
from pypdf import PdfReader

from .views import _build_reading_report_pdf
from .reading_report_details import summarize_workbook_progress
from .reading_report_pdf import _recommendation_code


def samples():
    path = Path(__file__).resolve().parents[2] / 'tools' / 'generate_reading_report_samples.py'
    spec = importlib.util.spec_from_file_location('reading_report_samples', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.sample_reports()


class ParentReportPresentationTests(SimpleTestCase):
    def render(self, report, note=''):
        original = deepcopy(report)
        content = _build_reading_report_pdf(report, message=note)
        self.assertEqual(report, original, 'Presentation must not modify the collector payload.')
        reader = PdfReader(BytesIO(content))
        text = ' '.join(' '.join(page.extract_text() or '' for page in reader.pages).split())
        return reader, text

    def test_empty_report_keeps_all_sections_on_one_page(self):
        report, note = samples()['empty']
        reader, text = self.render(report, note)
        self.assertEqual(len(reader.pages), 1)
        for heading in ['STUDENT INFORMATION', 'CRLA INITIAL ASSESSMENT', 'CRLA PROGRESS HISTORY',
                        'SUPPLEMENTARY ARAL ACTIVITIES', 'ARAL WORKBOOK PERFORMANCE',
                        'READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', 'READING PROGRESS', "TEACHER'S NOTE", 'NEXT STEPS']:
            self.assertIn(heading, text)
        for message in [report['crla']['message'], report['crla_history']['message'],
                        'No teacher note was added.', 'No recent persisted reading results are available.',
                        'No workbook progress or recording submissions are available for this reporting period.']:
            self.assertIn(message, text)
        self.assertIn('Page 1 of 1', text)

    def test_typical_report_retains_every_displayed_value_and_note(self):
        report, note = samples()['typical']
        reader, text = self.render(report, note)
        self.assertEqual(len(reader.pages), 2)
        for key in ['student_name', 'student_id', 'teacher_name', 'school_year']:
            self.assertIn(report[key], text)
        for value in ['Grade 2 / Rizal', 'Transitioning Reader', 'Midline', 'November 06, 2026',
                      '24', '87.5%', '46.2', 'Story Number: 2', 'Comprehension Correct: 4',
                      'Part1 Total Score: 24', '2/5 correct', '4/5 correct', 'Score: 80',
                      'Accuracy: 86%', 'WPM: 44', 'Items: 43/50', 'Automated speech-analysis data',
                      'Teacher score: 4/5 reviewed recording items', '33.3% of items',
                      'Pending teacher review', 'miscues 7', 'automated speech-analysis information', note]:
            self.assertIn(value, text)
        for item in report['workbook']['rows']:
            self.assertIn(item['title'], text)
            self.assertIn(item['completion_status'], text)
            self.assertIn(item['items'], text)
        for recommendation in report['recommendations']:
            self.assertIn(recommendation, text)
        for number, page in enumerate(reader.pages, 1):
            self.assertIn(f'Page {number} of {len(reader.pages)}', page.extract_text())
            if number > 1:
                self.assertIn('Student reading progress', page.extract_text())

    def test_extended_report_keeps_all_rows_and_continues_table_headers(self):
        report, note = samples()['extended']
        reader, text = self.render(report, note)
        self.assertGreater(len(reader.pages), 3)
        self.assertIn(note, text)
        for item in report['workbook']['rows']:
            self.assertIn(item['title'], text)
        for item in report['aral_activities']:
            self.assertIn(item['activity_name'], text)
        self.assertGreater(text.count('Results / teacher review'), 1)
        self.assertIn('School year unverified', text)
        self.assertIn('required total unverified', text)
        self.assertIn('EoSY', text)
        self.assertIn('Not recorded', text)

    def test_zero_scores_and_finalized_provenance_are_preserved(self):
        report, note = samples()['typical']
        report['crla'].update(total_score=0, accuracy=0, wpm=0, finalized_without_submission=True,
                              reading_profile='Low Emerging Reader')
        report['workbook']['rows'][0].update(completion_percent=0, items='0/5 items')
        report['aral_activities'][0].update(score=0, accuracy=0, correct_items=0, total_items=10)
        reader, text = self.render(report)
        for value in ['Low Emerging Reader', 'Accuracy', '0%', 'Words Per Minute', 'Score: 0',
                      'Items: 0/10', '0% of items', '0/5 items',
                      'No student submission was recorded. The class was finalized with a zero-score result.']:
            self.assertIn(value, text)
        self.assertNotIn('Mastered', text)

    def test_long_cells_notes_and_recommendations_split_without_losing_content(self):
        report, _note = samples()['typical']
        report['workbook']['rows'] = [report['workbook']['rows'][0]]
        report['workbook']['rows'][0]['results'] = ['Detailed recorded result. ' * 550 + 'WORKBOOK-END']
        report['student_name'] = 'Long student name ' * 25 + 'NAME-END'
        report['teacher_name'] = 'Long teacher name ' * 20 + 'TEACHER-END'
        report['recommendations'] = ['Continue supported practice. ' * 420 + 'ACTION-END']
        note = 'Teacher guidance remains fully visible. ' * 600 + 'NOTE-END'
        reader, text = self.render(report, note)
        self.assertGreater(len(reader.pages), 5)
        for sentinel in ['WORKBOOK-END', 'NAME-END', 'TEACHER-END', 'ACTION-END', 'NOTE-END']:
            self.assertIn(sentinel, text)
        # A page header can occur between words in extracted cross-page text.
        # Unique word counts verify retention without treating that as loss.
        self.assertEqual(len(re.findall(r'\bDetailed\b', text)), 550)
        self.assertEqual(len(re.findall(r'\bvisible\b', text)), 600)
        self.assertEqual(len(re.findall(r'\bsupported\b', text)), 420)

    def test_unicode_and_literal_markup_remain_readable(self):
        report, _note = samples()['typical']
        report['student_name'] = 'Sample Niño & <Family>'
        note = 'Teacher’s note: “Basahin nang maayos.” <b>Keep this literal.</b>'
        _reader, text = self.render(report, note)
        self.assertIn(report['student_name'], text)
        self.assertIn(note, text)
        self.assertNotIn('\u25a0', text)

    def test_document_embeds_fonts_and_has_a_document_title(self):
        report, note = samples()['typical']
        reader, _text = self.render(report, note)
        self.assertEqual(reader.metadata.title, 'Student Reading Progress Report')
        descriptors = []
        for page in reader.pages:
            for font in page['/Resources']['/Font'].get_object().values():
                descriptor = font.get_object().get('/FontDescriptor')
                if descriptor:
                    descriptors.append(descriptor.get_object())
        self.assertTrue(descriptors)
        self.assertTrue(any('/FontFile2' in descriptor for descriptor in descriptors))

    def test_varying_record_counts_do_not_leave_orphaned_section_headings(self):
        for count in [1, 3, 5, 8, 12]:
            with self.subTest(record_count=count):
                report, note = samples()['typical']
                report['aral_activities'] *= count
                report['workbook']['rows'] *= count
                reader, _text = self.render(report, note * count)
                for page in reader.pages:
                    text = page.extract_text()
                    if 'NEXT STEPS' in text:
                        self.assertIn(report['recommendations'][0], ' '.join(text.split()),
                                      'The recommendation key must stay with the first action.')
                    body = text[:text.rfind('PABASA  /  Reading development, together')].strip()
                    for label in ['CRLA PROGRESS HISTORY', 'SUPPLEMENTARY ARAL ACTIVITIES',
                                  'ARAL WORKBOOK PERFORMANCE', 'READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES',
                                  'READING PROGRESS', "TEACHER'S NOTE", 'NEXT STEPS',
                                  'Completion Overview', 'Activity Performance']:
                        self.assertFalse(body.endswith(label), f'Orphaned label: {label}')

    def test_skills_section_explains_teacher_directed_support_without_claiming_mastery(self):
        report, note = samples()['typical']
        _reader, text = self.render(report, note)
        section = text.split('READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', 1)[1].split('READING PROGRESS', 1)[0]
        self.assertIn('These reading skills were practiced through supplementary activities selected by the teacher to provide additional support in areas where the learner may need further improvement.', section)
        self.assertIn("Practice does not confirm mastery or measure the learner's overall reading proficiency.", section)
        self.assertIn('Vocabulary:', section)
        self.assertIn('Word Meaning Match', section)
        self.assertIn('Reading Comprehension:', section)
        self.assertIn('Story Response', section)
        self.assertNotIn('Phonological Awareness', section)
        self.assertNotIn('Phonics:', section)

    def test_skills_section_without_results_does_not_list_unpracticed_skills(self):
        report, note = samples()['empty']
        _reader, text = self.render(report, note)
        section = text.split('READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', 1)[1].split('READING PROGRESS', 1)[0]
        self.assertIn('No completed supplementary activities are recorded yet.', section)
        for competency in report['competencies']:
            self.assertNotIn(competency['name'], section)

    def test_progress_charts_show_workbook_and_supplementary_as_separate_measures(self):
        report, note = samples()['typical']
        _reader, text = self.render(report, note)
        section = text.split('07 READING PROGRESS', 1)[1].split("08 TEACHER'S NOTE", 1)[0]
        for value in ['Prescribed ARAL Workbook', 'Activity counts by verified term',
                      'Completed: 2', 'Ongoing: 1', 'Awaiting review: 1',
                      'Recordings: 2 awaiting review', 'Completion is not correctness or mastery',
                      'Supplementary activities', 'Accuracy (0-100%)', '86% accuracy',
                      '80% accuracy', 'miscues 7', 'automated speech-analysis information']:
            self.assertIn(value, section)
        self.assertNotIn('100% accuracy', section, 'Workbook completion is not accuracy.')

    def test_workbook_chart_counts_records_not_assignment_totals_and_deduplicates(self):
        report, _note = samples()['typical']
        workbook = report['workbook']
        original = deepcopy(workbook)
        workbook['rows'].append(deepcopy(workbook['rows'][0]))
        workbook['rows'].append(dict(workbook['rows'][0], school_calendar_id=99))
        workbook['rows'].append(dict(workbook['rows'][0], period_verified=False))
        summary = summarize_workbook_progress(workbook)
        self.assertEqual(summary['excluded_count'], 2)
        self.assertEqual(summary['periods'], [{
            'term': 2, 'completed': 2, 'ongoing': 1, 'awaiting_review': 1,
            'completion_unrecorded': 0, 'recordings_reviewed': 0,
            'recordings_pending': 2, 'recordings_retry': 0}])
        self.assertEqual(workbook['rows'][:4], original['rows'])
        self.assertNotIn('completion_percent', summary['periods'][0])

    def test_workbook_chart_keeps_completion_and_recording_review_independent(self):
        report, _note = samples()['typical']
        workbook = report['workbook']
        workbook['rows'] = [deepcopy(workbook['rows'][0])]
        workbook['rows'][0]['evidence']['recordings'] = [
            {'status': 'submitted', 'teacher_reviewed': False, 'teacher_score': None},
            {'status': 'checked', 'teacher_reviewed': True, 'teacher_score': 0},
            {'status': 'retry', 'teacher_reviewed': False, 'teacher_score': None}]
        period = summarize_workbook_progress(workbook)['periods'][0]
        self.assertEqual(period['completed'], 1)
        self.assertEqual(period['awaiting_review'], 0)
        self.assertEqual(period['recordings_pending'], 1)
        self.assertEqual(period['recordings_reviewed'], 1)
        self.assertEqual(period['recordings_retry'], 1)
        self.assertNotIn('accuracy', period)

    def test_recording_only_and_unverified_workbook_records_do_not_invent_completion(self):
        report, _note = samples()['typical']
        row = report['workbook']['rows'][0]
        row.update(completed=False, completion_percent=None)
        row['evidence'] = {'completion_recorded': False, 'recordings': [
            {'status': 'submitted', 'teacher_reviewed': False}]}
        report['workbook']['rows'] = [row]
        period = summarize_workbook_progress(report['workbook'])['periods'][0]
        self.assertEqual(period['completion_unrecorded'], 1)
        self.assertEqual(period['recordings_pending'], 1)
        self.assertEqual(period['completed'], 0)
        row['period_verified'] = False
        _reader, text = self.render(report)
        section = text.split('07 READING PROGRESS', 1)[1].split("08 TEACHER'S NOTE", 1)[0]
        self.assertIn('No workbook records with a verified school year and term are available to chart.', section)
        self.assertIn('1 workbook record(s)', section)
        self.assertEqual(summarize_workbook_progress(report['workbook'])['periods'], [])
        report['workbook']['school_calendar_id'] = None
        row['period_verified'] = True
        self.assertEqual(summarize_workbook_progress(report['workbook'])['periods'], [])

    def test_recent_results_without_accuracy_remain_available_without_zero_accuracy(self):
        report, _note = samples()['typical']
        report['recent_progress'] = [
            {'activity_name': 'Ungraded supplementary submission', 'accuracy': None,
             'supplementary_skill_activity': True, 'completed_at': '2026-11-06'},
            {'activity_name': 'Other saved result', 'accuracy': 0, 'wpm': 0, 'miscues': 0,
             'supplementary_skill_activity': False, 'completed_at': '2026-11-06'}]
        _reader, text = self.render(report)
        section = text.split('07 READING PROGRESS', 1)[1].split("08 TEACHER'S NOTE", 1)[0]
        supplementary, other = section.split('Other recent recorded results', 1)
        self.assertIn('Ungraded supplementary submission', supplementary)
        self.assertIn('Not recorded', supplementary)
        self.assertNotIn('0% accuracy', supplementary)
        self.assertIn('Other saved result', other)
        self.assertIn('0% accuracy', other)
        self.assertIn('miscues 0', other)

    def test_parent_recommendations_show_matching_codes_and_all_six_meanings(self):
        report, _note = samples()['typical']
        for code in ('P0', 'P3', 'P4', 'P5'):
            text = f'Synthetic advice for {code}.'
            report['recommendations'].append(text)
            report['recommendation_details'].append({'text': text, 'code': code})
        # Metadata order is not an academic association.
        report['recommendation_details'].reverse()
        _reader, text = self.render(report)
        section = text.split('09 NEXT STEPS', 1)[1]
        self.assertIn('Parent recommendations', section)
        for value in ['P0 CRLA unavailable', 'P1 Continue / review', 'P2 Guided practice',
                      'P3 Oral reading', 'P4 Regular reading / support', 'P5 Grade level / Practice Mode']:
            self.assertIn(value, section)
        for item in report['recommendation_details']:
            self.assertIn(f"{item['code']} {item['text']}", section)

    def test_each_workbook_term_bar_keeps_its_counts_and_recording_context_on_same_page(self):
        report, note = samples()['extended']
        reader, _text = self.render(report, note)
        pages = [' '.join((page.extract_text() or '').split()) for page in reader.pages]
        start = next(index for index, page in enumerate(pages) if '07 READING PROGRESS' in page)
        pages[start] = pages[start].split('07 READING PROGRESS', 1)[1]
        for period in summarize_workbook_progress(report['workbook'])['periods']:
            chart_page = next(page for page in pages[start:] if f"Term {period['term']}" in page)
            for key, label in [('completed', 'Completed'), ('ongoing', 'Ongoing'),
                               ('awaiting_review', 'Awaiting review'),
                               ('completion_unrecorded', 'Completion unrecorded')]:
                self.assertIn(f'{label}: {period[key]}', chart_page)
            self.assertIn(f"Recordings: {period['recordings_pending']} awaiting review", chart_page)

    def test_recommendation_codes_are_never_guessed_for_stale_or_legacy_metadata(self):
        self.assertIsNone(_recommendation_code('Continue reading.', []))
        self.assertIsNone(_recommendation_code('Continue reading.', [
            {'text': 'Different advice', 'code': 'P2'}]))
        self.assertIsNone(_recommendation_code('Continue reading.', [
            {'text': 'Continue reading.', 'code': 'P2'},
            {'text': 'Continue reading.', 'code': 'P3'}]))
        report, _note = samples()['empty']
        report.pop('recommendation_details')
        report['recommendations'].append('Additional legacy advice without code metadata.')
        _reader, text = self.render(report)
        self.assertIn('01 ' + report['recommendations'][0], text)
        self.assertIn('02 ' + report['recommendations'][1], text)

    def test_p0_and_p5_samples_display_only_the_applicable_advice_below_the_key(self):
        for name, code in [('empty', 'P0'), ('grade-level', 'P5')]:
            with self.subTest(sample=name):
                report, note = samples()[name]
                reader, text = self.render(report, note)
                self.assertEqual(len(reader.pages), 1, 'Brief P0/P5 reports should keep advice on the same page.')
                section = text.split('09 NEXT STEPS', 1)[1]
                self.assertIn(code + ' ' + report['recommendations'][0], section)
                self.assertEqual([item['code'] for item in report['recommendation_details']], [code])
                self.assertNotIn('Continue assigned ARAL', section)
                if code == 'P5':
                    self.assertIn('using Practice Mode', section)
