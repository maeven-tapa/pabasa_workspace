"""Return a retryable response when the bounded database pool is busy."""
import sys

from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.utils.html import format_html
from django.views.defaults import server_error as default_server_error
from psycopg_pool import PoolTimeout, TooManyRequests


def server_error(request):
    exception = sys.exc_info()[1]
    seen = set()
    while exception is not None and id(exception) not in seen:
        seen.add(id(exception))
        if isinstance(exception, (PoolTimeout, TooManyRequests)):
            message = 'The service is busy. Please wait a few seconds and try again.'
            if request.path.startswith('/api/'):
                response = JsonResponse({'success': False, 'error': message, 'retryable': True}, status=503)
            elif request.method in {'GET', 'HEAD'} and 'text/html' in request.headers.get('Accept', ''):
                # A navigation can reach a busy instance even while another is
                # healthy. Retry safe page loads without replaying any POST.
                response = HttpResponse(format_html(
                    '<!doctype html><html lang="en"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>Please wait | PABASA</title><body>'
                    '<main style="max-width:32rem;margin:15vh auto;padding:1.5rem;font:1.1rem system-ui">'
                    '<h1>Please wait a moment</h1><p id="retry-message" role="status">'
                    'We are reconnecting to your page. Please keep this tab open.</p>'
                    '<p><a href="" id="retry-link">Try again</a></p></main>'
                    '<script src="{}"></script></body></html>',
                    static('pabasa_app/js/service_busy.js'),
                ), status=503)
            else:
                response = HttpResponse(message, status=503, content_type='text/plain')
            response['Retry-After'] = '5'
            response['Cache-Control'] = 'no-store'
            return response
        exception = exception.__cause__ or exception.__context__
    return default_server_error(request)
