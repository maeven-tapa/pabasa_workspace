from django.db import OperationalError
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path
from psycopg_pool import PoolTimeout, TooManyRequests

handler500 = 'pabasa_site.errors.server_error'


def busy(request):
    try:
        raise PoolTimeout('synthetic pool capacity')
    except PoolTimeout as error:
        raise OperationalError('synthetic database wrapper') from error


def full(request):
    raise TooManyRequests('synthetic queue capacity')


def unrelated(request):
    raise ValueError('synthetic unrelated failure')


urlpatterns = [path('api/busy/', busy), path('api/full/', full),
               path('busy/', busy), path('other/', unrelated)]


@override_settings(DEBUG=False, ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], MIDDLEWARE=[])
class DatabaseCapacityResponseTests(SimpleTestCase):
    def test_pool_limits_return_retryable_503_through_django_exception_handling(self):
        for route in ('/api/busy/', '/api/full/'):
            with self.subTest(route=route):
                response = Client(raise_request_exception=False).get(route)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response['Retry-After'], '5')
                self.assertTrue(response.json()['retryable'])
                self.assertFalse(response.json()['success'])

    def test_busy_page_uses_plain_retry_message(self):
        response = Client(raise_request_exception=False).get('/busy/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'pool', response.content)

    def test_busy_html_navigation_retries_but_post_is_never_replayed(self):
        client = Client(raise_request_exception=False)
        response = client.get('/busy/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'service_busy.js', response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        response = client.post('/busy/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'<script', response.content)

    def test_unrelated_exceptions_remain_server_errors(self):
        response = Client(raise_request_exception=False).get('/other/')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('Retry-After', response)
