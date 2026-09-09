"""Practice persistence checks use disposable databases, never the application's data."""
import importlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.db import connection
from django.test import Client, TransactionTestCase
from django.urls import reverse

from .models import Material, User


class PracticePersistenceTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create(
            custom_id='ADM-PERSISTENCE', role='admin', first_name='Practice',
            last_name='Admin', sex='female', birth_month=1, birth_day=1,
            birth_year=1990, email='persistence@example.com',
            password_hash=make_password('test-password'),
        )
        self.login()

    def login(self):
        response = self.client.post(reverse('login_user'), {
            'custom_id': self.admin.custom_id, 'password': 'test-password',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])

    def create_modes(self):
        records = []
        for mode, content in [('free', 'araw\nbuwan'), ('color', 'Ito ay araw.'),
                              ('hunt', 'Ito ay araw. Maliwanag ang araw.')]:
            response = self.client.post(reverse('admin_practice_create'), {
                'mode': mode, 'difficulty_level': 'easy', 'level': 'level_1',
                'status': 'published', 'language': 'Filipino', 'content_text': content,
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(response.status_code, 200, response.content)
            self.assertTrue(response.json()['saved'])
            self.assertEqual(self.client.get(response.json()['redirect_url']).status_code, 200)
            records.append(Material.objects.get(type='practice', content_json__mode=mode))
        return records

    def assert_listing(self, records):
        response = self.client.get(reverse('admin_practice_assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['language_filter'], 'Filipino')
        self.assertSetEqual(
            {row['material'].pk for row in response.context['practice_items']},
            {record.pk for record in records},
        )
        for record in records:
            stored = Material.objects.get(pk=record.pk)
            self.assertEqual(stored.content_json, record.content_json)
            self.assertEqual(stored.content_text, record.content_text)

    def test_save_refresh_logout_login_and_new_server_processes(self):
        records = self.create_modes()
        self.assert_listing(records)
        self.assert_listing(records)
        self.client.get(reverse('logout'))
        self.assertNotIn('user_id', self.client.session)
        self.assertEqual(Material.objects.filter(pk__in=[r.pk for r in records]).count(), 3)
        self.client = Client()
        self.login()
        self.assert_listing(records)

        # Boot Django twice against the same on-disk snapshot: no Python state,
        # session cookie or cache survives between the independent processes.
        with tempfile.TemporaryDirectory(prefix='pabasa-persistence-') as directory:
            database = Path(directory) / 'practice.sqlite3'
            with closing(sqlite3.connect(database)) as target:
                connection.connection.backup(target)
            script = '''
import json, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[1]
settings.ALLOWED_HOSTS = ['testserver']
import django
django.setup()
from django.test import Client
from django.test.utils import setup_test_environment
from django.urls import reverse
from pabasa_app.models import Material
setup_test_environment()
client = Client()
assert client.post(reverse('login_user'), {'custom_id': 'ADM-PERSISTENCE', 'password': 'test-password'}).json()['success']
response = client.get(reverse('admin_practice_assessment'))
assert response.status_code == 200
assert response.context['language_filter'] == 'Filipino'
expected = json.loads(sys.argv[2])
assert sorted(row['material'].pk for row in response.context['practice_items']) == sorted(r['id'] for r in expected)
assert list(Material.objects.filter(pk__in=[r['id'] for r in expected]).order_by('pk').values('id', 'content_text', 'content_json')) == expected
'''
            expected = list(Material.objects.filter(pk__in=[r.pk for r in records])
                            .order_by('pk').values('id', 'content_text', 'content_json'))
            for _ in range(2):
                result = subprocess.run(
                    [sys.executable, '-c', script, str(database), json.dumps(expected)],
                    cwd=Path(__file__).resolve().parents[1],
                    env={**os.environ, 'K_SERVICE': ''}, capture_output=True, text=True,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_confirmed_selected_record_is_deleted_archive_preserves_content(self):
        records = self.create_modes()
        target = records[1]
        url = reverse('admin_practice_delete', args=[target.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.get(reverse('admin_practice_assessment'))  # Open/cancel modal: no POST.
        self.client.post(url, {})
        self.client.post(url, {'confirm_delete': 'no'})
        self.assert_listing(records)
        archive = reverse('admin_practice_archive', args=[target.pk])
        self.client.post(archive, {'action': 'archive'})
        self.assert_listing(records)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.client.post(archive, {'action': 'restore'})
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.client.post(url, {'confirm_delete': 'yes'})
        self.assertFalse(Material.objects.filter(pk=target.pk).exists())
        self.assert_listing([records[0], records[2]])

    def test_seed_and_migration_preserve_existing_practice(self):
        records = self.create_modes()
        records[0].content_text = ''
        records[0].save(update_fields=['content_text'])
        seed = {
            'title': 'Replacement must not be applied', 'item_type': 'word',
            'prompt_text': '', 'content_text': 'replacement',
            'content_json': records[0].content_json, 'difficulty_level': 'easy',
        }
        with patch('pabasa_app.management.commands.seed_filipino_practice.SEED_PATH') as path:
            path.read_text.return_value = json.dumps([seed])
            call_command('seed_filipino_practice', stdout=StringIO())
            call_command('seed_filipino_practice', stdout=StringIO())
        migration = importlib.import_module(
            'pabasa_app.migrations.0113_prevent_unsaved_practice_level_reservations')
        migration.remove_incomplete_admin_practice_materials(apps, None)
        self.assert_listing(records)
