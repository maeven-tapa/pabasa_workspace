"""Inspect aggregate database size/settings in an existing Cloud Run diagnostic job."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys


def inspect_database():
    sys.path.insert(0, '/app/pabasa_site')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    from django.conf import settings
    settings.DATABASES['default']['OPTIONS']['options'] = '-c default_transaction_read_only=on'
    import django
    django.setup()
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_database_size(current_database())')
        size = cursor.fetchone()[0]
        cursor.execute("SELECT name, setting, unit, source FROM pg_settings WHERE name IN "
                       "('shared_buffers','work_mem','maintenance_work_mem','effective_cache_size',"
                       "'max_connections','max_wal_size') ORDER BY name")
        settings_rows = [dict(zip(('name', 'setting', 'unit', 'source'), row)) for row in cursor.fetchall()]
    print('PABASA_DATABASE_SIZING ' + json.dumps({'database_bytes': size, 'settings': settings_rows}), flush=True)


def dispatch():
    sdk = Path(r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk')
    source = base64.b64encode(Path(__file__).read_bytes()).decode()
    code = f"import base64;exec(base64.b64decode('{source}'))"
    result = subprocess.run([str(sdk / 'platform/bundledpython/python.exe'), str(sdk / 'lib/gcloud.py'),
                             'run', 'jobs', 'execute', 'pabasa-revision-check-01172',
                             '--project=project-2b0d295d-ee06-40a7-927', '--region=asia-southeast1',
                             '--args=^~^-c~' + code, '--wait', '--format=value(metadata.name)'],
                            capture_output=True, text=True)
    if result.returncode:
        print(json.dumps({'status': 'failed', 'exit_code': result.returncode}))
    else:
        print(json.dumps({'status': 'succeeded', 'execution': result.stdout.strip()}))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    if os.environ.get('CLOUD_RUN_EXECUTION'):
        inspect_database()
    else:
        dispatch()
