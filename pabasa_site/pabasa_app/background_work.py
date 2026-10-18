"""Bound optional ORM work without retaining a connection between callbacks.

This is an in-process queue, not a durable job broker. Assessment results must
be committed by the request before handing optional follow-ups to this queue.
"""
from concurrent.futures import ThreadPoolExecutor, wait
import logging
import threading

from django.db import close_old_connections, connections, transaction

logger = logging.getLogger(__name__)


class DatabaseWorkQueue:
    def __init__(self, capacity=64):
        # Reserve at most one DB connection for optional work in each process.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pabasa-followups')
        self._slots = threading.BoundedSemaphore(capacity)
        self._lock = threading.Lock()
        self._pending = set()

    def submit(self, callback, *, label):
        # Submission runs after commit. Release the request's idle connection
        # before applying backpressure, so producers cannot starve the worker.
        close_old_connections()
        self._slots.acquire()
        try:
            future = self._executor.submit(self._run, callback, label)
        except BaseException:
            self._slots.release()
            raise
        with self._lock:
            self._pending.add(future)
        future.add_done_callback(self._finished)
        return future

    @staticmethod
    def _run(callback, label):
        # Django HTTP cleanup does not run in this executor. Both boundaries
        # execute on the owning worker, including after an exception.
        try:
            connections.close_all()
            return callback()
        except Exception:
            logger.exception('Background follow-up failed: %s', label)
        finally:
            connections.close_all()

    def _finished(self, future):
        with self._lock:
            self._pending.discard(future)
        self._slots.release()

    def drain(self, timeout=None):
        """Wait for submitted work in tests/diagnostics without holding DB slots."""
        close_old_connections()
        with self._lock:
            pending = tuple(self._pending)
        return not wait(pending, timeout=timeout).not_done

    def shutdown(self):
        self._executor.shutdown(wait=True)


completion_work = DatabaseWorkQueue()


def queue_after_commit(callback, *, label):
    transaction.on_commit(lambda: completion_work.submit(callback, label=label))
