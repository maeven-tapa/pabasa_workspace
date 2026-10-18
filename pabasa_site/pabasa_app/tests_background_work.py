from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import TransactionTestCase

from .background_work import DatabaseWorkQueue, queue_after_commit


class BackgroundWorkTests(TransactionTestCase):
    def test_thirty_callbacks_share_one_worker_and_release_connections_after_errors(self):
        queue = DatabaseWorkQueue()
        self.addCleanup(queue.shutdown)
        owners, entries, exits = set(), [], []
        original_close = connections.close_all

        def close():
            original_close()
            # Django deliberately keeps shared in-memory SQLite test handles
            # open. Force the owning worker's handle closed in this probe;
            # the main test handle keeps the disposable database alive.
            if threading.get_ident() != main_thread and connection.vendor == 'sqlite':
                BaseDatabaseWrapper.close(connection)
            exits.append((threading.get_ident(), connection.connection is None))

        def callback(index):
            owners.add(threading.get_ident())
            entries.append(connection.connection is None)
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                self.assertEqual(cursor.fetchone()[0], 1)
            if index == 12:
                raise RuntimeError('synthetic follow-up failure')
            return index

        main_thread = threading.get_ident()
        with patch('pabasa_app.background_work.connections.close_all', side_effect=close), \
                self.assertLogs('pabasa_app.background_work', level='ERROR'):
            futures = [queue.submit(lambda i=i: callback(i), label='test') for i in range(30)]
            self.assertTrue(queue.drain(timeout=20))
            self.assertEqual([future.result() for future in futures],
                             [i if i != 12 else None for i in range(30)])
        self.assertEqual(len(owners), 1)
        self.assertNotIn(threading.get_ident(), owners)
        self.assertEqual(entries, [True] * 30)
        self.assertTrue(all(closed for owner, closed in exits if owner in owners))
        self.assertEqual(sum(owner in owners for owner, closed in exits), 60)

    def test_followups_only_submit_after_successful_commit(self):
        callback = lambda: None
        with patch('pabasa_app.background_work.completion_work.submit') as submit:
            with transaction.atomic():
                queue_after_commit(callback, label='committed')
                submit.assert_not_called()
            submit.assert_called_once_with(callback, label='committed')
            submit.reset_mock()
            with self.assertRaises(ValueError), transaction.atomic():
                queue_after_commit(callback, label='rolled_back')
                raise ValueError('rollback')
            submit.assert_not_called()

    def test_saturated_queue_applies_backpressure_without_dropping_work(self):
        queue = DatabaseWorkQueue(capacity=1)
        self.addCleanup(queue.shutdown)
        started, release, submitted = threading.Event(), threading.Event(), threading.Event()

        def blocked():
            started.set()
            self.assertTrue(release.wait(5))

        first = queue.submit(blocked, label='first')
        self.assertTrue(started.wait(5))
        def producer():
            future = queue.submit(lambda: 'second', label='second')
            submitted.set()
            return future
        with ThreadPoolExecutor(max_workers=1) as producer_pool:
            pending = producer_pool.submit(producer)
            try:
                self.assertFalse(submitted.wait(.05))
            finally:
                release.set()
            self.assertEqual(pending.result(5).result(5), 'second')
        first.result(5)
