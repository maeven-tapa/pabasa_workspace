"""Presentation of the existing live-session participation summary.

No assessment writes, completion decisions, recipient selection or scheduling.
The caller supplies the same completed/missed lists used by the original email.
"""
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .email_branding import email_logo_url


ASSET_ROOT = Path(__file__).resolve().parent / 'static' / 'pabasa_app' / 'images'
PHASE_LABELS = {'pretest': 'BoSY Pre-Assessment', 'midtest': 'Midline Assessment',
                'posttest': 'EoSY Post-Assessment'}
PHASE_KEYS = {'bosy_crla_pretest': 'pretest', 'midline_crla_midtest': 'midtest',
              'eosy_crla_posttest': 'posttest'}
STATUS_LABELS = {'waiting': 'Waiting', 'batch_loaded': 'Batch loaded', 'countdown': 'Countdown',
                 'started': 'Started', 'paused': 'Paused', 'ended': 'Ended', 'cancelled': 'Cancelled'}


@lru_cache(maxsize=1)
def _logo_bytes():
    path = ASSET_ROOT / 'pabasa_logo.png'
    try:
        return path.read_bytes()
    except OSError:
        return None


def _name(person):
    return ' '.join(str(getattr(person, field, '') or '').strip()
                    for field in ('first_name', 'last_name')).strip()


def _student(person):
    identifier = str(getattr(person, 'custom_id', '') or '').strip()
    return {'name': _name(person) or identifier or 'Learner', 'pabasa_id': identifier}


def _duration(session):
    # start_at is the scheduled reading start of the CURRENT batch, not a
    # trustworthy whole-session start for a multi-batch session. Do not invent
    # a whole-session duration from created_at, per-student timers or that value.
    batches = getattr(session, 'batch_assignments', {}) or {}
    if not isinstance(batches, dict):
        return None
    try:
        batch_numbers = {int(value) for value in batches.values()}
    except (TypeError, ValueError):
        return None
    if ((getattr(session, 'total_batches', 0) or 0) > 1
            or (getattr(session, 'current_batch', 1) or 1) > 1
            or len(batch_numbers) > 1 or any(number < 1 for number in batch_numbers)):
        return None
    start, end = getattr(session, 'start_at', None), getattr(session, 'ends_at', None)
    if not start or not end or getattr(session, 'status', '') not in {'ended', 'cancelled'}:
        return None
    if not timezone.is_aware(start) or not timezone.is_aware(end):
        return None
    seconds = int((end - start).total_seconds())
    if seconds < 0:
        return None
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    for count, label in ((hours, 'hour'), (minutes, 'minute'), (seconds, 'second')):
        if count:
            parts.append(f'{count} {label}{"s" if count != 1 else ""}')
    return ' '.join(parts) or '0 seconds'


def summary_context(session, completed_students, missed_students, ended_at):
    """Read authoritative session relations; do not change or reinterpret them."""
    teacher = getattr(session, 'teacher', None)
    section = getattr(session, 'section', None)
    course = getattr(session, 'course', None)
    material = session.material
    school = (getattr(section, 'school', None) or getattr(course, 'school', None)
              or getattr(teacher, 'school_record', None))
    assessment = getattr(material, 'assessment', None)
    phase = ''
    for source in (material, assessment):
        if source:
            phase = (getattr(source, 'system_assessment_phase', '') or
                     PHASE_KEYS.get(getattr(source, 'system_assessment_key', ''), ''))
            if phase in PHASE_LABELS:
                break
    is_crla = getattr(material, 'assessment_kind', '') == 'crla'
    item_labels = {'word': 'Word assessment', 'vowel': 'Vowel assessment',
                   'sentence': 'Sentence assessment', 'paragraph': 'Reading assessment'}
    assessment_type = (f'CRLA / {PHASE_LABELS[phase]}' if phase in PHASE_LABELS else
                       'CRLA Assessment' if is_crla else
                       item_labels.get(getattr(material, 'item_type', ''), 'Reading assessment'))
    selected = len(session.student_ids or [])
    completed, missed = len(completed_students), len(missed_students)
    rate = round(completed / selected * 100, 1) if selected else 0
    # The visual stays within its track; the displayed ratio is never clamped.
    bar_rate = min(100, max(0, rate))
    duration = _duration(session)
    date = timezone.localtime(ended_at) if ended_at and timezone.is_aware(ended_at) else None
    return {
        'school_name': str(getattr(school, 'name', '') or ''),
        'assessment_title': material.title or 'Reading Activity',
        'assessment_type': assessment_type,
        'assessment_datetime': date.strftime('%B %d, %Y %I:%M %p') if date else '',
        'grade_level': str(getattr(section, 'grade_level', '') or ''),
        'section_name': str(getattr(section, 'section', '') or getattr(section, 'class_name', '') or ''),
        'teacher_name': _name(teacher) if teacher else '',
        'selected_count': selected, 'completed_count': completed, 'missed_count': missed,
        'completion_rate': f'{rate:g}', 'bar_rate': f'{bar_rate:g}',
        'bar_remaining': f'{100 - bar_rate:g}',
        'completed_students': [_student(person) for person in completed_students],
        'missed_students': [_student(person) for person in missed_students],
        'unavailable_records': max(0, selected - completed - missed),
        'session_duration': duration,
        'session_status': STATUS_LABELS.get(getattr(session, 'status', '')),
        'logo_url': 'cid:pabasa-live-summary-logo' if _logo_bytes() else email_logo_url(),
    }


def render_summary_email(session, completed_students, missed_students, ended_at):
    return render_to_string('pabasa_app/emails/live_assessment_summary.html',
        summary_context(session, completed_students, missed_students, ended_at))


class _SummaryEmail(EmailMultiAlternatives):
    """Keep text/HTML alternatives and embed the existing logo as related MIME.

    Django 6 returns a standard EmailMessage. Add related content to its HTML
    part through the standard library, without deprecated MIME subtype hacks.
    """
    def message(self, **kwargs):
        message = super().message(**kwargs)
        html = message.get_body(preferencelist=('html',))
        logo = _logo_bytes()
        if html is not None and logo:
            html.add_related(logo, maintype='image', subtype='png',
                cid='<pabasa-live-summary-logo>', filename='pabasa-logo.png', disposition='inline')
        return message


def send_summary_email(session, completed_students, missed_students, ended_at, text_message):
    """Use the same configured Django backend, sender, recipient and silent mode."""
    email = _SummaryEmail(
        f"Live Assessment Summary: {session.material.title or 'Reading Activity'}",
        text_message, settings.DEFAULT_FROM_EMAIL, [session.teacher.email])
    email.attach_alternative(render_summary_email(session, completed_students, missed_students, ended_at),
                             'text/html')
    return email.send(fail_silently=True)
