from datetime import datetime, timedelta, timezone as datetime_timezone
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .achievements import (
    FINALIZED_WITHOUT_SUBMISSION, _streaks, assessment_summary, practice_summary,
    prescribed_catalog, prescribed_summary, refresh_student_achievements,
)
from .models import (
    Assessment, Material, SchoolCalendar, StudentAchievement, StudentActivityProgress,
    StudentActivityRecordingSubmission, StudentLearningDay, User,
)
from .system_clock import now as system_now


class StudentAchievementTests(TestCase):
    def setUp(self):
        self.student = self.user('student', 'ACH-STUDENT')
        self.other = self.user('student', 'ACH-OTHER')
        self.teacher = self.user('teacher', 'ACH-TEACHER')
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        self.scope = {'school_calendar': self.calendar, 'term': 1}
        self.today = timezone.localdate(system_now())
        self.catalog = {f'activity-{i}': {'activity_key': f'activity-{i}', 'session_number': i // 5 + 1}
                        for i in range(10)}
        self.counter = 0

    def user(self, role, code):
        return User.objects.create(custom_id=code, role=role, first_name='Test', last_name=code,
                                   sex='female', birth_month=1, birth_day=1, birth_year=2015,
                                   password_hash='unused')

    def progress(self, keys, student=None, term=1, complete=True):
        StudentActivityProgress.objects.bulk_create([
            StudentActivityProgress(student=student or self.student, school_calendar=self.calendar,
                                    term=term, activity_key=key, activity_completed=complete,
                                    completed_items=5, total_items=5) for key in keys
        ])

    def result(self, material=None, source=None, student=None, completed=True, at=None, remarks=''):
        self.counter += 1
        return Assessment.objects.create(
            code=f'ACH-RESULT-{self.counter}', title='Reading', teacher=self.teacher,
            assessment_type='word', material=material, source_assessment=source,
            student=student or self.student, attempt_status='completed' if completed else 'started',
            completed_at=(at or system_now()) if completed else None, remarks=remarks,
        )

    def practice(self, mode, level, difficulty='easy', language='English', student=None,
                 status='completed', stars=0, completed_at=None):
        return Material.objects.create(
            title='Practice', type='practice', item_type='word', language=language,
            status='published', is_system_owned=True, source_type='shared',
            difficulty_level=difficulty, content_text='sample',
            content_json={'mode': mode, 'difficulty': difficulty, 'level': f'level_{level}',
                          'student_completions': {str((student or self.student).pk): {
                              'status': status, 'stars_earned': stars,
                              'completed_at': (completed_at or system_now()).isoformat(),
                          }}},
        )

    def unlocked(self, payload):
        return {badge['id'] for badge in payload['badges'] if badge['unlocked']}

    def test_catalog_covers_fifteen_sessions_and_legacy_entries(self):
        catalog = prescribed_catalog()
        self.assertEqual({item['session_number'] for item in catalog.values()}, set(range(1, 16)))
        self.assertIn('lesson-1-gawain-1', catalog)
        self.assertFalse(any(item.get('superseded_by') for item in catalog.values()))

    def test_new_student_gets_twelve_locked_badges(self):
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertEqual(len(payload['badges']), 12)
        self.assertEqual(self.unlocked(payload), set())

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_halfway_and_session_require_saved_completion(self, catalog):
        catalog.return_value = self.catalog
        self.progress(list(self.catalog)[:4])
        self.progress(['activity-4'], complete=False)  # All items submitted, awaiting review.
        summary = prescribed_summary(self.student, **self.scope)
        self.assertEqual(summary['completed_sessions'], 0)
        self.assertNotIn('rising-reader', summary['earned'])
        row = StudentActivityProgress.objects.get(student=self.student, activity_key='activity-4', **self.scope)
        row.activity_completed = True
        row.save()
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertTrue({'rising-reader', 'session-starter'} <= self.unlocked(payload))
        self.assertEqual(payload['metrics']['prescribed_percent'], 50)

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_exact_thresholds_do_not_round_up(self, catalog):
        catalog.return_value = {f'a-{i}': {'session_number': 1} for i in range(201)}
        self.progress([f'a-{i}' for i in range(100)])
        summary = prescribed_summary(self.student, **self.scope)
        self.assertEqual(summary['prescribed_percent'], 50)
        self.assertNotIn('rising-reader', summary['earned'])
        self.progress([f'a-{i}' for i in range(100, 200)])
        summary = prescribed_summary(self.student, **self.scope)
        self.assertEqual(summary['prescribed_percent'], 99)
        self.assertNotIn('reading-champion', summary['earned'])

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_five_sessions_and_ten_distinct_activities(self, catalog):
        catalog.return_value = {f'a-{i}': {'session_number': i // 2 + 1} for i in range(10)}
        self.progress(catalog.return_value)
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertTrue({'session-explorer', 'activity-achiever', 'reading-champion'} <= self.unlocked(payload))
        self.assertEqual(payload['metrics']['completed_sessions'], 5)

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_prescribed_cannot_mix_terms_or_students(self, catalog):
        catalog.return_value = self.catalog
        self.progress(list(self.catalog)[:4])
        self.progress(list(self.catalog)[4:], term=2)
        self.progress(list(self.catalog)[4:], student=self.other)
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertNotIn('rising-reader', self.unlocked(payload))
        self.assertEqual(payload['metrics']['completed_activities'], 4)
        self.assertEqual(prescribed_summary(self.student)['completed_activities'], 0)

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_alias_counts_once_and_canonical_reset_wins(self, catalog):
        catalog.return_value = {'session-2-lesson-4-gawain-2': {'session_number': 2}}
        self.progress(['lesson-4-gawain-2'])
        self.assertEqual(prescribed_summary(self.student, **self.scope)['completed_activities'], 1)
        self.progress(['session-2-lesson-4-gawain-2'], complete=False)
        self.assertEqual(prescribed_summary(self.student, **self.scope)['completed_activities'], 0)

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_awards_persist_across_resets_terms_and_new_content(self, catalog):
        catalog.return_value = self.catalog
        self.progress(self.catalog)
        original = self.unlocked(refresh_student_achievements(self.student, self.scope))
        StudentActivityProgress.objects.filter(student=self.student).update(activity_completed=False)
        catalog.return_value = {**self.catalog, 'new': {'session_number': 1}}
        self.assertEqual(self.unlocked(refresh_student_achievements(self.student, {'term': 2})), original)

    def test_assessments_are_distinct_saved_results_not_practice_or_finalization(self):
        material = Material.objects.create(title='Assessment', type='assessment', item_type='word')
        self.result(material=material)
        self.result(material=material)
        self.result(completed=False)
        self.result(remarks=FINALIZED_WITHOUT_SUBMISSION)
        practice = Material.objects.create(title='Practice', type='practice', item_type='word')
        self.result(material=practice)
        self.result(student=self.other)
        self.assertEqual(assessment_summary(self.student)[0], 1)
        self.assertFalse(StudentAchievement.objects.filter(student=self.student, achievement_key='book-explorer').exists())
        self.result()
        self.result()
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='book-explorer').exists())

    def test_source_assessment_retries_count_once(self):
        source = Assessment.objects.create(code='SOURCE', title='Source', teacher=self.teacher, assessment_type='word')
        for _ in range(3):
            self.result(source=source)
        self.assertEqual(assessment_summary(self.student)[0], 1)

    def test_material_result_exclusion_is_applied_before_first_award(self):
        material = Material.objects.create(
            title='Finalized assessment', type='assessment', item_type='word', teacher=self.teacher,
        )
        material.record_assessment_result(
            self.student, status='completed', remarks=FINALIZED_WITHOUT_SUBMISSION,
        )
        self.assertEqual(assessment_summary(self.student)[0], 0)
        self.assertFalse(StudentAchievement.objects.filter(student=self.student).exists())
        self.assertFalse(StudentLearningDay.objects.filter(student=self.student).exists())
        material.record_assessment_result(self.student, status='completed', total_score=12)
        self.assertEqual(assessment_summary(self.student)[0], 1)
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='first-steps').exists())
        self.assertTrue(StudentLearningDay.objects.filter(student=self.student, date=self.today).exists())
        self.assertEqual(material.assessment_results.latest('pk').total_score, 12)

    def test_source_result_exclusion_is_applied_before_first_award(self):
        source = Assessment.objects.create(
            code='EXCLUDED-SOURCE', title='Source', teacher=self.teacher, assessment_type='word',
        )
        source.record_attempt(
            self.student, status='completed', completed_at=system_now(),
            remarks=FINALIZED_WITHOUT_SUBMISSION,
        )
        self.assertEqual(assessment_summary(self.student)[0], 0)
        self.assertFalse(StudentAchievement.objects.filter(student=self.student).exists())
        self.assertFalse(StudentLearningDay.objects.filter(student=self.student).exists())
        # The default completion timestamp path must still award a genuine result.
        source.record_attempt(self.student, status='completed', total_score=15)
        self.assertEqual(assessment_summary(self.student)[0], 1)
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='first-steps').exists())
        self.assertEqual(source.attempt_rows.latest('pk').total_score, 15)

    def test_material_and_legacy_source_results_count_as_same_assessment(self):
        source = Assessment.objects.create(code='LEGACY-SOURCE', title='Source', teacher=self.teacher, assessment_type='word')
        material = Material.objects.create(title='Reading', type='assessment', item_type='word', assessment=source)
        self.result(source=source)
        self.result(source=source, material=material)
        self.result(material=material)
        self.assertEqual(assessment_summary(self.student)[0], 1)

    @patch('pabasa_app.achievements.prescribed_catalog')
    def test_completion_event_preserves_award_before_any_dashboard_visit(self, catalog):
        catalog.return_value = {'activity-0': {'session_number': 1}}
        row = StudentActivityProgress.objects.create(
            student=self.student, activity_key='activity-0', activity_completed=True, **self.scope,
        )
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='reading-champion').exists())
        row.activity_completed = False
        row.save()
        self.assertIn('reading-champion', self.unlocked(refresh_student_achievements(self.student, self.scope)))

    def test_practice_save_records_award_and_day_before_dashboard_visit(self):
        from .views import _record_material_practice_completion
        for i in range(1, 5):
            self.practice('hunt', i)
        material = self.practice('hunt', 5, status='started')
        _record_material_practice_completion(material, self.student, {'stars_earned': 100, 'completed_at': system_now()})
        material.refresh_from_db()
        self.assertIsInstance(material.content_json['student_completions'][str(self.student.pk)]['completed_at'], str)
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='word-hunter').exists())
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='star-collector').exists())
        self.assertTrue(StudentLearningDay.objects.filter(student=self.student, date=self.today).exists())

    def test_profile_matches_one_hundred_star_threshold_and_keeps_earned_badge(self):
        session = self.client.session
        session['user_id'] = self.student.pk
        session['user_role'] = 'student'
        session.save()
        self.student.theme_stars_credited = 99
        self.student.save()
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['achievement_star_collector'])
        self.assertContains(response, 'Earn 100 lifetime stars')
        self.student.theme_stars_credited = 100
        self.student.save()
        self.assertTrue(self.client.get(reverse('profile')).context['achievement_star_collector'])
        self.student.theme_stars_credited = 0
        self.student.save()
        self.assertTrue(self.client.get(reverse('profile')).context['achievement_star_collector'])

    def test_several_assessments_on_one_day_do_not_make_a_streak(self):
        for _ in range(15):
            self.result()
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertEqual(payload['metrics']['reading_days'], 1)
        self.assertNotIn('reading-streak', self.unlocked(payload))

    def test_streak_uses_actual_consecutive_dates_and_remains_earned(self):
        for i in range(7):
            self.result(at=system_now() - timedelta(days=i))
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertIn('reading-streak', self.unlocked(payload))
        self.assertEqual(payload['metrics']['best_streak'], 7)
        self.assertEqual(_streaks({self.today - timedelta(days=i + 10) for i in range(7)}, self.today), (0, 7))

    def test_streak_gaps_and_future_dates(self):
        days = {self.today - timedelta(days=i) for i in (0, 1, 2, 4, 5, 6, 7)}
        self.assertEqual(_streaks(days | {self.today + timedelta(days=1)}, self.today), (3, 4))
        self.result(at=system_now() + timedelta(days=1))
        self.assertEqual(assessment_summary(self.student)[0], 0)
        self.assertFalse(StudentLearningDay.objects.filter(student=self.student).exists())

    def test_streak_dates_use_manila_midnight(self):
        from .achievements import _local_date
        before = datetime(2026, 10, 1, 15, 59, tzinfo=datetime_timezone.utc)
        self.assertEqual(_local_date(before).isoformat(), '2026-10-01')
        self.assertEqual(_local_date(before + timedelta(minutes=2)).isoformat(), '2026-10-02')

    def test_review_does_not_create_reading_day_on_teacher_check_date(self):
        submission = StudentActivityRecordingSubmission.objects.create(
            student=self.student, activity_key='lesson-1-gawain-1', audio_file='synthetic.webm',
        )
        StudentLearningDay.objects.filter(student=self.student).delete()
        StudentActivityRecordingSubmission.objects.filter(pk=submission.pk).update(submitted_at=system_now() - timedelta(days=3))
        submission.refresh_from_db()
        submission.status = 'checked'
        submission.save()
        submission.refresh_from_db()
        self.assertEqual(timezone.localdate(submission.submitted_at), self.today - timedelta(days=3))
        StudentActivityProgress.objects.create(student=self.student, activity_key='lesson-1-gawain-1',
                                               activity_completed=True, **self.scope)
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertEqual(payload['metrics']['reading_days'], 1)
        self.assertFalse(StudentLearningDay.objects.filter(student=self.student, date=self.today).exists())

    def test_recording_retry_endpoint_counts_the_seventh_reading_day(self):
        for i in range(1, 7):
            StudentLearningDay.objects.create(student=self.student, date=self.today - timedelta(days=i))
        submission = StudentActivityRecordingSubmission.objects.create(
            student=self.student, activity_key='lesson-29-gawain-3', item_index=0,
            audio_file='old-synthetic.webm', status='retry',
        )
        StudentActivityRecordingSubmission.objects.filter(pk=submission.pk).update(
            submitted_at=system_now() - timedelta(days=6),
        )
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student'})
        session.save()
        with tempfile.TemporaryDirectory(prefix='pabasa-achievement-retry-') as folder, override_settings(
            MEDIA_ROOT=folder,
        ), patch('pabasa_app.views._active_prescribed_student', return_value=self.student), patch(
            'pabasa_app.views._student_can_open_prescribed_activity', return_value=True,
        ), patch('pabasa_app.views._enforce_student_access_for_request', return_value=None), patch(
            'pabasa_app.views._current_learning_context', return_value={**self.scope, 'state': 'ARAL_ACTIVE'},
        ):
            response = self.client.post(reverse('lesson29_trace_say_recording'), {
                'item_index': '0', 'duration_seconds': '1',
                'audio': SimpleUploadedFile('retry.webm', b'synthetic audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        submission.refresh_from_db()
        self.assertEqual(timezone.localdate(submission.submitted_at), self.today)
        self.assertTrue(StudentLearningDay.objects.filter(student=self.student, date=self.today).exists())
        self.assertEqual(StudentLearningDay.objects.filter(student=self.student).count(), 7)
        self.assertTrue(StudentAchievement.objects.filter(student=self.student, achievement_key='reading-streak').exists())

    def test_same_filename_upload_preserves_original_and_new_learning_dates(self):
        submission = StudentActivityRecordingSubmission.objects.create(
            student=self.student, activity_key='session-4-gawain-1', item_index=0,
            audio_file='retry.webm', status='retry',
        )
        old_time = system_now() - timedelta(days=6)
        StudentActivityRecordingSubmission.objects.filter(pk=submission.pk).update(submitted_at=old_time)
        submission.refresh_from_db()
        with tempfile.TemporaryDirectory(prefix='pabasa-achievement-upload-') as folder, override_settings(MEDIA_ROOT=folder):
            submission.audio_file = SimpleUploadedFile('retry.webm', b'new synthetic audio')
            submission.status = 'submitted'
            submission.save(update_fields=['audio_file', 'status', 'updated_at'])
        submission.refresh_from_db()
        self.assertEqual(timezone.localdate(submission.submitted_at), self.today)
        self.assertEqual(set(StudentLearningDay.objects.filter(student=self.student).values_list('date', flat=True)),
                         {timezone.localdate(old_time), self.today})

    def test_recording_metadata_save_keeps_original_submission_date(self):
        submission = StudentActivityRecordingSubmission.objects.create(
            student=self.student, activity_key='lesson-29-gawain-3', item_index=0,
            audio_file='synthetic.webm', status='submitted',
        )
        StudentLearningDay.objects.filter(student=self.student).delete()
        old_time = system_now() - timedelta(days=3)
        StudentActivityRecordingSubmission.objects.filter(pk=submission.pk).update(submitted_at=old_time)
        submission.refresh_from_db()
        submission.expected_text = 'a'
        submission.save(update_fields=['expected_text', 'updated_at'])
        submission.refresh_from_db()
        self.assertEqual(submission.submitted_at, old_time)
        self.assertFalse(StudentLearningDay.objects.filter(student=self.student, date=self.today).exists())

    def test_color_and_hunt_easy_levels_count_only_own_saved_completions(self):
        for i in range(1, 6):
            self.practice('color', i)
            self.practice('hunt', i, student=self.other)
        keys = practice_summary(self.student)[2]
        self.assertIn('color-champion', keys)
        self.assertNotIn('word-hunter', keys)
        self.assertNotIn('practice-star', keys)

    def test_levels_cannot_be_combined_across_languages(self):
        for i in range(1, 6):
            self.practice('color', i, language='English' if i < 3 else 'Filipino')
        self.assertNotIn('color-champion', practice_summary(self.student)[2])

    def test_practice_star_requires_all_45_levels(self):
        for mode in ('free', 'color', 'hunt'):
            for difficulty in ('easy', 'medium', 'hard'):
                for level in range(1, 6):
                    self.practice(mode, level, difficulty=difficulty,
                                  status='started' if (mode, difficulty, level) == ('hunt', 'hard', 5) else 'completed')
        self.assertNotIn('practice-star', practice_summary(self.student)[2])
        last = Material.objects.get(content_json__mode='hunt', content_json__difficulty='hard', content_json__level='level_5')
        last.content_json['student_completions'][str(self.student.pk)]['status'] = 'completed'
        last.save()
        self.assertIn('practice-star', practice_summary(self.student)[2])

    def test_star_collector_boundary_and_spent_stars(self):
        self.student.theme_stars_credited = 99
        self.student.save()
        self.assertNotIn('star-collector', self.unlocked(refresh_student_achievements(self.student, self.scope)))
        self.student.theme_stars_credited = 100
        self.student.available_stars = 0
        self.student.save()
        self.assertIn('star-collector', self.unlocked(refresh_student_achievements(self.student, self.scope)))
        self.assertEqual(practice_summary(self.student)[0], 100)

    def test_filipino_stars_match_badge_profile_and_wallet_without_double_credit(self):
        from .views import _student_theme_lifetime_stars, _sync_student_theme_wallet
        for mode in ('free', 'color', 'hunt'):
            for difficulty in ('easy', 'medium', 'hard'):
                for i in range(1, 6):
                    self.practice(mode, i, difficulty=difficulty, language='Filipino',
                                  stars=1 if mode == 'free' else 3)
        self.student.theme_stars_credited = self.student.available_stars = 45
        self.student.save()
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertEqual(payload['metrics']['lifetime_stars'], 105)
        self.assertEqual(_student_theme_lifetime_stars(self.student), 105)
        self.assertIn('star-collector', self.unlocked(payload))
        self.assertEqual(_sync_student_theme_wallet(self.student), 105)
        self.student.refresh_from_db()
        self.assertEqual((self.student.theme_stars_credited, self.student.available_stars), (105, 105))
        self.student.available_stars = 5  # Spending cannot reduce lifetime stars.
        self.student.save()
        self.assertEqual(_sync_student_theme_wallet(self.student), 105)
        self.student.refresh_from_db()
        self.assertEqual(self.student.available_stars, 5)
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student'})
        session.save()
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.context['achievement_total_stars'], 105)
        self.assertTrue(profile.context['achievement_star_collector'])

    def test_bilingual_stars_combine_and_credit_only_the_uncredited_difference(self):
        from .views import _student_theme_lifetime_stars, _sync_student_theme_wallet
        for language in ('English', 'Filipino'):
            for mode in ('free', 'color'):
                for difficulty in ('easy', 'medium', 'hard'):
                    for level in range(1, 6):
                        self.practice(mode, level, difficulty=difficulty, language=language,
                                      stars=1 if mode == 'free' else 3)
            if language == 'English':
                self.assertEqual(_sync_student_theme_wallet(self.student), 60)
                self.student.available_stars = 10  # Fifty previously credited stars were spent.
                self.student.save()
        # Another learner's stars must not inflate the combined total.
        self.practice('hunt', 1, student=self.other, stars=3)
        payload = refresh_student_achievements(self.student, self.scope)
        self.assertEqual(payload['metrics']['lifetime_stars'], 120)
        self.assertIn('star-collector', self.unlocked(payload))
        self.assertNotIn('practice-star', self.unlocked(payload))
        self.assertEqual(_student_theme_lifetime_stars(self.student), 120)
        self.assertEqual(_sync_student_theme_wallet(self.student), 120)
        self.student.refresh_from_db()
        self.assertEqual((self.student.theme_stars_credited, self.student.available_stars), (120, 70))
        self.assertEqual(_sync_student_theme_wallet(self.student), 120)
        self.student.refresh_from_db()
        self.assertEqual(self.student.available_stars, 70)
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student'})
        session.save()
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.context['achievement_total_stars'], 120)
        self.assertTrue(profile.context['achievement_star_collector'])
        # Credited and imported lifetime totals already include progression stars.
        self.student.theme_stars_credited = 150
        self.student.preference = {'total_stars_earned': 160}
        self.assertEqual(practice_summary(self.student)[0], 160)

    def test_english_stars_and_invalid_optional_preference_use_shared_total(self):
        from .views import _student_theme_lifetime_stars
        self.practice('color', 1, stars=3)
        self.student.preference = {'total_stars_earned': 'invalid'}
        self.assertEqual(_student_theme_lifetime_stars(self.student), practice_summary(self.student)[0])
        self.assertEqual(_student_theme_lifetime_stars(self.student), 3)

    def test_malformed_optional_practice_data_does_not_crash_dashboard(self):
        self.student.preference = {'total_stars_earned': 'invalid'}
        self.practice('color', 1)
        material = Material.objects.get(content_json__mode='color')
        material.content_json['student_completions'][str(self.student.pk)] = {'status': 'completed', 'completed_at': 'bad', 'stars_earned': 'bad'}
        material.save()
        self.assertEqual(len(refresh_student_achievements(self.student, self.scope)['badges']), 12)

    def test_refresh_is_idempotent_without_repeat_database_writes(self):
        self.result()
        refresh_student_achievements(self.student, self.scope)
        with CaptureQueriesContext(connection) as queries:
            refresh_student_achievements(self.student, self.scope)
        self.assertFalse(any(query['sql'].lstrip().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in queries))

    def test_server_render_has_twelve_badges_and_no_client_unlock_logic(self):
        payload = refresh_student_achievements(self.student, self.scope)
        html = render_to_string('pabasa_app/dashboard.html', {'nav_role': 'student', 'student_achievements': payload})
        self.assertEqual(html.count('data-achievement-id='), 12)
        self.assertIn('100 lifetime stars', html)
        self.assertNotIn('pabasa_practice_progress_v1', html)

    def test_nonstudent_cannot_receive_student_badges(self):
        self.assertEqual(refresh_student_achievements(self.teacher)['badges'], [])
        self.assertFalse(StudentAchievement.objects.filter(student=self.teacher).exists())

    def test_dashboard_ignores_requested_student_and_browser_completion_flags(self):
        StudentAchievement.objects.create(student=self.other, achievement_key='star-collector')
        session = self.client.session
        session['user_id'] = self.student.pk
        session['user_role'] = 'student'
        session.save()
        with patch('pabasa_app.views._dashboard_context', return_value={'nav_role': 'student'}), patch(
            'pabasa_app.views._current_learning_context', return_value=self.scope,
        ):
            response = self.client.get(reverse('dashboard'), {'student_id': self.other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('star-collector', self.unlocked(response.context['student_achievements']))
        self.assertContains(response, 'data-achievement-id=', count=12)
        client = Client()
        self.assertEqual(client.get(reverse('dashboard')).status_code, 302)
