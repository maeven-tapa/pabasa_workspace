"""Test the replacement-only migration release on disposable SQLite databases.

Run with Django 6.0.3: python tools/verify_migrations.py
The configured database is opened read-only and copied, never migrated in place.
"""

import contextlib
import hashlib
import io
from pathlib import Path
import sqlite3
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "pabasa_site"
CURRENT_MIGRATION = ("pabasa_app", "0001_current_schema")


def snapshot(path):
    """Fingerprint schema and records without exposing application data."""
    with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        tables = sorted(row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations'"
        ))
        records = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = sorted(repr(row) for row in db.execute("SELECT * FROM " + quoted))
            records[table] = (len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest())
        schema = db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name != 'django_migrations' ORDER BY type,name"
        ).fetchall()
        return schema, records


def main():
    sys.path.insert(0, str(PROJECT))
    from django.conf import settings
    from pabasa_site import settings as project_settings

    with tempfile.TemporaryDirectory(prefix="pabasa-migration-check-") as directory:
        scratch = Path(directory).resolve()
        config = {
            key: getattr(project_settings, key)
            for key in dir(project_settings) if key.isupper()
        }
        config["DATABASES"] = {"default": {
            "ENGINE": "django.db.backends.sqlite3", "NAME": str(scratch / "fresh.sqlite3")
        }}
        settings.configure(**config)
        import django
        django.setup()
        from django.apps import apps
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from django.db.migrations.recorder import MigrationRecorder

        def check(**kwargs):
            call_command("check_migration_readiness", stdout=io.StringIO(), **kwargs)

        def expect_rejection(message):
            try:
                check()
            except CommandError as error:
                assert message in str(error), str(error)
            else:
                raise AssertionError("Unsafe migration history was accepted")

        try:
            check()
            executor = MigrationExecutor(connection)
            app_files = {key for key in executor.loader.disk_migrations if key[0] == "pabasa_app"}
            assert app_files == {CURRENT_MIGRATION}, app_files
            # Seed functions may print account details; do not expose those logs.
            with contextlib.redirect_stdout(io.StringIO()):
                executor.migrate(executor.loader.graph.leaf_nodes())
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA integrity_check")
                assert cursor.fetchall() == [("ok",)]
                cursor.execute("PRAGMA foreign_key_check")
                assert not cursor.fetchall()
                actual = set(connection.introspection.table_names(cursor))
            expected = {
                model._meta.db_table
                for model in apps.get_app_config("pabasa_app").get_models(include_auto_created=True)
            }
            assert expected <= actual, expected - actual
            check(require_recorded=True)
            print("PASS: only the replacement is loaded; a fresh database builds and passes integrity checks")

            source = PROJECT / "db.sqlite3"
            target = scratch / "existing.sqlite3"
            with contextlib.closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
                with contextlib.closing(sqlite3.connect(target)) as copy:
                    original.backup(copy)
            before = snapshot(target)
            connection.close()
            connection.settings_dict["NAME"] = str(target)
            check()
            executor = MigrationExecutor(connection)
            assert not executor.migration_plan([CURRENT_MIGRATION]), "Existing database would replay operations"
            executor.migrate([CURRENT_MIGRATION])
            assert snapshot(target) == before, "Application data or schema changed"
            check(require_recorded=True)
            assert CURRENT_MIGRATION in MigrationRecorder(connection).applied_migrations()
            # Repeated deployment must also be a no-op.
            MigrationExecutor(connection).migrate([CURRENT_MIGRATION])
            assert snapshot(target) == before
            print("PASS: current database copy upgrades and re-runs without changing schema or application records")

            # Corrupt only the disposable copy's history to exercise the guard.
            recorder = MigrationRecorder(connection)
            recorder.record_unapplied(*CURRENT_MIGRATION)
            recorder.record_unapplied("pabasa_app", "0113_prevent_unsaved_practice_level_reservations")
            expect_rejection("historical migrations are not recorded")
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM django_migrations WHERE app=%s", ["pabasa_app"])
            expect_rejection("Application tables exist without migration history")
            print("PASS: readiness gate rejects partial history and existing tables with missing history")
        finally:
            connection.close()


if __name__ == "__main__":
    main()
