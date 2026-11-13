"""Disposable file-backed SQLite for real, concurrent browser HTTP requests.

Django's default in-memory SQLite live server shares one connection across
request threads, including their transaction state. A file gives each request
its own connection, as it would have in the running application.
"""
import tempfile
from pathlib import Path

from .settings import *  # noqa: F401,F403

_browser_test_directory = tempfile.TemporaryDirectory(prefix='pabasa-browser-tests-')
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': str(Path(_browser_test_directory.name) / 'local.sqlite3'),
    'TEST': {'NAME': str(Path(_browser_test_directory.name) / 'test.sqlite3')},
    'OPTIONS': {'timeout': 20},
}}
