"""Async sync worker: processes jobs from the message queue concurrently."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.config import get_settings
from app.database import get_session_factory, init_db
from app.queue import get_queue
from app.services import sync_service
from app.utils.logger import setup_logger


async def run_worker() -> None:
    """Consume jobs from the queue until interrupted.

    Each job runs in its own :class:`asyncio.Task`, bounded by a semaphore
    (``worker_concurrency``), so messages for different users are delivered in
    parallel instead of one-by-one.
    """
    await init_db()
    queue = get_queue()
    factory = get_session_factory()
    settings = get_settings()
    semaphore = asyncio.Semaphore(max(1, settings.worker_concurrency))
    tasks: set[asyncio.Task] = set()

    async def _process(job: dict[str, Any]) -> None:
        async with semaphore:
            try:
                async with factory() as session:
                    await sync_service.process_job(session, job)
            except Exception:  # noqa: BLE001 - keep the worker alive
                logger.exception("Unhandled error while processing job {}", job)

    logger.info(
        "Sync worker started (queue={}, concurrency={})",
        type(queue).__name__,
        settings.worker_concurrency,
    )
    try:
        while True:
            job = await queue.dequeue(timeout=1.0)
            if job is None:
                continue
            logger.debug(
                "[LATENCY] dequeue msg_id={} links={}",
                job.get("message", {}).get("message_id"),
                len(job.get("sync_link_ids", [])),
            )
            task = asyncio.create_task(_process(job), name="worker-job")
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    except asyncio.CancelledError:
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        await queue.close()


def main() -> None:
    """Entry point for ``python -m app.workers.sync_worker``."""
    setup_logger()
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
