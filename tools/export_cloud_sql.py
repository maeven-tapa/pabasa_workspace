"""Back up a local SQLite source and export an upgraded COPY for Cloud SQL.

The source is opened read-only. Backups contain private account/student data and
must stay outside Git and container images. Run while application writes are paused.
"""
import argparse
from collections import Counter
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'pabasa_site'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=PROJECT / 'db.sqlite3')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = (args.output_dir or ROOT / 'backups' / f'cloud-sql-{stamp}').resolve()
    destination.mkdir(parents=True, exist_ok=False)
    backup = destination / 'source.sqlite3'
    working = destination / 'export.sqlite3'
    fixture = destination / 'pabasa-data.json'

    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(backup)) as target:
            original.backup(target)
            if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('SQLite backup failed its integrity check.')
            if target.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('Source has broken foreign keys; repair a copy before exporting.')
    shutil.copy2(backup, working)

    # Only this disposable working copy receives schema/data migrations.
    os.environ['DB_ENGINE'] = 'sqlite'
    os.environ['SQLITE_PATH'] = str(working)
    if os.environ.get('K_SERVICE') or os.environ.get('CLOUD_RUN_JOB') or os.environ.get('DJANGO_ENV') == 'production':
        raise RuntimeError('Run this export locally, outside a production service or job.')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    sys.path.insert(0, str(PROJECT))
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connections
    try:
        # Historical seed commands may print credentials: do not publish them.
        with redirect_stdout(io.StringIO()):
            call_command('check_migration_readiness', stdout=io.StringIO())
            call_command('migrate', interactive=False, verbosity=0, stdout=io.StringIO())
            # Explicit UTF-8 also preserves Filipino text and emoji on Windows.
            with fixture.open('w', encoding='utf-8') as fixture_stream:
                call_command('dumpdata', exclude=['contenttypes', 'auth.permission'],
                             use_base_manager=True, use_natural_foreign_keys=True,
                             verbosity=0, stdout=fixture_stream)
        payload = json.loads(fixture.read_text(encoding='utf-8'))
        manifest = {
            'created_at_utc': stamp,
            'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'source_backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
            'counts': dict(sorted(Counter(item['model'] for item in payload).items())),
            'total_objects': len(payload),
            'includes_sessions': True,
        }
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f'Backup and export ready: {destination}')
        print(f'Exported {len(payload)} records. Source database was not modified.')
    finally:
        connections.close_all()


if __name__ == '__main__':
    main()
