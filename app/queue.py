"""Message queue abstraction.

Supports two backends:

* **Redis** (production, when ``QUEUE_ENABLED=true``): a simple list-based
  queue using ``LPUSH``/``BRPOP``. Swap for ``arq``/``Celery`` if you need
  scheduling or retries inside the broker.
* **In-memory** (dev/tests): an ``asyncio.Queue`` shared within the process.

Jobs are JSON-serialisable dictionaries.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any

from app.config import get_settings


class BaseQueue:
    """Minimal queue interface used by the sync engine and the worker."""

    async def enqueue(self, item: dict[str, Any]) -> None:
        """Push ``item`` onto the queue."""
        raise NotImplementedError

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """Pop an item, blocking up to ``timeout`` seconds, or ``None``."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release underlying resources."""


class MemoryQueue(BaseQueue):
    """In-process queue backed by ``asyncio.Queue``."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def enqueue(self, item: dict[str, Any]) -> None:
        await self._queue.put(item)

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def close(self) -> None:
        return None


class RedisQueue(BaseQueue):
    """Redis list-backed queue."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)
        self._key = "syncbot:jobs"

    async def enqueue(self, item: dict[str, Any]) -> None:
        await self._redis.lpush(self._key, json.dumps(item))

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        # BRPOP treats timeout=0 as "block forever" — clamp to at least 1s.
        result = await self._redis.brpop(self._key, timeout=max(1, int(timeout)))
        if result is None:
            return None
        return json.loads(result[1])

    async def close(self) -> None:
        await self._redis.aclose()


@lru_cache
def get_queue() -> BaseQueue:
    """Return the configured queue instance (cached)."""
    settings = get_settings()
    if settings.queue_enabled:
        return RedisQueue(settings.redis_url)
    return MemoryQueue()
