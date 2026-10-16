"""Capture saved milestones at completion, including between dashboard visits."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .achievements import (
    _award, _local_date, _streaks, assessment_summary, prescribed_catalog,
    prescribed_summary, record_learning_dates,
)
from .models import (
    Assessment, PrescribedReadingAttempt, StudentActivityProgress,
    StudentActivityRecordingSubmission, StudentLearningDay,
)
from .system_clock import now as system_now


def _reading_day(student_id, value):
    date = _local_date(value)
    if not date:
        return
    record_learning_dates(student_id, {date})
    days = StudentLearningDay.objects.filter(student_id=student_id).values_list('date', flat=True)
    if _streaks(days, _local_date(system_now()))[1] >= 7:
        _award(student_id, {'reading-streak'})


@receiver(pre_save, sender=StudentActivityProgress)
def remember_completion(sender, instance, raw=False, **kwargs):
    if raw or not instance.activity_completed:
        return
    instance._achievement_was_complete = bool(instance.pk and sender.objects.filter(
        pk=instance.pk,
    ).values_list('activity_completed', flat=True).first())


@receiver(post_save, sender=StudentActivityProgress)
def prescribed_completed(sender, instance, raw=False, **kwargs):
    if raw or not instance.activity_completed or instance.student.role != 'student':
        return
    if getattr(instance, '_achievement_was_complete', False):
        return
    summary = prescribed_summary(instance.student, instance.school_calendar, instance.term)
    _award(instance.student_id, summary['earned'])
    activity = prescribed_catalog().get(instance.activity_key)
    # Recording dates come from the student's submission, not the later review.
    if (activity and activity.get('interaction') != 'teacher_reading_checklist'
            and instance.activity_key != 'lesson-1-gawain-1'
            and not StudentActivityRecordingSubmission.objects.filter(
                student_id=instance.student_id, activity_key=instance.activity_key,
            ).exists()):
        _reading_day(instance.student_id, system_now())


@receiver(post_save, sender=Assessment)
def assessment_completed(sender, instance, raw=False, **kwargs):
    if raw or not instance.student_id or instance.attempt_status != 'completed' or not instance.completed_at:
        return
    if instance.student.role != 'student':
        return
    _count, dates, keys = assessment_summary(instance.student)
    _award(instance.student_id, keys)
    record_learning_dates(instance.student_id, dates)
    if dates:
        _reading_day(instance.student_id, max(dates))


@receiver(post_save, sender=PrescribedReadingAttempt)
def reading_saved(sender, instance, created=False, raw=False, **kwargs):
    if not raw and created and instance.audio_file and instance.student.role == 'student':
        _reading_day(instance.student_id, instance.created_at)


@receiver(post_save, sender=StudentActivityRecordingSubmission)
def recording_submitted(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == 'submitted' and instance.audio_file and instance.student.role == 'student':
        # Preserve the older reading evidence even if its replaceable recording
        # predates the achievement feature and has not yet been backfilled.
        previous = getattr(instance, '_previous_submitted_at', None)
        if previous:
            record_learning_dates(instance.student_id, {_local_date(previous)})
        _reading_day(instance.student_id, instance.submitted_at)
