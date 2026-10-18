"""Wait before Django creates a request thread or checks out a DB connection."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

_request_slot = ContextVar('pabasa_http_slot', default=None)


class _RequestSlot:
    def __init__(self, slots):
        self.slots = slots
        self.loop = asyncio.get_running_loop()
        self.held = True
        self.active = True

    def release(self):
        if self.held:
            self.held = False
            self.slots.release()

    async def resume(self):
        if not self.active:
            return False
        await self.slots.acquire()
        if not self.active:
            self.slots.release()
            return False
        self.held = True
        return True

    def close(self):
        self.active = False
        self.release()


@contextmanager
def provider_io(*, enabled=True):
    """A sync Django worker yields its slot only around external provider I/O.

    Context variables propagate through Django's ASGI sync worker. Reacquire
    before scoring/session middleware can use the database again. Direct WSGI
    calls and callers inside a transaction retain their existing lifecycle.
    """
    slot = _request_slot.get() if enabled else None
    if slot:
        slot.loop.call_soon_threadsafe(slot.release)
    try:
        yield
    finally:
        if slot:
            if slot.loop.is_closed():
                raise asyncio.CancelledError()
            resumed = asyncio.run_coroutine_threadsafe(slot.resume(), slot.loop).result()
            if not resumed:
                # The browser disconnected while the provider was working.
                raise asyncio.CancelledError()


class HttpAdmission:
    def __init__(self, pool_size=6):
        # Leave room for the single follow-up worker and speech authorization.
        self.limit = max(1, pool_size - 2)
        self._slots = asyncio.Semaphore(self.limit)

    @asynccontextmanager
    async def request(self, scope):
        path = scope.get('path', '')
        if path.startswith(('/static/', '/media/')):
            yield
        else:
            await self._slots.acquire()
            slot = _RequestSlot(self._slots)
            token = _request_slot.set(slot)
            try:
                yield
            finally:
                slot.close()
                _request_slot.reset(token)
