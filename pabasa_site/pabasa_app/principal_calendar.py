"""Read-only Principal access to the published, shared school calendar."""
from datetime import date

from django.http import JsonResponse
from django.shortcuts import render

from .models import SchoolCalendar
from .principal_reporting import PrincipalScope


def visible_calendar_events(scope, user, *, source=None):
    """One shared Admin calendar feed, including published derived ARAL blocks."""
    from .views import _calendar_events_for_audience
    events = _calendar_events_for_audience(scope.calendar, user, published_only=True) if source is None else source
    result = []
    seen = set()
    for event in events:
        if scope.term and event['term'] != scope.term:
            continue
        if event['id'] in seen:
            continue
        seen.add(event['id'])
        result.append({**event, 'editable': False})
    return result


def upcoming_calendar_events(scope, user, *, today=None):
    from .system_clock import now
    from django.utils import timezone
    today = today or timezone.localdate(now())
    return [event for event in visible_calendar_events(scope, user)
            if (event.get('end_date') or event['start']) >= today.isoformat()][:5]


def calendar_response(request, user, context):
    if request.method not in {'GET', 'HEAD'}:
        return JsonResponse({'success': False, 'error': 'Principal calendar is read-only. Contact an Administrator to manage events.'}, status=403)
    # School leadership calendar filters expose the three supported academic
    # terms. Older calendars may contain Term 4 rows; keep those records intact
    # and show them under All terms rather than exposing a dead filter.
    params = request.GET.copy()
    selected_term = params.get('term', '')
    params.pop('term', None)
    term_filter = selected_term if selected_term in {'1', '2', '3'} else ''
    scope = PrincipalScope.resolve(user, params)
    scope.term = int(term_filter) if term_filter else None
    school = user.school_record if user.role == 'principal' else None

    if request.method in {'GET', 'HEAD'}:
        from .views import _calendar_events_for_audience
        from .system_clock import today
        current = today()
        source = _calendar_events_for_audience(scope.calendar, user, published_only=True)
        data = visible_calendar_events(scope, user, source=source)
        academic = [event for event in source if event.get('scope') == 'global' and event['event_type'] in
                    {'school_opening', 'school_closing', 'start_of_classes', 'end_of_classes'}]
        blocks = {}
        for event in academic:
            field = {'school_opening':'opening', 'school_closing':'closing'}.get(event['event_type'])
            if field:
                blocks.setdefault(str(event['term']), {}).setdefault(field, event['start'])
        config = {'schoolYear': scope.calendar.school_year if scope.calendar else '', 'today': current.isoformat(),
                  'rangeEvents': [{key:event[key] for key in ('event_type','start','end_date')} for event in academic],
                  'termBlocks': blocks}
        view = request.GET.get('view', 'month')
        view = view if view in {'month', 'week', 'year'} else 'month'
        if request.GET.get('format') == 'json' or request.headers.get('Accept', '').startswith('application/json'):
            response = JsonResponse({'events': data, 'calendar_id': scope.calendar.pk if scope.calendar else None,
                                     'term': scope.term, 'calendar': config})
            response['Cache-Control'] = 'private, no-store'
            return response
        focus = current
        window = scope.term_windows.get(scope.term) if scope.term else None
        if window and not window[0] <= current <= window[1]:
            focus = window[0]
        elif scope.start and scope.end and not scope.start <= current <= scope.end:
            focus = scope.start
        elif scope.term and data and not any(event['start'] <= current.isoformat() <= (event.get('end_date') or event['start']) for event in data):
            focus = date.fromisoformat(data[0]['start'])
        context.update({'events': data, 'school': school, 'calendar_start': scope.start.isoformat() if scope.start else '',
                        'calendar_config': config, 'calendar_view': view,
                        'calendar_initial_date': focus.isoformat(),
                        'calendar_term_options': tuple((value, label) for value, label in SchoolCalendar.TERM_CHOICES
                                                       if str(value) in {'1', '2', '3'}),
                        'can_manage_events': False,
                        'school_calendars': scope.calendars, 'scope_calendar': scope.calendar, 'scope_term': str(scope.term or ''),
                        'student_calendar_school_year': scope.calendar.school_year if scope.calendar else 'Not configured',
                        'student_calendar_current_term': f'Term {scope.calendar.current_term}' if scope.calendar else 'Not configured'})
        return render(request, 'pabasa_app/principal_calendar.html', context)
