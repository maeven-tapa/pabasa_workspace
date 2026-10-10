"""Resolve historical lesson image names to the compact source assets."""
import json
from functools import lru_cache
from pathlib import Path

from django.contrib.staticfiles.finders import AppDirectoriesFinder
from django.contrib.staticfiles.storage import StaticFilesStorage


@lru_cache(maxsize=1)
def image_asset_aliases():
    return json.loads(Path(__file__).with_name('static_image_aliases.json').read_text(encoding='utf-8'))


def canonical_asset_name(name):
    # Only exact manifest entries are mapped; uploads and other paths stay intact.
    name = str(name).replace('\\', '/')
    return image_asset_aliases().get(name, name)


@lru_cache(maxsize=1)
def original_image_names():
    return {new: old for old, new in image_asset_aliases().items()}


def original_asset_name(name):
    return original_image_names().get(name, name)


class CompactStaticFilesStorage(StaticFilesStorage):
    def url(self, name):
        return super().url(canonical_asset_name(name))


class CompactAppDirectoriesFinder(AppDirectoriesFinder):
    def find_in_app(self, app, path):
        return super().find_in_app(app, canonical_asset_name(path) if app == 'pabasa_app' else path)
