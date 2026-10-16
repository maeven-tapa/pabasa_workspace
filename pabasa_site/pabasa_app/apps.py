from django.apps import AppConfig
import logging


logger = logging.getLogger(__name__)


class PabasaAppConfig(AppConfig):
    name = 'pabasa_app'
    # Match the existing schema rather than Django 6's new implicit default.
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from . import achievement_signals  # noqa: F401
        try:
            from .management.commands.seed_official_crla_assessments import validate_official_crla_payloads
            warnings = validate_official_crla_payloads()
            for warning in warnings:
                logger.warning("Official CRLA payload validation: %s", warning)
        except Exception as exc:
            logger.warning("Official CRLA payload validation could not run at startup: %s", exc)
