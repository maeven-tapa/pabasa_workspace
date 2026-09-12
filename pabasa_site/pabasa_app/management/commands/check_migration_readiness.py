"""Read-only gate for databases upgrading to the replacement-only release."""

from importlib import import_module

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


REPLACEMENT = ("pabasa_app", "0001_current_schema")


class Command(BaseCommand):
    help = "Check that this database can safely use the current migration release."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default", choices=tuple(connections))
        parser.add_argument("--require-recorded", action="store_true")

    def handle(self, *args, **options):
        connection = connections[options["database"]]
        migration = import_module("pabasa_app.migrations.0001_current_schema").Migration
        applied = MigrationRecorder(connection).applied_migrations()
        missing = sorted(set(migration.replaces) - applied.keys())
        app_history = {key for key in applied if key[0] == REPLACEMENT[0]}
        if missing and app_history:
            raise CommandError(
                f"{len(missing)} historical migrations are not recorded. "
                "Do not migrate with this release. Use the previous release containing "
                "all original migrations, run migrate there, then deploy this cleanup."
            )
        if REPLACEMENT not in applied and options["require_recorded"]:
            raise CommandError(
                "The current migration is not recorded. Run migrate after the readiness check passes."
            )
        loader = MigrationLoader(connection)
        loader.check_consistent_history(connection)
        if REPLACEMENT in applied:
            message = "The replacement migration is recorded; this database is ready."
        elif not app_history:
            with connection.cursor() as cursor:
                tables = set(connection.introspection.table_names(cursor))
            state = loader.project_state([REPLACEMENT])
            app_tables = {
                model._meta.db_table
                for model in state.apps.get_app_config("pabasa_app").get_models(include_auto_created=True)
            }
            if app_tables & tables:
                raise CommandError("Application tables exist without migration history. Stop and restore/repair the migration history before upgrading.")
            message = "No application tables or migration history exist; a fresh install is ready."
        else:
            message = "All 117 originals are recorded; migrate will record the replacement without replaying its operations."
        self.stdout.write(self.style.SUCCESS(message))
