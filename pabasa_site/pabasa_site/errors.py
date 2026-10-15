"""Return a retryable response when the bounded database pool is busy."""
import sys

from django.http import HttpResponse, JsonResponse
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
            else:
                response = HttpResponse(message, status=503, content_type='text/plain')
            response['Retry-After'] = '5'
            return response
        exception = exception.__cause__ or exception.__context__
    return default_server_error(request)
