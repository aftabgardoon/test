"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.config import get_settings
from app.database import dispose_engine, get_session_factory, init_db
from app.utils.logger import setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: init DB, then launch pollers and worker tasks."""
    del app
    setup_logger()
    await init_db()
    logger.info("Database initialised")

    settings = get_settings()
    tasks: list[asyncio.Task] = []

    # Warm-up: preload caches and warm HTTP connection pools.
    from app.pollers import build_polling_adapters
    from app.services.cache_service import cache_service

    warm_started = asyncio.get_running_loop().time()
    async with get_session_factory()() as session:
        await cache_service.warm_up(session)
    for platform, adapter in build_polling_adapters().items():
        if hasattr(adapter, "get_me"):
            try:
                await adapter.get_me()
            except Exception as exc:  # noqa: BLE001 - warm-up is best-effort
                logger.debug("Warm-up getMe failed for {}: {}", platform.value, exc)
    logger.info(
        "Warm-up completed in {:.1f}ms",
        (asyncio.get_running_loop().time() - warm_started) * 1000,
    )

    # Long-polling source listeners (Bale / Rubika).
    if settings.polling_enabled:
        from app.pollers import start_all_pollers

        adapters = build_polling_adapters()
        if adapters:
            tasks.extend(await start_all_pollers(adapters, get_session_factory()))
        else:
            logger.warning("No source bot tokens configured; polling is idle")

    # Manager bot (interactive) runs in-process when a token is configured.
    if settings.manager_bot_token:
        from app.bot_manager.manager import run_manager

        tasks.append(asyncio.create_task(run_manager()))

    # Run an in-process worker when Redis queue is disabled (local dev / tests).
    if not settings.queue_enabled:
        from app.workers.sync_worker import run_worker

        tasks.append(asyncio.create_task(run_worker()))

    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await dispose_engine()


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Health/liveness endpoint."""
    return {"status": "ok", "app": get_settings().app_name}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
