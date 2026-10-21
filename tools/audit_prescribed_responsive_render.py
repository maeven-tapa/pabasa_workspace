"""Render isolated Session 1–3 fixtures and HEAD baselines without database access."""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pabasa_site'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from django.db import connection
from django.http import HttpResponse
from django.template import Engine, RequestContext, engines
from django.test import RequestFactory
from pabasa_app import views

out = ROOT / 'tmp' / 'prescribed-responsive-audit'
out.mkdir(parents=True, exist_ok=True)
base = engines['django'].engine
baseline_ref = os.environ.get('PABASA_AUDIT_BASE', 'HEAD')
baseline_commit = subprocess.check_output(['git', 'rev-parse', baseline_ref], cwd=ROOT, text=True).strip()
changed = subprocess.check_output(['git', 'diff', baseline_commit, '--name-only', '--', 'pabasa_site/pabasa_app/templates'], cwd=ROOT, text=True).splitlines()
originals = {
    str(Path(name).relative_to('pabasa_site/pabasa_app/templates')).replace('\\', '/'):
    subprocess.check_output(['git', 'show', baseline_commit + ':' + name], cwd=ROOT).decode('utf-8')
    for name in changed
}
baseline = Engine(dirs=base.dirs, loaders=[('django.template.loaders.locmem.Loader', originals), 'django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader'], libraries=base.libraries, builtins=base.builtins)
factory = RequestFactory()
manifest = []

def no_database(execute, sql, params, many, context):
    raise AssertionError('Audit fixture attempted database access')

for session in views._admin_prescribed_sessions()[:3]:
    for activity in session['activities']:
        key = activity['activity_key']
        request = factory.get('/activity/' + key)
        request.session = {'user_id': -999999, 'user_role': 'admin'}
        request._admin_prescribed_preview = True
        captured = {}

        def render_fixture(req, template, context=None, **kwargs):
            captured.update(template=template, context=context or {})
            return HttpResponse('fixture')

        with connection.execute_wrapper(no_database), patch.object(views, '_dashboard_context', return_value={}), patch.object(views, '_enforce_prescribed_activity_sequence', return_value=None), patch.object(views, '_active_prescribed_student', return_value=None), patch.object(views.StudentActivityProgress.objects, 'filter') as progress, patch.object(views, 'render', side_effect=render_fixture):
            progress.return_value.first.return_value = None
            fn = inspect.unwrap(getattr(views, activity['route_name'])) if activity.get('route_name') else inspect.unwrap(views.prescribed_activity_page)
            response = fn(request) if activity.get('route_name') else fn(request, key)
            assert response.status_code == 200 and captured, (key, response.status_code)
        for name, engine in [('current', base), ('baseline', baseline)]:
            html = engine.get_template(captured['template']).render(RequestContext(request, captured['context']))
            (out / (key + '-' + name + '.html')).write_text(html, encoding='utf-8')
        manifest.append({'key': key, 'session': session['number'], 'template': captured['template']})
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(out / 'baseline.json').write_text(json.dumps({'commit': baseline_commit}, indent=2), encoding='utf-8')
print(f'Rendered {len(manifest)} actual activity views and HEAD baselines without database access: {out}')
