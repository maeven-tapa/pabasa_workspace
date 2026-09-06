"""One application-wide clock, with an admin-only debug override.

The override stores a reference time plus the real time it was set, so simulated
time continues to advance normally and is shared by every web worker.
"""
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.utils import timezone


_real_now = timezone.now
_CACHE_KEY = 'pabasa:system-time-override'
_CACHE_MISSING = object()


def real_now():
    """The host clock, used only to anchor an override change."""
    return _real_now()


def now():
    """Return the real clock unless the persisted debug clock is enabled."""
    real_now = _real_now()
    state = cache.get(_CACHE_KEY, _CACHE_MISSING)
    if state is _CACHE_MISSING:
        try:
            from .models import SystemTimeOverride
            override = SystemTimeOverride.objects.filter(pk=1, enabled=True).only(
                'reference_time', 'configured_at'
            ).first()
            state = (override.reference_time, override.configured_at) if override else False
        except (OperationalError, ProgrammingError):
            # The table is unavailable during initial migration/startup.
            state = False
        # Keep worker-wide database work bounded while allowing an admin change to
        # reach every worker almost immediately.
        cache.set(_CACHE_KEY, state, timeout=1)

    if not state:
        return real_now
    reference_time, configured_at = state
    return reference_time + (real_now - configured_at)


def today():
    return timezone.localtime(now()).date()


def invalidate_override_cache():
    cache.delete(_CACHE_KEY)


def install_timezone_override():
    """Route Django's timezone-aware clock through this app-wide clock."""
    if timezone.now is not now:
        timezone.now = now
