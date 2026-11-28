import uuid
from contextlib import contextmanager

from django.core.cache import cache


@contextmanager
def cache_lock(key: str, timeout: int):
    """Non-blocking lock built on cache.add (atomic on Redis/Memcached).

    Yields True if we got the lock, False if someone else holds it.
    `timeout` is a safety expiry so a crashed worker can't hold it forever;
    keep it longer than the task's hard time limit.
    The cache MUST be shared between workers (Redis), not LocMemCache.
    """
    token = uuid.uuid4().hex
    acquired = cache.add(key, token, timeout)
    try:
        yield acquired
    finally:
        # Only release a lock we own (it may have expired and been re-taken).
        if acquired and cache.get(key) == token:
            cache.delete(key)
