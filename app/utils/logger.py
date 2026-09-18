"""Logging configuration built on top of ``loguru``.

All logs go to stderr (terminal only) with a compact, colourised format.
Sensitive values (tokens) are never logged — callers must redact them first
(see :mod:`app.utils.crypto`).
"""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger

from app.config import get_settings

_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | "
    "<level>{level: <7}</level> | "
    "<cyan>{name}</cyan> | "
    "<level>{message}</level>"
)


def setup_logger() -> None:
    """Configure the global ``loguru`` logger (terminal-only, colourful)."""
    settings = get_settings()
    level = "DEBUG" if settings.debug else "INFO"

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        enqueue=True,
        backtrace=settings.debug,
        diagnose=settings.debug,
        format=_FORMAT,
    )


def log_user_event(platform: str, user_id: str, action: str, **extra: Any) -> None:
    """Log a single user action in a clean, colourful way.

    Example::

        log_user_event("bale", "123", "addchannel", platform="bale", id="@foo")
    """
    parts = [f"{key}={value}" for key, value in extra.items()]
    suffix = f" | {' '.join(parts)}" if parts else ""
    logger.info(
        "<magenta>[USER]</magenta> <yellow>{}</yellow>@<cyan>{}</cyan> {}<dim>{}</dim>",
        user_id,
        platform,
        action,
        suffix,
    )
