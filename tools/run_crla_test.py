import os
import subprocess

os.chdir(r'c:\Users\iamdo\Documents\GitHub\pabasa_workspace')
result = subprocess.run([
    'python',
    'pabasa_site\manage.py',
    'test',
    'pabasa_app.tests.ClassMaterialsApiTests.test_get_class_materials_filters_official_crla_by_active_calendar_phase_for_aral_students',
    '--verbosity=2'
], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
print('RETURN_CODE=', result.returncode)
