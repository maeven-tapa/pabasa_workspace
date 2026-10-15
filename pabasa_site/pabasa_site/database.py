"""Database configuration shared by the web service and migration jobs."""
from django.core.exceptions import ImproperlyConfigured


def database_config(env, base_dir, *, production=False):
    engine = env.get('DB_ENGINE', 'postgresql' if production else 'sqlite').strip().lower()
    if engine == 'sqlite':
        if production:
            raise ImproperlyConfigured('Production requires PostgreSQL; SQLite is instance-local on Cloud Run.')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': env.get('SQLITE_PATH') or base_dir / 'db.sqlite3'}
    if engine != 'postgresql':
        raise ImproperlyConfigured('DB_ENGINE must be postgresql or sqlite.')

    required = ('DB_NAME', 'DB_USER', 'DB_PASSWORD')
    missing = [name for name in required if not env.get(name)]
    host = env.get('DB_HOST', '').strip()
    instance = env.get('INSTANCE_CONNECTION_NAME', '').strip()
    if not host and instance:
        if len(instance.split(':')) != 3 or '/' in instance:
            raise ImproperlyConfigured('INSTANCE_CONNECTION_NAME must be project:region:instance.')
        host = f'/cloudsql/{instance}'
    if not host:
        missing.append('INSTANCE_CONNECTION_NAME or DB_HOST')
    if missing:
        raise ImproperlyConfigured('Missing PostgreSQL configuration: ' + ', '.join(missing))
    try:
        pool_size = int(env.get('DB_POOL_MAX_SIZE', '6'))
    except (TypeError, ValueError):
        raise ImproperlyConfigured('DB_POOL_MAX_SIZE must be an integer between 1 and 32.') from None
    if not 1 <= pool_size <= 32:
        raise ImproperlyConfigured('DB_POOL_MAX_SIZE must be an integer between 1 and 32.')
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env['DB_NAME'],
        'USER': env['DB_USER'],
        'PASSWORD': env['DB_PASSWORD'],
        'HOST': host,
        'PORT': env.get('DB_PORT') or '5432',
        # Returning a connection releases it to the bounded per-process pool.
        # Budget every web worker, overlapping revision, and migration job.
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'connect_timeout': 10,
            'pool': {
                'min_size': 0,
                'max_size': pool_size,
                'timeout': 5,
                'max_waiting': 32,
                'max_idle': 60,
            },
        },
    }
