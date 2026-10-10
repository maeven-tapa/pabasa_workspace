"""Shared branding for HTML emails, using URLs mail clients can resolve."""
from html import escape
from urllib.parse import urljoin

from django.conf import settings
from django.templatetags.static import static


def email_logo_url():
    base_url = settings.SITE_URL or getattr(settings, 'BASE_URL', '')
    return urljoin(base_url.rstrip('/') + '/', static('pabasa_app/images/pabasa_logo.png'))


def email_logo_html(width=240):
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
        '<tr><td align="center" style="text-align: center;">'
        f'<img src="{escape(email_logo_url(), quote=True)}" alt="PABASA" width="{width}" '
        f'height="{width // 3}" style="display: block; width: {width}px; max-width: 100%; '
        'height: auto; margin: 0 auto; border: 0;">'
        '</td></tr></table>'
    )
