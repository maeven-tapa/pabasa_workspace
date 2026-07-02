from collections import defaultdict
from datetime import datetime
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Assessment, Course, Practice, Section, User


def _settings_for_user(user):
    defaults = {
        "push_enabled": True,
        "email_notifications": True,
        "weekly_digest_enabled": False,
        "new_materials": True,
        "reading_reminders": getattr(user, "role", "") == "student",
        "progress_updates": True,
    }
    prefs = getattr(user, "preference", None) or {}
    if not isinstance(prefs, dict):
        prefs = {}
    saved = prefs.get("notification_settings") or {}
    if not isinstance(saved, dict):
        saved = {}
    return {**defaults, **saved}


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _in_window(value, start, end):
    dt = _parse_dt(value)
    return bool(dt and start <= dt < end)


def _score_from_attempt(attempt):
    for key in ("total_score", "accuracy", "fluency_score", "pronunciation_score", "time_score"):
        try:
            if attempt.get(key) not in (None, ""):
                return float(attempt.get(key))
        except (TypeError, ValueError):
            continue
    values = []
    for key in ("accuracy", "fluency_score", "pronunciation_score", "time_score"):
        try:
            if attempt.get(key) not in (None, ""):
                values.append(float(attempt.get(key)))
        except (TypeError, ValueError):
            pass
    return round(sum(values) / len(values), 2) if values else None


def _student_ids_for_section(section, active_only=True):
    return [
        _as_int(entry.get("student_id"))
        for entry in section.get_enrolled_students(active_only=active_only)
        if _as_int(entry.get("student_id")) is not None
    ]


def _student_label(user):
    return f"{user.first_name} {user.last_name}".strip() or user.custom_id


def _average(values):
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 1) if clean else 0


def _attempt_time(attempt):
    return attempt.get("completed_at") or attempt.get("updated_at") or attempt.get("started_at")


def _completed_attempts_for_student(assessment, student):
    return [
        attempt for attempt in assessment.get_attempts(student)
        if isinstance(attempt, dict) and attempt.get("status") == "completed"
    ]


def _teacher_sections(user):
    return Section.objects.filter(teacher=user, is_active=True)


def build_teacher_weekly_digest(user, start, end):
    sections = list(_teacher_sections(user))
    section_ids = [section.id for section in sections]
    section_student_ids = set()
    for section in sections:
        section_student_ids.update(_student_ids_for_section(section))

    courses = Course.objects.filter(teacher=user, is_active=True)
    courses_created = courses.filter(created_at__gte=start, created_at__lt=end).count()
    assessments = Assessment.objects.filter(teacher=user, is_active=True)
    assessments_created = assessments.filter(created_at__gte=start, created_at__lt=end).count()

    students_added_by_section = {}
    for section in sections:
        count = 0
        for entry in section.get_enrolled_students(active_only=False):
            if _in_window(entry.get("joined_at"), start, end):
                count += 1
        students_added_by_section[section.class_name] = count

    students_added_by_course = {}
    for course in courses.prefetch_related("sections"):
        seen = set()
        for section in course.sections.all():
            for entry in section.get_enrolled_students(active_only=False):
                if _in_window(entry.get("joined_at"), start, end) and entry.get("student_id"):
                    seen.add(entry.get("student_id"))
        students_added_by_course[course.title] = len(seen)

    submissions = 0
    completed = 0
    current_scores = defaultdict(list)
    previous_scores = defaultdict(list)
    incomplete_by_student = defaultdict(int)
    low_scores = defaultdict(list)
    class_scores = defaultdict(list)
    previous_start = start - (end - start)

    students_by_id = {
        student.id: student
        for student in User.objects.filter(id__in=section_student_ids, role="student", is_archived=False)
    }

    for assessment in assessments:
        attempts = assessment.get_attempts()
        if not attempts:
            continue
        completed_student_ids = set()
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            student_id = _as_int(attempt.get("student_id"))
            if student_id not in section_student_ids:
                continue
            attempt_dt = _parse_dt(_attempt_time(attempt))
            score = _score_from_attempt(attempt)
            if attempt_dt and start <= attempt_dt < end:
                submissions += 1
                if attempt.get("status") == "completed":
                    completed += 1
                    completed_student_ids.add(student_id)
                    if score is not None:
                        current_scores[student_id].append(score)
                        if score < 75:
                            low_scores[student_id].append(score)
                        class_label = assessment.section.class_name if assessment.section else "Unassigned"
                        class_scores[class_label].append(score)
            elif attempt_dt and previous_start <= attempt_dt < start and score is not None:
                previous_scores[student_id].append(score)
        if assessment.section_id in section_ids:
            for student_id in _student_ids_for_section(assessment.section):
                if student_id not in completed_student_ids:
                    incomplete_by_student[student_id] += 1

    improvement_rows = []
    for student_id, scores in current_scores.items():
        current_avg = _average(scores)
        previous_avg = _average(previous_scores.get(student_id, []))
        if previous_avg:
            improvement_rows.append((student_id, round(current_avg - previous_avg, 1), current_avg))
    improvement_rows.sort(key=lambda row: row[1], reverse=True)

    support_rows = []
    for student_id in set(low_scores.keys()) | set(incomplete_by_student.keys()):
        low_avg = _average(low_scores.get(student_id, []))
        support_rows.append((student_id, low_avg, incomplete_by_student.get(student_id, 0)))
    support_rows.sort(key=lambda row: (row[1] or 101, -row[2]))

    class_performance = {
        class_name: _average(scores)
        for class_name, scores in class_scores.items()
    }

    return {
        "role": "teacher",
        "user": user,
        "start": start,
        "end": end,
        "sections_created": Section.objects.filter(teacher=user, created_at__gte=start, created_at__lt=end).count(),
        "courses_created": courses_created,
        "students_added_by_section": students_added_by_section,
        "students_added_by_course": students_added_by_course,
        "assessments_created": assessments_created,
        "submissions_received": submissions,
        "assessments_completed": completed,
        "most_improved": [
            {
                "student": _student_label(students_by_id.get(student_id)) if students_by_id.get(student_id) else str(student_id),
                "improvement": improvement,
                "average": current_avg,
            }
            for student_id, improvement, current_avg in improvement_rows[:5]
        ],
        "needs_support": [
            {
                "student": _student_label(students_by_id.get(student_id)) if students_by_id.get(student_id) else str(student_id),
                "low_score_average": low_avg,
                "incomplete_assessments": incomplete_count,
            }
            for student_id, low_avg, incomplete_count in support_rows[:5]
        ],
        "class_performance": class_performance,
        "average_class_reading_performance": _average(class_performance.values()),
    }


