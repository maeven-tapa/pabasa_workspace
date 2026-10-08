"""Restore an export into a new, empty PostgreSQL database before cutover."""
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import a verified SQLite export into a new, empty PostgreSQL database.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=Path)
        parser.add_argument('--expected-database', required=True)

    def handle(self, *args, **options):
        fixture = options['fixture'].resolve(strict=True)
        manifest = json.loads(fixture.with_name('manifest.json').read_text(encoding='utf-8'))
        if hashlib.sha256(fixture.read_bytes()).hexdigest() != manifest['fixture_sha256']:
            raise CommandError('Export checksum mismatch; the target has not been changed.')
        source = json.loads(fixture.read_text(encoding='utf-8'))
        counts = dict(Counter(item['model'] for item in source))
        if counts != manifest['counts'] or len(source) != manifest['total_objects']:
            raise CommandError('Export record counts do not match the manifest.')
        if connection.vendor != 'postgresql':
            raise CommandError('This command only imports into PostgreSQL.')
        if connection.settings_dict['NAME'] != options['expected_database']:
            raise CommandError('Configured database does not match --expected-database.')

        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [72422790])
            if not cursor.fetchone()[0]:
                raise CommandError('Another import is running. Wait for it to finish.')
        try:
            if connection.introspection.table_names():
                raise CommandError('Target already contains tables. Use a newly created, empty database; nothing was overwritten.')
            with redirect_stdout(io.StringIO()):
                call_command('check_migration_readiness', stdout=io.StringIO())
                call_command('migrate', interactive=False, verbosity=0, stdout=io.StringIO())
                # Only a database proven empty above reaches this step. Remove
                # the bootstrap records created by migrations, preserving schema
                # and migration history, before restoring the source's IDs.
                call_command('flush', interactive=False, verbosity=0, stdout=io.StringIO())
                call_command('loaddata', str(fixture), verbosity=0, stdout=io.StringIO())
                restored_stream = io.StringIO()
                call_command('dumpdata', exclude=['contenttypes', 'auth.permission'],
                             use_base_manager=True, use_natural_foreign_keys=True,
                             verbosity=0, stdout=restored_stream)
            restored = json.loads(restored_stream.getvalue())
            by_key = lambda records: {(item['model'], str(item['pk'])): item for item in records}
            if by_key(source) != by_key(restored) or len(source) != len(restored):
                raise CommandError('Imported data did not match the export. Keep traffic off this database and investigate.')
            call_command('check_migration_readiness', require_recorded=True, stdout=io.StringIO())
            self.stdout.write(self.style.SUCCESS(
                f'Imported and verified all {len(source)} records in {options["expected_database"]}.'))
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [72422790])
