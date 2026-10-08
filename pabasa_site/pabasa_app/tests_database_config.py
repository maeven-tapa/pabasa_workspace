import os
from pathlib import Path
import subprocess
import sys

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from pabasa_site.database import database_config


class DatabaseConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.env = {
            'DB_NAME': 'pabasa', 'DB_USER': 'pabasa_app', 'DB_PASSWORD': 'test-only-password',
            'INSTANCE_CONNECTION_NAME': 'example:asia-southeast1:pabasa-db',
        }

    def test_local_development_defaults_to_sqlite(self):
        self.assertEqual(database_config({}, Path('/project'))['NAME'], Path('/project/db.sqlite3'))

    def test_cloud_run_uses_shared_postgres_socket(self):
        config = database_config(self.env, Path('/project'), production=True)
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['HOST'], '/cloudsql/example:asia-southeast1:pabasa-db')
        self.assertEqual(config['CONN_MAX_AGE'], 0)

    def test_proxy_host_can_be_used_locally(self):
        self.env.update(DB_ENGINE='postgresql', DB_HOST='127.0.0.1', DB_PORT='15432')
        config = database_config(self.env, Path('/project'))
        self.assertEqual((config['HOST'], config['PORT']), ('127.0.0.1', '15432'))

    def test_production_cannot_fall_back_to_sqlite(self):
        with self.assertRaises(ImproperlyConfigured):
            database_config({'DB_ENGINE': 'sqlite'}, Path('/project'), production=True)

    def test_missing_credentials_are_rejected_without_exposing_password(self):
        del self.env['DB_USER']
        with self.assertRaises(ImproperlyConfigured) as raised:
            database_config(self.env, Path('/project'), production=True)
        self.assertIn('DB_USER', str(raised.exception))
        self.assertNotIn(self.env['DB_PASSWORD'], str(raised.exception))

    def test_missing_connection_is_rejected(self):
        del self.env['INSTANCE_CONNECTION_NAME']
        with self.assertRaises(ImproperlyConfigured):
            database_config(self.env, Path('/project'), production=True)

    def test_password_whitespace_is_preserved(self):
        self.env['DB_PASSWORD'] = ' password with spaces '
        self.assertEqual(database_config(self.env, Path('/project'), production=True)['PASSWORD'],
                         self.env['DB_PASSWORD'])

    def test_service_and_job_both_select_production(self):
        for marker in ('K_SERVICE', 'CLOUD_RUN_JOB'):
            with self.subTest(marker=marker):
                env = {**os.environ, **self.env, marker: 'test', 'DJANGO_SECRET_KEY': 'test-only-signing-key'}
                env.pop('DB_ENGINE', None)
                code = ('import pabasa_site.settings as s; '
                        "assert s.DJANGO_ENV == 'production'; "
                        "assert s.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'")
                subprocess.run([sys.executable, '-c', code], env=env, check=True,
                               capture_output=True, timeout=30)
