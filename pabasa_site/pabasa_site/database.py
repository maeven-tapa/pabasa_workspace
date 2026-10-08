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
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env['DB_NAME'],
        'USER': env['DB_USER'],
        'PASSWORD': env['DB_PASSWORD'],
        'HOST': host,
        'PORT': env.get('DB_PORT') or '5432',
        # Close connections after each request to bound idle connections across
        # Cloud Run instances. Size Cloud Run's instance limit for the database.
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'connect_timeout': 10},
    }
