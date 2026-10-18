"""
ASGI config for pabasa_site project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.conf import settings

from .http_admission import HttpAdmission

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')

django_application = get_asgi_application()
http_admission = HttpAdmission(
    settings.DATABASES['default'].get('OPTIONS', {}).get('pool', {}).get('max_size', 6)
)

from pabasa_app.crla_stream import crla_websocket


async def application(scope, receive, send):
    if scope['type'] == 'websocket':
        await crla_websocket(scope, receive, send)
    else:
        async with http_admission.request(scope):
            await django_application(scope, receive, send)
