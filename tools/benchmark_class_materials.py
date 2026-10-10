"""Local, disposable 20-student listing benchmark; never targets the live site.

Run with Python 3.13 and requirements.txt installed:
    python tools/benchmark_class_materials.py --baseline-ref <previous-commit>
Only aggregate timings, query counts and response sizes are printed or saved.
"""

import argparse
import ast
import concurrent.futures
import datetime as dt
import json
import logging
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
CLIENTS = 20
ROUNDS = 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--output', default='tmp/class-materials-twenty-benchmark.json')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    if os.environ.get('K_SERVICE') or os.environ.get('CLOUD_RUN_JOB'):
        parser.error('This benchmark is local-only.')
    source = subprocess.run(
        ['git', 'show', f'{args.baseline_ref}:pabasa_site/pabasa_app/views.py'],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8',
    ).stdout
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'get_class_materials')
    baseline_revision = subprocess.run(
        ['git', 'rev-parse', args.baseline_ref], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory(prefix='pabasa-materials-') as directory:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
        os.environ['DJANGO_ENV'] = 'development'
        os.environ['DB_ENGINE'] = 'sqlite'
        os.environ['SQLITE_PATH'] = str(Path(directory) / 'benchmark.sqlite3')
        sys.path.insert(0, str(ROOT / 'pabasa_site'))
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import connection, connections
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.messages.storage.fallback import FallbackStorage
        from pabasa_app import views
        from pabasa_app.models import Material, Practice, StoryReadingProgress, StoryResponseSubmission
        from pabasa_app.prescribed_test_fixtures import prescribed_term_fixture
        from pabasa_app.tests_class_materials_efficiency import ClassMaterialsEfficiencyTests

        # This database was just created inside the temporary directory.
        call_command('migrate', verbosity=0, interactive=False)
        case = ClassMaterialsEfficiencyTests()
        case.setUp()
        students = [case.student]
        for number in range(2, CLIENTS + 1):
            student = case.make_user(f'benchmark-student-{number}')
            prescribed_term_fixture(student, section=case.section, calendar=case.calendar, teacher=case.teacher)
            students.append(student)
        for number in range(1, 21):
            kind = number % 5
            content = (
                {'activity_type': 'story_reading', 'storyText': 'Synthetic story. ' * 200} if kind == 1 else
                {'activity_type': 'story_response', 'response_prompt': 'Synthetic prompt. ' * 200} if kind == 2 else
                {'activity_type': 'retell_story', 'response_prompt': 'Synthetic prompt. ' * 200} if kind == 3 else
                {'activity_key': 'fluency_reading', 'items': ['Synthetic sentence.'] * 100} if kind == 4 else
                {'items': ['Synthetic word'] * 100, 'language': 'English'}
            )
            material = case.make_material(number, content_json=content, item_type='paragraph' if kind in (1, 2, 3) else 'word')
            if kind == 0:
                group = case.make_assessment(number, material)
                case.attempt(group, 1)
            elif kind == 1:
                case.direct_result(material, number)
            elif kind in (2, 3):
                StoryResponseSubmission.objects.create(
                    student=case.student, material=material, school_calendar=case.calendar,
                    term=1, status='pending',
                )
                if kind == 3:
                    case.direct_result(material, number)
            else:
                case.direct_result(material, number, remarks=views.ARAL_RESULT_PREFIXES['fluency-reading'] + '{}')
        Practice.objects.create(
            teacher=case.teacher, section=case.section, title='Synthetic practice', code='BENCH-P',
            practice_type='word', status='published', contents='Synthetic practice. ' * 100,
        )
        # Cover standalone assessments as well as material-linked attempts.
        case.make_assessment(999)
        namespace = dict(vars(views))
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<baseline view>', 'exec'), namespace)
        baseline = namespace['get_class_materials']
        for student in students:
            original = case.payload(user=student, view=baseline)
            optimized = case.payload(user=student)
            if original != optimized:
                raise AssertionError('Detailed response parity failed on synthetic fixture')

        # Save actual Django-rendered HTML for a separate browser integration
        # check. This file and its data contain synthetic fixtures only.
        request = case.factory.get('/dashboard/assessment/')
        request.session = {'user_id': case.student.id, 'user_role': 'student', 'email': case.student.email}
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        page = views.assessment(request)
        if page.status_code == 200:
            (ROOT / 'tmp/materials-browser-page.html').write_bytes(page.content)
            (ROOT / 'tmp/materials-browser-payload.json').write_text(json.dumps({
                'listing': case.payload(summary=True),
                'classes': {'success': True, 'classes': [{
                    'id': case.section.id, 'section_id': case.section.id,
                    'code': case.section.class_code, 'name': case.section.class_name,
                    'subject': case.section.subject,
                }]},
            }), encoding='utf-8')
        story = Material.objects.get(code='LIST-M-1')
        StoryReadingProgress.objects.create(
            student=case.student, material=story, enrollment=case.enrollment,
            school_calendar=case.calendar, term=1, completed=True,
        )
        story_request = case.factory.get('/dashboard/assessment/story-reading/', {
            'id': f'material-{story.id}', 'section_id': case.section.id,
        })
        story_request.session = request.session
        story_request.user = AnonymousUser()
        story_request._messages = FallbackStorage(story_request)
        story_page = views.story_reading_page(story_request)
        if story_page.status_code == 200:
            (ROOT / 'tmp/materials-browser-story-page.html').write_bytes(story_page.content)

        def run_wave(view, summary):
            barrier = threading.Barrier(CLIENTS)
            def request(student):
                connections.close_all()
                # Endpoint calls are verified read-only during the benchmark.
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA query_only=ON')
                timings = []
                def capture(execute, sql, params, many, context):
                    started = time.perf_counter()
                    try:
                        return execute(sql, params, many, context)
                    finally:
                        timings.append(time.perf_counter() - started)
                barrier.wait(timeout=30)
                started = time.perf_counter()
                try:
                    with connection.execute_wrapper(capture):
                        response = case.request(user=student, summary=summary, view=view)
                    elapsed = time.perf_counter() - started
                    if response.status_code != 200:
                        raise AssertionError('Synthetic benchmark request failed')
                    return {'ms': elapsed * 1000, 'queries': len(timings),
                            'sql_ms': sum(timings) * 1000, 'bytes': len(response.content)}
                finally:
                    connections.close_all()
            with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENTS) as pool:
                return list(pool.map(request, students))

        def summarize(samples):
            times = sorted(row['ms'] for row in samples)
            return {
                'requests': len(samples), 'errors': 0,
                'mean_ms': round(statistics.mean(times), 2),
                'p95_ms': round(times[int(len(times) * .95) - 1], 2),
                'mean_queries': round(statistics.mean(row['queries'] for row in samples), 2),
                'mean_sql_ms': round(statistics.mean(row['sql_ms'] for row in samples), 2),
                'mean_response_bytes': round(statistics.mean(row['bytes'] for row in samples)),
            }
        samples = {name: [] for name in ('baseline_full', 'optimized_full', 'optimized_summary')}
        variants = [('baseline_full', baseline, False), ('optimized_full', views.get_class_materials, False),
                    ('optimized_summary', views.get_class_materials, True)]
        for round_number in range(ROUNDS):
            # Rotate scheduling order to avoid consistently favoring warm runs.
            for name, view, summary in variants[round_number:] + variants[:round_number]:
                samples[name].extend(run_wave(view, summary))
        result = {
            'measured_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'python_version': sys.version.split()[0], 'django_version': django.get_version(),
            'scope': 'Internal Django requests on disposable local SQLite; excludes HTTP/network/browser and production PostgreSQL.',
            'clients': CLIENTS, 'distinct_students': len(students), 'enrolled_students': CLIENTS,
            'rounds': ROUNDS, 'fixture_materials': 20, 'baseline_revision': baseline_revision,
            'detailed_response_parity': True, 'browser_fixture_rendered': page.status_code == 200,
            'story_browser_fixture_rendered': story_page.status_code == 200,
            'results': {name: summarize(rows) for name, rows in samples.items()},
        }
        before = result['results']['baseline_full']
        after = result['results']['optimized_summary']
        result['p95_reduction_percent'] = round((1 - after['p95_ms'] / before['p95_ms']) * 100, 1)
        result['payload_reduction_percent'] = round((1 - after['mean_response_bytes'] / before['mean_response_bytes']) * 100, 1)
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
        connections.close_all()


if __name__ == '__main__':
    main()
