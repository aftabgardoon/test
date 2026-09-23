"""Platform adapters and the adapter factory."""

from __future__ import annotations

from app.adapters.bale import BaleAdapter
from app.adapters.base import (
    AbstractAdapter,
    AdapterError,
    IncomingMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageType,
    Platform,
    TransientError,
)
from app.adapters.eitaa import EitaaAdapter
from app.adapters.rubika import RubikaAdapter
from app.config import get_settings

_ADAPTERS: dict[Platform, type[AbstractAdapter]] = {
    Platform.BALE: BaleAdapter,
    Platform.EITAA: EitaaAdapter,
    Platform.RUBIKA: RubikaAdapter,
}


def build_adapter(
    platform: str | Platform,
    token: str,
    *,
    rps: int | None = None,
    client=None,
) -> AbstractAdapter:
    """Instantiate the adapter for ``platform`` with ``token``.

    Raises:
        AdapterError: if the platform is unknown or the token is missing.
    """
    if isinstance(platform, str):
        try:
            platform = Platform(platform)
        except ValueError as exc:
            raise AdapterError(f"Unsupported platform: {platform!r}") from exc

    adapter_cls = _ADAPTERS.get(platform)
    if adapter_cls is None:
        raise AdapterError(f"Unsupported platform: {platform}")

    rate = rps if rps is not None else get_settings().rate_limit_rps
    return adapter_cls(token=token, rps=rate, client=client)


def platform_supports_source(platform: str | Platform) -> bool:
    """Whether ``platform`` can act as a sync *source* (no network access).

    Used by the manager bot to reject e.g. Eitaa channels as sources before
    the user configures them.  Instantiating the adapter with a probe token
    is safe: the HTTP client and the rate-limiter task are both created
    lazily, so nothing is opened or leaked.
    """
    if isinstance(platform, str):
        try:
            key = Platform(platform)
        except ValueError:
            return False
    else:
        key = platform
    adapter_cls = _ADAPTERS.get(key)
    if adapter_cls is None:
        return False
    return adapter_cls("probe").supports_source


__all__ = [
    "AbstractAdapter",
    "AdapterError",
    "BaleAdapter",
    "EitaaAdapter",
    "IncomingMessage",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "MessageType",
    "Platform",
    "RubikaAdapter",
    "TransientError",
    "build_adapter",
    "platform_supports_source",
]