def _student_sections(user):
    return [
        section for section in Section.objects.filter(is_active=True)
        if section.has_student(user, active_only=True)
    ]


def build_student_weekly_digest(user, start, end):
    sections = _student_sections(user)
    previous_start = start - (end - start)
    joined_count = 0
    for section in sections:
        for entry in section.get_enrolled_students(active_only=True):
            if str(entry.get("student_id")) == str(user.id) and _in_window(entry.get("joined_at"), start, end):
                joined_count += 1

    assessments = Assessment.objects.filter(section__in=sections, is_active=True)
    scores = []
    previous_scores = []
    best = None
    completed_count = 0
    pending = []
    weak_areas = defaultdict(list)

    for assessment in assessments:
        completed_current = False
        for attempt in assessment.get_attempts(user):
            if not isinstance(attempt, dict):
                continue
            attempt_dt = _parse_dt(_attempt_time(attempt))
            score = _score_from_attempt(attempt)
            if attempt.get("status") == "completed" and attempt_dt and start <= attempt_dt < end:
                completed_count += 1
                completed_current = True
                if score is not None:
                    scores.append(score)
                    if best is None or score > best["score"]:
                        best = {"title": assessment.title, "score": score}
                for key, label in (
                    ("pronunciation_score", "pronunciation"),
                    ("fluency_score", "fluency"),
                    ("accuracy", "accuracy"),
                ):
                    try:
                        value = float(attempt.get(key))
                    except (TypeError, ValueError):
                        continue
                    if value < 75:
                        weak_areas[label].append(value)
            elif attempt.get("status") == "completed" and attempt_dt and previous_start <= attempt_dt < start and score is not None:
                previous_scores.append(score)
        if not completed_current and not assessment.has_student_completed(user):
            pending.append(assessment.title)

    practice_completed = 0
    for practice in Practice.objects.filter(is_active=True):
        for attempt in practice.get_attempts(user):
            if (
                isinstance(attempt, dict)
                and attempt.get("status") == "completed"
                and _in_window(_attempt_time(attempt), start, end)
            ):
                practice_completed += 1

    current_avg = _average(scores)
    previous_avg = _average(previous_scores)
    progress_delta = round(current_avg - previous_avg, 1) if current_avg and previous_avg else 0
    badge = "Steady Reader"
    if progress_delta > 0:
        badge = "Most Improved"
    elif completed_count >= 3:
        badge = "Assessment Finisher"
    elif practice_completed >= 3:
        badge = "Practice Champion"

    return {
        "role": "student",
        "user": user,
        "start": start,
        "end": end,
        "classes_joined": joined_count,
        "assessments_completed": completed_count,
        "practice_sessions_completed": practice_completed,
        "average_reading_score": current_avg,
        "reading_level": user.reading_level or "Not set",
        "progress_delta": progress_delta,
        "best_assessment": best,
        "areas_needing_improvement": sorted(weak_areas.keys()),
        "pending_assessments": pending[:10],
        "encouraging_message": "Keep practicing. Every completed reading helps build confidence.",
        "achievement_badge": badge,
    }


