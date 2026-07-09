import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from pabasa_app.models import User
import pabasa_app.views as views_mod

teacher = User.objects.filter(email='upload-teacher@example.com').first()
if not teacher:
    teacher = User.objects.create(
        custom_id='TCH-TEST', role='teacher', first_name='Tina', last_name='Teacher',
        middle_initial='', suffix='', sex='female', birth_month=5, birth_day=10, birth_year=1988,
        email='upload-teacher@example.com', password_hash=make_password('teacher-password'),
        teacher_role='Teacher',
    )

client = Client()
session = client.session
session['user_id'] = teacher.id
session['user_role'] = teacher.role
session['first_name'] = teacher.first_name
session['last_name'] = teacher.last_name
session['email'] = teacher.email
session['custom_id'] = teacher.custom_id
session.save()

orig = views_mod._extract_text_from_image
views_mod._extract_text_from_image = lambda upload: {'text': 'Alpha beta gamma', 'layout': []}
try:
    response = client.post('/dashboard/teacher/extract-material/', {'file': SimpleUploadedFile('scan.png', b'abc', content_type='image/png')}, format='multipart')
    print('status', response.status_code)
    print('content-type', response['Content-Type'])
    print(response.content.decode())
finally:
    views_mod._extract_text_from_image = orig
