"""Request-local data for class listings; never caches one student's progress globally."""

from collections import defaultdict

from django.db.models import F, Window
from django.db.models.functions import RowNumber

from .models import Assessment, Enrollment, StoryResponseSubmission


SUMMARY_CONTENT_KEYS = frozenset({
    'template_title', 'template_activity_name', 'template_lesson', 'template_type',
    'activity_type', 'activity_key', 'activity_slug', 'activity_format',
    'activity_id', 'activity_name', 'language', 'sourceMaterialId',
    'source_material_id', 'source_story_reading_material_id',
})


def listing_summary(item, *, kind):
    """Keep launch metadata, not the exercises already loaded by Material readers."""
    compact = {key: value for key, value in item.items() if key != 'content_text'}
    if kind == 'material':
        compact.pop('content', None)
        content = item.get('content_json') or {}
        compact['content_json'] = {
            key: value for key, value in content.items() if key in SUMMARY_CONTENT_KEYS
        }
    return compact


class ClassMaterialsProgress:
    """Batch the lookups that otherwise run once (or three times) per card."""

    def __init__(self, student, materials, assessments, practices):
        self.student = student
        self._attempts = defaultdict(list)
        self._result_cache = {}
        self._material_ids = [material.id for material in materials]
        self._practice_enrollments = {}
        self._submissions = None
        self._assessment_attempts = {}
        if student is None:
            return

        group_ids = {
            assessment.source_assessment_id or assessment.id
            for assessment in assessments
        }
        if group_ids:
            fields = (
                'source_assessment_id', 'enrollment__student_id',
                'enrollment__school_calendar_id', 'student_id', 'attempt_status',
                'completed_at', 'wpm', 'fluency_score', 'accuracy',
                'pronunciation_score', 'time_score', 'total_score',
                'crla_classification', 'classification',
            )
            rows = Assessment.objects.filter(
                source_assessment_id__in=group_ids, student_id=student.id,
            ).order_by('attempt_number', 'created_at', 'id').values(*fields)
            for row in rows:
                row['status'] = row.pop('attempt_status')
                completed_at = row['completed_at']
                row['completed_at'] = completed_at.isoformat() if completed_at else None
                self._attempts[row['source_assessment_id']].append(row)

        section_ids = {practice.section_id for practice in practices if practice.section_id}
        if section_ids:
            enrollments = Enrollment.objects.filter(
                student_id=student.id, status='active', is_active=True,
                school_calendar__is_active=True, section__is_active=True,
                section_id__in=section_ids,
            ).order_by('id').values_list('section_id', 'id')
            for section_id, enrollment_id in enrollments:
                self._practice_enrollments.setdefault(section_id, enrollment_id)

    def attempts(self, assessment):
        if assessment.id not in self._assessment_attempts:
            rows = self._attempts[assessment.source_assessment_id or assessment.id]
            calendar_id = assessment.section.school_calendar_id if assessment.section_id else None
            if calendar_id:
                rows = [row for row in rows if (
                    row['enrollment__student_id'] == self.student.id
                    and row['enrollment__school_calendar_id'] == calendar_id
                )]
            self._assessment_attempts[assessment.id] = rows
        return self._assessment_attempts[assessment.id]

    def completed_result(self, material, *, scope=None, remarks_prefix=None):
        calendar_id = getattr(scope.get('school_calendar'), 'id', None) if scope else None
        term = scope.get('term') if scope else None
        key = (scope is not None, calendar_id, term, remarks_prefix)
        if key not in self._result_cache:
            rows = Assessment.objects.filter(
                material_id__in=self._material_ids, student_id=self.student.id,
                attempt_status='completed',
            )
            if remarks_prefix is not None:
                # Dedicated Fluency completion permits a missing date, as before.
                rows = rows.filter(remarks__startswith=remarks_prefix)
            else:
                rows = rows.filter(completed_at__isnull=False)
            if scope is not None:
                rows = rows.filter(
                    supplementary_school_calendar_id=calendar_id, supplementary_term=term,
                )
            # Return only the newest row per material, not entire histories or
            # recording transcripts. Native NULL ordering matches the old helper.
            rows = rows.annotate(_listing_rank=Window(
                expression=RowNumber(), partition_by=[F('material_id')],
                order_by=[F('completed_at').desc(), F('created_at').desc(), F('id').desc()],
            )).filter(_listing_rank=1).only(
                'id', 'material_id', 'student_id', 'attempt_status', 'completed_at',
                'duration_seconds', 'accuracy', 'total_score',
            ).order_by()
            self._result_cache[key] = {row.material_id: row for row in rows}
        return self._result_cache[key].get(material.id)

    def submission(self, material, scope, material_ids):
        if scope is None:
            return None
        if self._submissions is None:
            rows = StoryResponseSubmission.objects.filter(
                student_id=self.student.id, material_id__in=material_ids,
                school_calendar=scope['school_calendar'], term=scope['term'],
            ).only('id', 'material_id', 'grade', 'status', 'submitted_at').order_by('pk')
            self._submissions = {}
            for row in rows:
                self._submissions.setdefault(row.material_id, row)
        return self._submissions.get(material.id)

    def practice_attempt_count(self, practice):
        enrollment_id = self._practice_enrollments.get(practice.section_id)
        attempts = practice.attempts if isinstance(practice.attempts, list) else []
        if enrollment_id is None:
            return 0
        return sum(
            attempt.get('student_id') == self.student.id
            and str(attempt.get('enrollment_id')) == str(enrollment_id)
            for attempt in attempts
        )
