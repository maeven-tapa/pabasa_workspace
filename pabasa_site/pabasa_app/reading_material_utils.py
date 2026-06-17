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


def format_assigned_week_display(week):
    if week in (None, ""):
        return "Unassigned"
    return f"Week {week}"
