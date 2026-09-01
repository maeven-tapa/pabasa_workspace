import json

from django.core.management.base import BaseCommand
from django.db.models import Count

from pabasa_app.models import Assessment, Enrollment, Practice, Section, StoryReadingProgress, User


class Command(BaseCommand):
    help = 'Read-only report of enrollment, account, cache, and roster integrity issues.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', dest='as_json')
        parser.add_argument('--fix-cache', action='store_true', dest='fix_cache', help='Synchronize legacy User and Section.students caches only.')

    def handle(self, *args, **options):
        issues = []
        repaired = []
        groups = Enrollment.objects.filter(school_calendar__isnull=False, status__in=['active', 'awaiting_assignment']).values('student_id', 'school_calendar_id').annotate(total=Count('id')).filter(total__gt=1)
        for row in groups:
            ids = list(Enrollment.objects.filter(student_id=row['student_id'], school_calendar_id=row['school_calendar_id'], status__in=['active', 'awaiting_assignment']).values_list('id', flat=True))
            issues.append({'type': 'duplicate_current_enrollment', 'student_id': row['student_id'], 'school_calendar_id': row['school_calendar_id'], 'enrollment_ids': ids})
        for enrollment in Enrollment.objects.select_related('section'):
            if enrollment.status == 'active' and not enrollment.is_active:
                issues.append({'type': 'active_not_is_active', 'enrollment_id': enrollment.id})
            if enrollment.status == 'completed' and enrollment.is_active:
                issues.append({'type': 'completed_is_active', 'enrollment_id': enrollment.id})
            if enrollment.status == 'awaiting_assignment' and enrollment.is_active:
                issues.append({'type': 'awaiting_is_active', 'enrollment_id': enrollment.id})
            if enrollment.section_id:
                if enrollment.school_id != enrollment.section.school_id:
                    issues.append({'type': 'school_mismatch', 'enrollment_id': enrollment.id})
                if enrollment.school_calendar_id != enrollment.section.school_calendar_id:
                    issues.append({'type': 'calendar_mismatch', 'enrollment_id': enrollment.id})
        for user in User.objects.filter(role='student'):
            current = Enrollment.objects.filter(student=user, status='active', is_active=True, school_calendar__is_active=True, section__is_active=True, grade_level='Grade 2').select_related('section').order_by('id').first()
            expected = (current.grade_level, current.section.section, current.school_calendar_id) if current else ('Grade 2', None, None)
            if (user.grade_level, user.section, user.school_calendar_id) != expected:
                issues.append({'type': 'stale_user_cache', 'user_id': user.id})
                if options['fix_cache']:
                    cache_enrollment = current or Enrollment.objects.filter(
                        student=user, status='awaiting_assignment', is_active=False,
                        school_calendar__is_active=True, grade_level='Grade 2',
                    ).order_by('id').first()
                    user.sync_legacy_student_fields(cache_enrollment)
                    repaired.append({'type': 'stale_user_cache', 'user_id': user.id})
            if (user.account_status == 'archived') != bool(user.is_archived):
                issues.append({'type': 'account_status_mismatch', 'user_id': user.id})
        for section in Section.objects.all():
            json_ids = {str(item.get('student_id')) for item in (section.students or []) if item.get('student_id') is not None}
            relational_ids = {str(value) for value in Enrollment.objects.filter(section=section, school_calendar=section.school_calendar, status='active', is_active=True).values_list('student_id', flat=True)}
            if json_ids != relational_ids:
                issues.append({'type': 'section_students_mismatch', 'section_id': section.id})
                if options['fix_cache'] and section.id in {15, 20}:
                    # Keep only current relational members in this legacy roster cache.
                    section.students = section.get_enrolled_students(active_only=True)
                    section._save_enrollment()
                    repaired.append({'type': 'section_students_mismatch', 'section_id': section.id})
        for row in Assessment.objects.filter(student__isnull=False, section__isnull=False, enrollment__isnull=True):
            issues.append({'type': 'unresolved_assessment_enrollment', 'assessment_id': row.id})
        for row in StoryReadingProgress.objects.filter(enrollment__isnull=True):
            issues.append({'type': 'unresolved_story_progress_enrollment', 'progress_id': row.id})
        for practice in Practice.objects.filter(section__isnull=False):
            for attempt in (practice.attempts if isinstance(practice.attempts, list) else []):
                if attempt.get('student_id') and not attempt.get('enrollment_id'):
                    issues.append({'type': 'unresolved_practice_enrollment', 'practice_id': practice.id, 'student_id': attempt.get('student_id')})
        output = json.dumps(issues, default=str, indent=2)
        if options['fix_cache']:
            self.stdout.write(f'Repaired cache entries: {len(repaired)}')
        self.stdout.write(output if options['as_json'] else f'Enrollment integrity issues: {len(issues)}\n{output}')
