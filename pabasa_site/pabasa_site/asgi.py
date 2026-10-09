"""
ASGI config for pabasa_site project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')

django_application = get_asgi_application()

from pabasa_app.crla_stream import crla_websocket


async def application(scope, receive, send):
    if scope['type'] == 'websocket':
        await crla_websocket(scope, receive, send)
    else:
        await django_application(scope, receive, send)
