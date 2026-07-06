from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.mail import send_mail
from django.templatetags.static import static
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

    students_enrolled_by_section = {}
    for section in sections:
        students_enrolled_by_section[section.class_name] = len(section.get_enrolled_students(active_only=True))

    students_enrolled_by_course = {}
    for course in courses.prefetch_related("sections"):
        seen = set()
        for section in course.sections.all():
            for entry in section.get_enrolled_students(active_only=True):
                if entry.get("student_id"):
                    seen.add(entry.get("student_id"))
        students_enrolled_by_course[course.title] = len(seen)

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
        "students_added_by_section": students_enrolled_by_section,
        "students_added_by_course": students_enrolled_by_course,
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
        "classes_joined": len(sections),
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
            "Students enrolled per section:",
        ])
        lines.extend([f"- {name}: {count}" for name, count in digest["students_added_by_section"].items()] or ["- None"])
        lines.append("")
        lines.append("Students enrolled per course:")
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


def _format_percent(value):
    return f"{value}%"


def _format_delta(value):
    if value > 0:
        return f"+{value} pts"
    return f"{value} pts"


def _digest_logo_url():
    base_url = getattr(settings, "SITE_URL", "") or getattr(settings, "BASE_URL", "")
    logo_path = static("pabasa_app/images/pabasalogo.png")
    if base_url and logo_path.startswith("/"):
        return f"{base_url.rstrip('/')}{logo_path}"
    return logo_path


def _metric_card(label, value, accent="#0f766e"):
    return f"""
        <td class="stack-column" style="width: 33.333%; padding: 6px;">
            <div style="border: 1px solid #d9edf0; border-radius: 12px; padding: 14px; background: #ffffff;">
                <div style="font-size: 12px; line-height: 18px; color: #5f6f73; text-transform: uppercase;">{escape(str(label))}</div>
                <div style="font-size: 24px; line-height: 30px; color: {accent}; font-weight: 800;">{escape(str(value))}</div>
            </div>
        </td>
    """


def _list_items(items, empty_text):
    if not items:
        return f'<li style="margin: 0 0 8px;">{escape(empty_text)}</li>'
    return "".join(f'<li style="margin: 0 0 8px;">{escape(str(item))}</li>' for item in items)


def _section_card(title, body):
    return f"""
        <tr>
            <td style="padding: 8px 24px;">
                <div style="border: 1px solid #d9edf0; border-radius: 14px; background: #ffffff; padding: 18px;">
                    <h2 style="margin: 0 0 12px; font-size: 17px; line-height: 24px; color: #134e4a;">{escape(title)}</h2>
                    {body}
                </div>
            </td>
        </tr>
    """


