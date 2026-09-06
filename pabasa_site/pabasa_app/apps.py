from django.apps import AppConfig
import logging


logger = logging.getLogger(__name__)


class PabasaAppConfig(AppConfig):
    name = 'pabasa_app'

    def ready(self):
        # Deliberately installed at app startup so existing server-side consumers
        # (scheduled materials, live sessions, and timestamps) share the debug clock.
        from .system_clock import install_timezone_override
        install_timezone_override()
        try:
            from .management.commands.seed_official_crla_assessments import validate_official_crla_payloads
            warnings = validate_official_crla_payloads()
            for warning in warnings:
                logger.warning("Official CRLA payload validation: %s", warning)
        except Exception as exc:
            logger.warning("Official CRLA payload validation could not run at startup: %s", exc)
