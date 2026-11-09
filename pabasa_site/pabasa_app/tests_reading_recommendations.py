"""P0-P5 decisions use official CRLA status and structured activity evidence."""

from copy import deepcopy

from django.test import SimpleTestCase

from .reading_progress_reports import _recommendations


class ReadingRecommendationRuleTests(SimpleTestCase):
    def workbook_row(self, **changes):
        row = {
            "activity_key": "lesson-15-gawain-1", "title": "Letrang Ww at Yy",
            "session": 5, "lesson": 15, "gawain": 1,
            "school_calendar_id": 7, "term": 2, "period_verified": True,
            "completed": False,
            "evidence": {
                "progress_id": 42, "completion_recorded": True, "submitted": False,
                "pending_review": False, "retry_requested": False, "teacher_checked": False,
                "scored_answers": [], "recordings": [], "oral_reading": False,
            },
        }
        row.update(changes)
        return row

    def recording(self, **changes):
        row = {"submission_id": 12, "item_index": 0, "substep": None,
               "has_recording": True, "status": "submitted", "review_status": "pending",
               "teacher_reviewed": False, "teacher_score": None,
               "classification": "", "classification_source": ""}
        row.update(changes)
        return row

    def recommend(self, *rows, supplementary=(), calendar_id=7, term=2, crla=True, program=None, profile=''):
        return _recommendations({"available": crla, "reading_profile": profile}, supplementary, {
            "school_calendar_id": calendar_id, "current_term": term, "rows": list(rows),
            "program": program or {},
        })

    def codes(self, recommendations):
        return [item["code"] for item in recommendations]

    def test_no_results_retains_p1(self):
        self.assertEqual(self.codes(self.recommend()), ["P1"])

    def test_legacy_payload_without_verified_program_scope_retains_p4(self):
        recommendations = self.recommend(self.workbook_row(completed=True))
        self.assertEqual(self.codes(recommendations), ["P4"])

    def program(self, **changes):
        program = {'verified': True, 'school_calendar_id': 7, 'term': 2,
                   'activity_keys': ['lesson-15-gawain-1', 'lesson-15-gawain-2', 'lesson-15-gawain-3']}
        program.update(changes)
        return program

    def perfect_supplementary(self):
        return [{'activity_id': 'word_meaning_match', 'activity_name': 'Word Meaning Match',
                 'accuracy': 100, 'wpm': None}]

    def test_perfect_supplementary_and_completed_subset_need_p1_for_unrecorded_work(self):
        row = self.workbook_row(completed=True)
        original = deepcopy(row)
        recommendations = self.recommend(row, supplementary=self.perfect_supplementary(), program=self.program())
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertIn('1 of 3 prescribed activities', recommendations[0]['text'])
        self.assertEqual(recommendations[0]['evidence'][0]['remaining_activity_keys'],
                         ['lesson-15-gawain-2', 'lesson-15-gawain-3'])
        self.assertEqual(row, original)

    def test_no_recorded_work_but_verified_program_and_perfect_supplementary_need_p1(self):
        recommendations = self.recommend(supplementary=self.perfect_supplementary(), program=self.program())
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertIn('0 of 3 prescribed activities', recommendations[0]['text'])

    def test_entire_verified_program_completed_without_other_triggers_uses_p4(self):
        rows = [self.workbook_row(activity_key=key, completed=True) for key in self.program()['activity_keys']]
        self.assertEqual(self.codes(self.recommend(*rows, program=self.program())), ['P4'])

    def test_program_summary_enriches_existing_p1_without_repeating_continuation_advice(self):
        recommendations = self.recommend(self.workbook_row(), program=self.program())
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertIn('Continue Session 5, Lesson 15, Gawain 1', recommendations[0]['text'])
        self.assertIn('0 of 3 prescribed activities', recommendations[0]['text'])
        self.assertEqual(recommendations[0]['text'].count('Workbook progress:'), 1)

    def test_empty_program_work_enriches_existing_no_results_p1_only_once(self):
        recommendations = self.recommend(program=self.program())
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertIn('Continue assigned ARAL reading activities', recommendations[0]['text'])
        self.assertIn('0 of 3 prescribed activities', recommendations[0]['text'])
        self.assertEqual(len(recommendations[0]['evidence']), 2)

    def test_unfinished_program_can_coexist_with_specific_p2_errors(self):
        row = self.workbook_row(completed=True)
        row['evidence']['scored_answers'] = [{'item_id': 1, 'correct': False}]
        recommendations = self.recommend(row, program=self.program())
        self.assertEqual(self.codes(recommendations), ['P2', 'P1'])
        self.assertEqual(recommendations[0]['evidence'][0]['incorrect_item_ids'], [1])

    def test_wrong_or_unverified_program_period_cannot_supply_missing_work_judgments(self):
        for change in [{'verified': False}, {'school_calendar_id': 8}, {'term': 1}]:
            with self.subTest(change=change):
                recommendations = self.recommend(self.workbook_row(completed=True),
                    supplementary=self.perfect_supplementary(), program=self.program(**change))
                self.assertEqual(self.codes(recommendations), ['P4'])

    def test_program_counts_use_unique_keys_and_actual_current_rows_not_stale_totals(self):
        program = self.program(total_count=99, completed_count=99)
        program['activity_keys'] *= 2
        recommendations = self.recommend(self.workbook_row(completed=True), program=program)
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertIn('1 of 3 prescribed activities', recommendations[0]['text'])

    def test_program_completion_excludes_other_terms_and_school_years(self):
        keys = self.program()['activity_keys']
        rows = [self.workbook_row(activity_key=keys[0], completed=True),
                self.workbook_row(activity_key=keys[1], completed=True, term=1),
                self.workbook_row(activity_key=keys[2], completed=True, school_calendar_id=8)]
        recommendations = self.recommend(*rows, program=self.program())
        self.assertEqual(self.codes(recommendations), ['P1'])
        self.assertEqual(recommendations[0]['evidence'][0]['completed_activity_keys'], [keys[0]])
        self.assertIn('1 of 3 prescribed activities', recommendations[0]['text'])

    def test_ongoing_work_is_p1_without_inventing_incorrect_answers(self):
        row = self.workbook_row(results=['Teacher score: 0/5'], correct_items=0)
        recommendations = self.recommend(row)
        self.assertEqual(self.codes(recommendations), ["P1"])
        self.assertIn('Session 5, Lesson 15, Gawain 1', recommendations[0]['text'])

    def test_pending_review_is_p1_and_not_p2(self):
        row = self.workbook_row()
        row['evidence'].update(pending_review=True, recordings=[self.recording(teacher_score=0)])
        self.assertEqual(self.codes(self.recommend(row)), ['P1'])

    def test_pending_answer_grading_is_not_treated_as_an_incorrect_answer(self):
        row = self.workbook_row()
        row['evidence'].update(pending_review=True,
                               scored_answers=[{'item_id': 'ungraded', 'correct': False}])
        self.assertEqual(self.codes(self.recommend(row)), ['P1'])

    def test_incorrect_answer_generates_p2_without_an_accuracy_threshold(self):
        row = self.workbook_row(completed=True)
        row['evidence']['scored_answers'] = [
            {'item_id': index, 'correct': index != 0} for index in range(10)
        ]
        recommendations = self.recommend(row)
        self.assertEqual(self.codes(recommendations), ['P2'])
        self.assertEqual(recommendations[0]['evidence'][0]['incorrect_item_ids'], [0])

    def test_teacher_zero_is_p2_and_teacher_one_is_not(self):
        row = self.workbook_row(completed=True)
        checked = self.recording(status='checked', review_status='reviewed',
                                 teacher_reviewed=True, teacher_score=0)
        row['evidence']['recordings'] = [checked]
        self.assertEqual(self.codes(self.recommend(row)), ['P2'])
        checked['teacher_score'] = 1
        self.assertEqual(self.codes(self.recommend(row)), ['P4'])

    def test_ongoing_and_specific_errors_can_generate_p1_and_p2(self):
        row = self.workbook_row()
        row['evidence']['scored_answers'] = [{'item_id': 'word-1', 'correct': False}]
        self.assertEqual(self.codes(self.recommend(row)), ['P1', 'P2'])

    def test_oral_recording_uses_p3_without_claiming_automated_results_or_wpm(self):
        row = self.workbook_row(completed=True)
        row['evidence'].update(oral_reading=True, recordings=[self.recording()])
        recommendations = self.recommend(row)
        self.assertEqual(self.codes(recommendations), ['P1', 'P3'])
        self.assertNotIn('automated', recommendations[-1]['text'])
        self.assertNotIn('WPM', recommendations[-1]['text'])

    def test_non_reading_recording_does_not_trigger_p3(self):
        row = self.workbook_row(completed=True)
        row['evidence']['recordings'] = [self.recording()]
        self.assertEqual(self.codes(self.recommend(row)), ['P1'])

    def test_oral_teacher_support_can_trigger_p3_without_an_audio_file(self):
        row = self.workbook_row(completed=True)
        row['evidence'].update(oral_reading=True, recordings=[self.recording(
            has_recording=False, status='checked', review_status='reviewed',
            teacher_reviewed=True, classification='YELLOW', classification_source='teacher')])
        self.assertEqual(self.codes(self.recommend(row)), ['P3'])

    def test_retry_requests_are_workflow_advice_not_incorrect_scores(self):
        row = self.workbook_row()
        row['evidence'].update(retry_requested=True, recordings=[self.recording(
            status='retry', review_status='not_required', teacher_score=0)])
        self.assertEqual(self.codes(self.recommend(row)), ['P1'])

    def test_unverified_and_other_period_rows_cannot_drive_performance_advice(self):
        for change in [{'period_verified': False}, {'school_calendar_id': None},
                       {'school_calendar_id': 8}, {'term': 1}, {'term': None}]:
            with self.subTest(change=change):
                row = self.workbook_row(**change)
                row['evidence'].update(oral_reading=True,
                    scored_answers=[{'item_id': 0, 'correct': False}], recordings=[self.recording()])
                recommendations = self.recommend(row)
                self.assertEqual(self.codes(recommendations), ['P1'])
                self.assertIsNone(recommendations[0]['activity'])

    def test_no_verified_current_period_does_not_use_workbook_results(self):
        row = self.workbook_row()
        row['evidence']['scored_answers'] = [{'item_id': 0, 'correct': False}]
        for change in [{'term': None}, {'calendar_id': None}]:
            self.assertEqual(self.codes(self.recommend(row, **change)), ['P1'])

    def test_repeated_activity_does_not_repeat_advice(self):
        row = self.workbook_row()
        row['evidence']['scored_answers'] = [{'item_id': 0, 'correct': False}]
        recommendations = self.recommend(row, deepcopy(row))
        self.assertEqual(self.codes(recommendations), ['P1', 'P2'])
        self.assertEqual(len(recommendations[1]['evidence']), 1)

    def test_supplementary_rules_remain_available_alongside_workbook(self):
        supplementary = {'activity_id': 'fluency_reading', 'activity_name': 'Fluency Reading',
                         'accuracy': 70, 'wpm': 40, 'automated_speech_analysis': True,
                         'evidence_source': 'Assessment', 'record_id': 99, 'material_id': 5}
        recommendations = self.recommend(self.workbook_row(), supplementary=[supplementary])
        self.assertEqual(self.codes(recommendations), ['P2', 'P3', 'P1'])
        self.assertIn('automated fluency results', recommendations[1]['text'])
        self.assertEqual(recommendations[0]['evidence'][0]['record_id'], 99)

    def test_unverified_workbook_does_not_suppress_supplementary_advice(self):
        supplementary = {'activity_id': 'word_meaning_match', 'activity_name': 'Word Meaning Match',
                         'accuracy': 60, 'wpm': None}
        self.assertEqual(self.codes(self.recommend(self.workbook_row(period_verified=False),
                                                  supplementary=[supplementary])), ['P2'])

    def test_non_automated_supplementary_does_not_claim_automated_analysis(self):
        supplementary = {'activity_id': 'fluency_reading', 'activity_name': 'Fluency Reading',
                         'accuracy': 90, 'wpm': 0, 'automated_speech_analysis': False}
        recommendations = self.recommend(supplementary=[supplementary])
        self.assertEqual(self.codes(recommendations), ['P3'])
        self.assertNotIn('automated', recommendations[0]['text'])

    def test_baseline_message_is_retained_with_a_reason_and_evidence(self):
        recommendations = self.recommend(self.workbook_row(completed=True), crla=False)
        self.assertEqual(len(recommendations), 1)
        self.assertIn('An official CRLA result is not yet available.', recommendations[0]['text'])
        self.assertIn('may use Practice Mode', recommendations[0]['text'])
        self.assertEqual(recommendations[0]['code'], 'P0')
        self.assertEqual(recommendations[0]['evidence'][0]['source'], 'Assessment')

    def test_no_official_crla_result_only_produces_p0_even_with_old_activity_evidence(self):
        row = self.workbook_row()
        row['evidence'].update(oral_reading=True, pending_review=True,
            recordings=[self.recording()], scored_answers=[{'item_id': 1, 'correct': False}])
        supplementary = [{'activity_id': 'fluency_reading', 'activity_name': 'Fluency Reading',
                          'accuracy': 0, 'wpm': 1}]
        recommendations = self.recommend(row, crla=False, supplementary=supplementary, program=self.program())
        self.assertEqual(self.codes(recommendations), ['P0'])
        self.assertNotIn('Continue', recommendations[0]['text'])
        self.assertEqual(self.codes(self.recommend(crla=False)), ['P0'])

    def test_grade_level_p5_overrides_activity_rules_and_points_to_practice_mode(self):
        row = self.workbook_row()
        row['evidence'].update(oral_reading=True, recordings=[self.recording()],
                               scored_answers=[{'item_id': 1, 'correct': False}])
        supplementary = [{'activity_id': 'fluency_reading', 'activity_name': 'Fluency Reading',
                          'accuracy': 0, 'wpm': 1}]
        for profile in ['Reading At Grade Level', 'Readers at Grade Level', 'Reader at Grade Level']:
            with self.subTest(profile=profile):
                recommendations = self.recommend(row, profile=profile, supplementary=supplementary,
                                                 program=self.program())
                self.assertEqual(self.codes(recommendations), ['P5'])
                self.assertIn('Practice Mode', recommendations[0]['text'])
                self.assertNotIn('workbook', recommendations[0]['text'])
                self.assertEqual(recommendations[0]['evidence'][0]['value'], 'Reading At Grade Level')
        self.assertEqual(self.codes(self.recommend(profile='Reading At Grade Level')), ['P5'])

    def test_unavailable_result_takes_precedence_over_stale_grade_level_label(self):
        self.assertEqual(self.codes(self.recommend(crla=False, profile='Reading At Grade Level')), ['P0'])
        result = _recommendations({'available': True, 'finalized_without_submission': True,
                                   'reading_profile': 'Low Emerging Reader'}, [], {})
        self.assertEqual(self.codes(result), ['P0'])

    def test_non_grade_level_classifications_keep_existing_activity_rules(self):
        for profile in ['Low Emerging Reader', 'High Emerging Reader', 'Developing Reader', 'Transitioning Reader']:
            self.assertEqual(self.codes(self.recommend(self.workbook_row(), profile=profile)), ['P1'])

    def test_accuracy_and_wpm_do_not_substitute_for_an_official_grade_level_classification(self):
        recommendations = _recommendations({'available': True, 'reading_profile': 'Developing Reader',
                                           'accuracy': 100, 'wpm': 100}, [], {})
        self.assertEqual(self.codes(recommendations), ['P1'])

    def test_every_recommendation_retains_code_activity_reason_and_evidence(self):
        row = self.workbook_row()
        row['evidence'].update(oral_reading=True, scored_answers=[{'item_id': 0, 'correct': False}],
                               recordings=[self.recording()])
        for item in self.recommend(row):
            self.assertIn(item['code'], ['P1', 'P2', 'P3', 'P4'])
            self.assertEqual(item['activity']['activity_key'], row['activity_key'])
            self.assertTrue(item['reason'])
            self.assertTrue(item['evidence'])
            self.assertTrue(all(evidence['source'] for evidence in item['evidence']))