def render_digest_html(digest):
    user = digest["user"]
    name = _student_label(user)
    start = digest["start"].date().isoformat()
    end = (digest["end"] - timedelta(days=1)).date().isoformat()
    logo_url = _digest_logo_url()

    if digest["role"] == "teacher":
        metrics = [
            ("Sections created", digest["sections_created"], "#0f766e"),
            ("Courses created", digest["courses_created"], "#155e75"),
            ("Assessments made", digest["assessments_created"], "#7c3aed"),
            ("Attempts received", digest["submissions_received"], "#0f766e"),
            ("Completed by students", digest["assessments_completed"], "#155e75"),
            ("Class average", _format_percent(digest["average_class_reading_performance"]), "#b45309"),
        ]
        sections_rows = "".join(
            f'<tr><td style="padding: 8px 0; color: #20393d;">{escape(section)}</td><td align="right" style="padding: 8px 0; font-weight: 700; color: #0f766e;">{count}</td></tr>'
            for section, count in digest["students_added_by_section"].items()
        ) or '<tr><td style="padding: 8px 0;">No active section enrollments yet.</td></tr>'
        courses_rows = "".join(
            f'<tr><td style="padding: 8px 0; color: #20393d;">{escape(course)}</td><td align="right" style="padding: 8px 0; font-weight: 700; color: #155e75;">{count}</td></tr>'
            for course, count in digest["students_added_by_course"].items()
        ) or '<tr><td style="padding: 8px 0;">No active course enrollments yet.</td></tr>'
        improved = [
            f"{row['student']}: +{row['improvement']} pts, {row['average']}% average"
            for row in digest["most_improved"]
        ]
        support = [
            f"{row['student']}: {row['low_score_average']}% low-score average, {row['incomplete_assessments']} incomplete"
            for row in digest["needs_support"]
        ]
        class_perf = [
            f"{class_name}: {score}%"
            for class_name, score in digest["class_performance"].items()
        ]
        detail_cards = [
            _section_card("Students Enrolled Per Section", f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{sections_rows}</table>'),
            _section_card("Students Enrolled Per Course", f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{courses_rows}</table>'),
            _section_card("Most Improved", f'<ul style="padding-left: 20px; margin: 0; color: #20393d;">{_list_items(improved, "No comparable score data yet.")}</ul>'),
            _section_card("Needs Support", f'<ul style="padding-left: 20px; margin: 0; color: #20393d;">{_list_items(support, "No low-score or incomplete-assessment flags this week.")}</ul>'),
            _section_card("Class Reading Performance", f'<ul style="padding-left: 20px; margin: 0; color: #20393d;">{_list_items(class_perf, "No completed scores this week.")}</ul>'),
        ]
    else:
        best = digest["best_assessment"]
        best_label = f"{best['title']} ({best['score']}%)" if best else "No completed assessment this week"
        metrics = [
            ("Classes joined", digest["classes_joined"], "#0f766e"),
            ("Assessments done", digest["assessments_completed"], "#155e75"),
            ("Practice sessions", digest["practice_sessions_completed"], "#7c3aed"),
            ("Average score", _format_percent(digest["average_reading_score"]), "#b45309"),
            ("Reading level", digest["reading_level"], "#0f766e"),
            ("Weekly progress", _format_delta(digest["progress_delta"]), "#155e75"),
        ]
        weak_areas = digest["areas_needing_improvement"] or ["Keep building consistency"]
        detail_cards = [
            _section_card("Best Assessment", f'<p style="margin: 0; color: #20393d; font-weight: 700;">{escape(best_label)}</p>'),
            _section_card("Areas To Practice", f'<ul style="padding-left: 20px; margin: 0; color: #20393d;">{_list_items(weak_areas, "Keep building consistency")}</ul>'),
            _section_card("Pending Assessments", f'<ul style="padding-left: 20px; margin: 0; color: #20393d;">{_list_items(digest["pending_assessments"], "None")}</ul>'),
            _section_card("Achievement", f'<p style="margin: 0 0 8px; color: #0f766e; font-size: 18px; font-weight: 800;">&#127941; {escape(digest["achievement_badge"])}</p><p style="margin: 0; color: #20393d;">{escape(digest["encouraging_message"])}</p>'),
        ]

    metric_rows = []
    for index in range(0, len(metrics), 3):
        cards = "".join(_metric_card(label, value, accent) for label, value, accent in metrics[index:index + 3])
        metric_rows.append(f'<tr>{cards}</tr>')

    return f"""<!doctype html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        @media screen and (max-width: 620px) {{
            .email-container {{ width: 100% !important; }}
            .stack-column {{ display: block !important; width: 100% !important; box-sizing: border-box !important; }}
            .mobile-padding {{ padding-left: 16px !important; padding-right: 16px !important; }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background: #eef7f8; font-family: Arial, Helvetica, sans-serif; color: #20393d;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #eef7f8;">
        <tr>
            <td align="center" style="padding: 24px 12px;">
                <table role="presentation" class="email-container" width="640" cellspacing="0" cellpadding="0" style="width: 640px; max-width: 640px; background: #f8fcfc; border-radius: 18px; overflow: hidden;">
                    <tr>
                        <td class="mobile-padding" style="padding: 24px; background: #0f766e;">
                            <img src="{escape(logo_url)}" alt="PABASA" width="72" style="display: block; border: 0; margin-bottom: 14px;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; line-height: 34px;">Your Weekly PABASA Digest</h1>
                            <p style="margin: 8px 0 0; color: #dff7f4; font-size: 14px; line-height: 22px;">{escape(start)} to {escape(end)}</p>
                        </td>
                    </tr>
                    <tr>
                        <td class="mobile-padding" style="padding: 24px 24px 10px;">
                            <p style="margin: 0; font-size: 16px; line-height: 25px;">Hello {escape(name)},</p>
                            <p style="margin: 8px 0 0; font-size: 15px; line-height: 24px; color: #486166;">Here is a friendly summary of this week's reading activity.</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 18px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                {''.join(metric_rows)}
                            </table>
                        </td>
                    </tr>
                    {''.join(detail_cards)}
                    <tr>
                        <td align="center" style="padding: 22px 24px 28px; color: #60777b; font-size: 12px; line-height: 20px;">
                            <strong style="color: #134e4a;">PABASA</strong><br>
                            Copyright &copy; {timezone.now().year} PABASA. This email was generated automatically from your account activity.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


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
    html_body = render_digest_html(digest)
    subject = "Your Weekly PABASA Digest"
    if not dry_run:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
            html_message=html_body,
        )
        prefs["weekly_digest"] = {
            "last_sent_at": timezone.now().isoformat(),
            "last_window_start": start.isoformat(),
            "last_window_end": end.isoformat(),
            "last_window_key": window_key,
        }
        user.preference = prefs
        user.save(update_fields=["preference", "updated_at"])
    return {"sent": not dry_run, "dry_run": dry_run, "subject": subject, "body": body, "html_body": html_body, "digest": digest}


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
