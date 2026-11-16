"""Read production through authenticated synthetic users; roll back all writes."""
import logging
import os
from pathlib import Path
import sys
import uuid


def main():
    if not os.environ.get('CLOUD_RUN_EXECUTION'):
        raise RuntimeError('This check requires an isolated same-image Cloud Run Job.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pabasa_site'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
    import django
    django.setup()
    from django.db import transaction
    from django.test import Client
    from pabasa_app.models import School, User

    logging.disable(logging.CRITICAL)
    marker = uuid.uuid4().hex[:12]
    with transaction.atomic():
        school = School.objects.create(name='Synthetic build verification', code='BC' + marker)
        teacher = User.objects.create(custom_id='BC-' + marker + '-T', role='teacher',
            first_name='Synthetic', last_name='Build Check', sex='female', birth_month=1,
            birth_day=1, birth_year=1990, password_hash='!unusable-build-check', school_record=school)
        client = Client(HTTP_HOST='tupcpabasa.app', HTTP_X_FORWARDED_PROTO='https')
        session = client.session
        session.update({'user_id': teacher.pk, 'user_role': 'teacher'})
        session.save()
        for path in ('/dashboard/teacher/', '/dashboard/teacher/needs-checking/',
                     '/api/teacher/needs-checking/'):
            response = client.get(path, secure=True)
            if response.status_code != 200:
                raise RuntimeError('Authenticated release check failed: ' + path + ' HTTP ' + str(response.status_code))
            print('Authenticated release check passed: ' + path, flush=True)
        anonymous = Client(HTTP_HOST='tupcpabasa.app', HTTP_X_FORWARDED_PROTO='https')
        response = anonymous.get('/api/teacher/needs-checking/', secure=True)
        if response.status_code not in (302, 401, 403):
            raise RuntimeError('Anonymous teacher endpoint access was not rejected.')
        transaction.set_rollback(True)
    if User.objects.filter(custom_id='BC-' + marker + '-T').exists() or School.objects.filter(code='BC' + marker).exists():
        raise RuntimeError('Synthetic release records were not rolled back.')
    print('Authenticated checks passed; synthetic records and sessions rolled back.', flush=True)


if __name__ == '__main__':
    main()