def render_digest_text(digest):
    user = digest["user"]
    name = _student_label(user)
    start = digest["start"].date().isoformat()
    end = (digest["end"] - timedelta(days=1)).date().isoformat()
    lines = [f"Hello {name},", "", f"Here is your PABASA weekly digest for {start} to {end}.", ""]

    if digest["role"] == "teacher":
        lines.extend([
            f"Sections made: {digest['sections_created']}",
            f"Courses made: {digest['courses_created']}",
            f"Assessments created: {digest['assessments_created']}",
            f"Student submissions/attempts received: {digest['submissions_received']}",
            f"Assessments completed by students: {digest['assessments_completed']}",
            f"Average class reading performance: {digest['average_class_reading_performance']}%",
            "",
            "Students added per section:",
        ])
        lines.extend([f"- {name}: {count}" for name, count in digest["students_added_by_section"].items()] or ["- None"])
        lines.append("")
        lines.append("Students added per course:")
        lines.extend([f"- {name}: {count}" for name, count in digest["students_added_by_course"].items()] or ["- None"])
        lines.append("")
        lines.append("Students with the most improvement:")
        lines.extend([f"- {row['student']}: +{row['improvement']} pts, average {row['average']}%" for row in digest["most_improved"]] or ["- No comparable score data yet."])
        lines.append("")
        lines.append("Students who may need additional support:")
        lines.extend([f"- {row['student']}: low score average {row['low_score_average']}%, incomplete assessments {row['incomplete_assessments']}" for row in digest["needs_support"]] or ["- No support flags this week."])
        lines.append("")
        lines.append("Average class reading performance:")
        lines.extend([f"- {name}: {score}%" for name, score in digest["class_performance"].items()] or ["- No completed scores this week."])
    else:
        best = digest["best_assessment"]
        lines.extend([
            f"Sections/classes joined: {digest['classes_joined']}",
            f"Assessments completed: {digest['assessments_completed']}",
            f"Practice sessions completed: {digest['practice_sessions_completed']}",
            f"Average reading score: {digest['average_reading_score']}%",
            f"Reading level: {digest['reading_level']}",
            f"Progress compared to previous week: {digest['progress_delta']} pts",
            f"Best-performing assessment: {best['title']} ({best['score']}%)" if best else "Best-performing assessment: No completed assessment this week",
            f"Areas needing improvement: {', '.join(digest['areas_needing_improvement']) if digest['areas_needing_improvement'] else 'Keep building consistency'}",
            "Pending assessments assigned by the teacher:",
        ])
        lines.extend([f"- {title}" for title in digest["pending_assessments"]] or ["- None"])
        lines.extend([
            "",
            f"Achievement badge: {digest['achievement_badge']}",
            digest["encouraging_message"],
        ])

    lines.extend(["", "Thank you,", "The PABASA Team"])
    return "\n".join(lines)


def _window_key(start, end):
    return f"{start.isoformat()}::{end.isoformat()}"


def send_weekly_digest(user, start, end, dry_run=False, force=False):
    settings_dict = _settings_for_user(user)
    if settings_dict.get("weekly_digest_enabled") is not True:
        return {"sent": False, "skipped": "weekly_digest_disabled"}
    if not getattr(user, "email", ""):
        return {"sent": False, "skipped": "missing_email"}

    prefs = getattr(user, "preference", None) or {}
    if not isinstance(prefs, dict):
        prefs = {}
    digest_meta = prefs.get("weekly_digest") or {}
    window_key = _window_key(start, end)
    if not force and digest_meta.get("last_window_key") == window_key:
        return {"sent": False, "skipped": "duplicate_window"}

    if user.role == "teacher":
        digest = build_teacher_weekly_digest(user, start, end)
    elif user.role == "student":
        digest = build_student_weekly_digest(user, start, end)
    else:
        return {"sent": False, "skipped": "unsupported_role"}

    body = render_digest_text(digest)
    subject = "Your Weekly PABASA Digest"
    if not dry_run:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        prefs["weekly_digest"] = {
            "last_sent_at": timezone.now().isoformat(),
            "last_window_start": start.isoformat(),
            "last_window_end": end.isoformat(),
            "last_window_key": window_key,
        }
        user.preference = prefs
        user.save(update_fields=["preference", "updated_at"])
    return {"sent": not dry_run, "dry_run": dry_run, "subject": subject, "body": body, "digest": digest}


def send_weekly_digests(start=None, end=None, user_id=None, dry_run=False, force=False):
    end = end or timezone.now()
    start = start or (end - timedelta(days=7))
    users = User.objects.filter(role__in=["teacher", "student"], is_archived=False)
    if user_id:
        users = users.filter(id=user_id)

    results = []
    for user in users:
        result = send_weekly_digest(user, start, end, dry_run=dry_run, force=force)
        results.append({"user_id": user.id, "email": user.email, **result})
    return results
