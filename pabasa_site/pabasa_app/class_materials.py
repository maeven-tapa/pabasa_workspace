"""Request-local data for class listings; never caches one student's progress globally."""

from collections import defaultdict
import re
from urllib.parse import urlencode

from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.urls import reverse

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


def supplementary_launch_url(item, category):
    """Resolve the same existing reader destinations used by assessment cards."""
    if not item.get('student_access'):
        return ''
    content = item.get('content_json') or {}
    if not isinstance(content, dict):
        content = {}
    if content.get('activity_type') == 'story_response' and item.get('story_response_submitted') and not item.get('student_has_completed'):
        return ''
    material_id = str(item.get('id') or '')
    section_id = str(item.get('section_id') or '')
    if not material_id or not section_id:
        return ''
    markers = [item.get('title'), item.get('template_title'), item.get('template_type'),
               content.get('template_title'), content.get('template_lesson'),
               content.get('template_type'), content.get('activity_type')]
    normalized = {
        re.sub(r'[^a-z0-9]+', '_', str(value or '').strip().lower()).strip('_')
        for value in markers
    }
    source_type = str(item.get('source_type') or '').lower()
    activity_key = str(content.get('activity_key') or '')
    slug = str(content.get('activity_slug') or '')
    route = None
    params = {'id': material_id, 'section_id': section_id}
    if activity_key in {'word_meaning_match', 'fluency_reading'}:
        route = ('aral_template_activity_page', {'activity_slug': activity_key.replace('_', '-')})
    elif (source_type == 'template' and item.get('assessment_kind', 'regular') == 'regular'
          and ('sentence_reading' in normalized or 'sentence_reading_practice' in normalized)):
        route = ('sentence_bot_page', None)
    elif 'phrase_reading' in normalized or 'phrase_reading_practice' in normalized:
        route = ('phrase_reading_page', None)
    elif content.get('activity_type') == 'story_response':
        route = ('story_response_page', None)
    elif content.get('template_title') == "5W's Story Questions":
        route = ('story_call_page', None)
        params['id'] = str(content.get('sourceMaterialId') or '')
        if not params['id']:
            return ''
    elif 'story_reading' in normalized:
        route = ('story_reading_page', None)
        params['return_to'] = 'reading_assessment'
    elif 'clap_count_syllables' in normalized:
        route = ('clap_count_syllables_page', None)
    elif 'sound_detective' in normalized:
        route = ('sound_detective_page', None)
    elif 'letter_sound_matching' in normalized:
        route = ('letter_sound_matching_page', None)
    elif slug == 'letter-sound-correspondence':
        route = ('letter_sound_correspondence_page', None)
    elif slug == 'word-decoding':
        route = ('word_decoding_page', None)
    elif 'syllable_blending' in normalized or 'blend_the_syllables' in normalized:
        route = ('syllable_blending_page', None)
    elif 'picture_word_matching' in normalized:
        route = ('picture_word_matching_page', None)
    else:
        route_names = {'word': 'reading_word_page', 'sentence': 'reading_sentence_page',
                       'paragraph': 'reading_para_page', 'vowel': 'reading_vowel_page'}
        route_name = route_names.get(category)
        if not route_name:
            return ''
        route = (route_name, None)
        params.update(test=item.get('title') or '', content=item.get('content') or '',
                      item_type=item.get('item_type') or category,
                      language=item.get('language') or '')
    route_name, kwargs = route
    return f"{reverse(route_name, kwargs=kwargs)}?{urlencode(params)}"


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
