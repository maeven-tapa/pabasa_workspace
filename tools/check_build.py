"""Validate the built image against disposable local data, without cloud access."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    if (root / '.env').exists():
        raise RuntimeError('Build checks require a clean build context without .env.')
    with tempfile.TemporaryDirectory(prefix='pabasa-build-check-') as directory:
        env = dict(os.environ, DB_ENGINE='sqlite', SQLITE_PATH=str(Path(directory) / 'check.sqlite3'),
                   DJANGO_ENV='development', DJANGO_SECRET_KEY='disposable-build-check-only',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PYTHONPATH=str(root / 'pabasa_site'))
        for name in ('K_SERVICE', 'CLOUD_RUN_JOB', 'DJANGO_SETTINGS_MODULE'):
            env.pop(name, None)

        def run(*args):
            subprocess.run([sys.executable, *args], cwd=root, env=env, check=True)

        run('-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_cloud_release*.py')
        manage = 'pabasa_site/manage.py'
        run(manage, 'check')
        run(manage, 'makemigrations', '--check', '--dry-run')
        run(manage, 'test', 'pabasa_app.tests_database_config', 'pabasa_app.tests_account_sessions',
            'pabasa_app.tests_enrollment_lifecycle_remaining', 'pabasa_app.tests_review_queue',
            'pabasa_app.tests_story_response_review', '--noinput')
        print('Build checks passed using disposable SQLite only.', flush=True)


if __name__ == '__main__':
    main()
