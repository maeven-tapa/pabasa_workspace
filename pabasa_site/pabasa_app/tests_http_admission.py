import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from unittest.mock import patch

from asgiref.testing import ApplicationCommunicator
from django.core.asgi import get_asgi_application
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from django.urls import path

from django.test import SimpleTestCase

from pabasa_site.http_admission import HttpAdmission, provider_io
from . import views

urlpatterns = [path('api/reading/transcribe/', views.reading_transcribe_api),
               path('api/poll/', lambda request: JsonResponse({'success':True}))]


class HttpAdmissionTests(SimpleTestCase):
    async def test_thirty_page_loads_wait_before_entering_django(self):
        admission = HttpAdmission(pool_size=6)
        release = asyncio.Event()
        active = 0
        maximum = 0
        entered = 0

        async def page():
            nonlocal active, maximum, entered
            async with admission.request({'path':'/dashboard/assessment/'}):
                active += 1
                entered += 1
                maximum = max(maximum, active)
                await release.wait()
                await asyncio.sleep(0)
                active -= 1
                return 200

        tasks = [asyncio.create_task(page()) for _ in range(30)]
        await asyncio.sleep(0)
        self.assertEqual(entered, 4)
        release.set()
        self.assertEqual(await asyncio.gather(*tasks), [200] * 30)
        self.assertEqual(maximum, 4)
        self.assertEqual(entered, 30)

    async def test_thirty_waiting_recordings_do_not_block_polling_or_navigation(self):
        admission = HttpAdmission()
        release = threading.Event()
        started = 0
        lock = threading.Lock()
        workers = ThreadPoolExecutor(max_workers=30)

        def provider():
            nonlocal started
            with provider_io():
                with lock:
                    started += 1
                self.assertTrue(release.wait(10))

        async def recording():
            async with admission.request({'path':'/api/reading/transcribe/'}):
                await asyncio.get_running_loop().run_in_executor(workers,copy_context().run,provider)

        tasks = [asyncio.create_task(recording()) for _ in range(30)]
        try:
            async with asyncio.timeout(5):
                while started < 30:
                    await asyncio.sleep(.01)
            self.assertEqual(started, 30)
            async with asyncio.timeout(1):
                async with admission.request({'path':'/api/live-assessment/session/test/'}):
                    self.assertFalse(release.is_set())
                async with admission.request({'path':'/dashboard/assessment/'}):
                    self.assertFalse(release.is_set())
        finally:
            release.set()
            await asyncio.gather(*tasks)
            workers.shutdown(wait=True)

    async def test_cancellation_releases_the_slot(self):
        admission = HttpAdmission(pool_size=3)
        started = asyncio.Event()

        async def page():
            async with admission.request({'path':'/dashboard/assessment/'}):
                started.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(page())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        async with asyncio.timeout(1):
            async with admission.request({'path':'/dashboard/assessment/'}):
                pass

    async def test_late_provider_return_after_disconnect_cannot_leak_a_slot_or_grade(self):
        admission = HttpAdmission(pool_size=3)
        started,release,finished = threading.Event(),threading.Event(),threading.Event()
        graded = []

        def provider():
            try:
                with provider_io():
                    started.set()
                    release.wait(5)
                graded.append(True)
            finally:
                finished.set()

        async def request():
            async with admission.request({'path':'/api/reading/transcribe/'}):
                await asyncio.to_thread(provider)

        task = asyncio.create_task(request())
        async with asyncio.timeout(2):
            while not started.is_set(): await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        release.set()
        async with asyncio.timeout(2):
            while not finished.is_set(): await asyncio.sleep(.01)
            async with admission.request({'path':'/dashboard/assessment/'}):
                self.assertEqual(graded,[])

    @override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=[], ALLOWED_HOSTS=['testserver'],
                       GOOGLE_CLOUD_PROJECT_ID='synthetic')
    async def test_real_django_asgi_workers_release_slots_for_thirty_provider_waits(self):
        admission = HttpAdmission()
        django_app = get_asgi_application()
        release = threading.Event()
        started = 0
        lock = threading.Lock()

        async def application(scope, receive, send):
            async with admission.request(scope):
                await django_app(scope,receive,send)

        def recognize(*args, **kwargs):
            nonlocal started
            with lock:
                started += 1
            self.assertTrue(release.wait(10))
            return 'bata','chirp_3',''

        async def request(recording):
            if recording:
                source = RequestFactory().post('/api/reading/transcribe/',{
                    'audio':SimpleUploadedFile('synthetic.webm',b'audio',content_type='audio/webm'),
                    'target_text':'bata','mode':'reading','language':'Filipino'})
                body = source.body
                headers = [(b'content-type',source.META['CONTENT_TYPE'].encode()),
                           (b'content-length',str(len(body)).encode())]
            else:
                body,headers = b'',[]
            headers += [(b'host',b'testserver'),(b'origin',b'https://testserver'),
                (b'cookie',b'csrftoken='+b'a'*32),(b'x-csrftoken',b'a'*32),
                (b'x-pabasa-stt-provider',b'google'),(b'x-pabasa-stt-model',b'chirp_3')]
            communicator = ApplicationCommunicator(application,{
                'type':'http','http_version':'1.1','method':'POST' if recording else 'GET',
                'path':'/api/reading/transcribe/' if recording else '/api/poll/',
                'query_string':b'','headers':headers,'scheme':'https',
                'server':('testserver',443),'client':('127.0.0.1',1)})
            await communicator.send_input({'type':'http.request','body':body})
            start = await communicator.receive_output(timeout=15)
            while True:
                output = await communicator.receive_output(timeout=15)
                if not output.get('more_body'): break
            await communicator.wait(timeout=5)
            return start['status']

        with patch.object(views,'_check_auth',return_value=True), \
                patch.object(views,'_enforce_student_access_for_request',return_value=None), \
                patch.object(views,'transcribe_audio_bytes_with_model',side_effect=recognize):
            tasks = [asyncio.create_task(request(True)) for _ in range(30)]
            try:
                async with asyncio.timeout(5):
                    while started < 30:
                        await asyncio.sleep(.01)
                self.assertEqual(await asyncio.wait_for(request(False),1),200)
                self.assertFalse(release.is_set())
            finally:
                release.set()
                results = await asyncio.gather(*tasks)
            self.assertEqual(results,[200]*30)
