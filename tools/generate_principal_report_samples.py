"""Render an existing local school's aggregate snapshot with SQLite read-only.

No migrations, sessions, account creation, production access or student details.
Synthetic stress samples are explicitly labeled and never masquerade as records.
"""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'pabasa_site' / 'db.sqlite3')
    parser.add_argument('--school-id', type=int)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'pdf' / 'principal')
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error('The existing local SQLite database was not found.')
    os.environ.update(DB_ENGINE='sqlite', SQLITE_PATH=str(args.database.resolve()),
                      DJANGO_ENV='development', K_SERVICE='', CLOUD_RUN_JOB='',
                      DJANGO_SETTINGS_MODULE='pabasa_site.settings')
    sys.path.insert(0, str(ROOT / 'pabasa_site'))
    import django
    django.setup()
    from django.db import connection
    from pabasa_app.models import User
    from pabasa_app.principal_exports import pdf_response, report_rows
    from pabasa_app.principal_reporting import build_principal_snapshot
    from pabasa_app.views import _principal_report_logo_path

    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA query_only = ON')
    principals = User.objects.filter(role='principal', school_record__isnull=False).select_related('school_record')
    if args.school_id:
        principals = principals.filter(school_record_id=args.school_id)
    principal = principals.order_by('pk').first()
    if principal is None:
        parser.error('No existing school-assigned principal is available. No data was created.')
    snapshot = build_principal_snapshot(principal)
    args.output.mkdir(parents=True, exist_ok=True)

    def write(name, value, logo=None):
        headers, rows = report_rows(value, 'school')
        response = pdf_response(value, 'school', headers, rows, logo)
        target = args.output / f'pabasa-principal-{name}.pdf'
        target.write_bytes(response.content)
        print(f'{name}: {target}')

    write('existing-data', snapshot, _principal_report_logo_path(snapshot))
    # Use a separate, explicitly synthetic fixture for fuller visual QA.
    from pabasa_app.tests_principal_report_pdf import example_snapshot
    illustrative = example_snapshot(school_name='Salawag Elementary School / Illustrative layout sample')
    write('illustrative', illustrative)
    empty = deepcopy(illustrative)
    empty.update(school_name='Salawag Elementary School / Zero-data layout sample',
        scope_calendar=None, scope_term='', scope_phase='', scope_phase_label='All CRLA periods',
        total_students=0, total_teachers=0, total_sections=0, total_assessments=0,
        official_completed_students=0, completion_rate=0, average_score=None, accuracy_samples=0,
        aral_eligible_students=0, aral_progress_students=0, aral_recorded_exits=0,
        pending_review_students=0, prescribed_counts={'completed': 0},
        supplementary_counts={'assigned': 0, 'completed': 0})
    write('zero-data', empty)
    # A multipage detail export exercises long text, repeated headers and page totals.
    stress_headers, _ = report_rows(illustrative, 'intervention')
    stress_rows = [[f'Illustrative Learner {index + 1}', 'Illustrative Section', 'Illustrative Teacher',
                    'Illustrative recorded follow-up details. ' * (75 if index == 0 else 4)]
                   for index in range(14)]
    stress = pdf_response(illustrative, 'intervention', stress_headers, stress_rows)
    (args.output / 'pabasa-principal-pagination-check.pdf').write_bytes(stress.content)
    connection.close()


if __name__ == '__main__':
    main()
