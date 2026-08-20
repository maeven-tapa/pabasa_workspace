import re


def parse_assigned_week(raw_value):
    """
    Parse assigned week from API/form input.
    Returns (week_int_or_none, error_message_or_none).
    """
    if raw_value is None:
        return None, None

    if isinstance(raw_value, bool):
        return None, "Assigned Week must be a number between 1 and 99."

    if isinstance(raw_value, int):
        week = raw_value
    elif isinstance(raw_value, float):
        if not raw_value.is_integer():
            return None, "Assigned Week must be a whole number between 1 and 99."
        week = int(raw_value)
    else:
        value = str(raw_value).strip()
        if not value or value.lower() in {"unassigned", "none", "null"}:
            return None, None
        match = re.match(r"^(?:week\s*)?(\d{1,2})$", value, re.IGNORECASE)
        if not match:
            return None, "Assigned Week must be a number between 1 and 99."
        week = int(match.group(1))

    if week < 1 or week > 99:
        return None, "Assigned Week must be between 1 and 99."
    return week, None


def parse_assigned_weeks(raw_value, minimum=1, maximum=10):
    """
    Parse one or more assigned weeks from API/form input.
    Returns (weeks_list_or_none, error_message_or_none).
    """
    if raw_value in (None, "", []):
        return [], None

    if isinstance(raw_value, (list, tuple, set)):
        raw_values = list(raw_value)
    else:
        raw_values = [segment.strip() for segment in str(raw_value).split(',') if segment.strip()]

    weeks = []
    for item in raw_values:
        if isinstance(item, bool):
            return None, f"Assigned Weeks must be between {minimum} and {maximum}."
        if isinstance(item, int):
            week = item
        elif isinstance(item, float):
            if not item.is_integer():
                return None, f"Assigned Weeks must be whole numbers between {minimum} and {maximum}."
            week = int(item)
        else:
            match = re.match(r"^(?:week\s*)?(\d{1,2})$", str(item).strip(), re.IGNORECASE)
            if not match:
                return None, f"Assigned Weeks must be between {minimum} and {maximum}."
            week = int(match.group(1))
        if week < minimum or week > maximum:
            return None, f"Assigned Weeks must be between {minimum} and {maximum}."
        weeks.append(week)

    unique_weeks = sorted(set(weeks))
    return unique_weeks, None


def format_assigned_week_display(week):
    if week in (None, ""):
        return "Unassigned"
    return f"Week {week}"


def format_assigned_weeks_display(weeks):
    if not weeks:
        return "Unassigned"
    normalized = []
    for week in weeks:
        try:
            normalized.append(int(week))
        except (TypeError, ValueError):
            continue
    normalized = sorted({week for week in normalized if 1 <= week <= 99})
    if not normalized:
        return "Unassigned"
    if len(normalized) == 1:
        return f"Week {normalized[0]}"
    return ", ".join(f"Week {week}" for week in normalized)
