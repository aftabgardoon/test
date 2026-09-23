"""Service layer: business logic for users, channels, tokens and sync.

Note: ``cache_service`` is intentionally imported as the *singleton
instance* (``app.services.cache_service.cache_service``), which shadows the
submodule name in this package.  Callers use it via
``from app.services import cache_service`` and invoke its methods
(``get_source_channel``, ``invalidate_links``, ``warm_up``, ...).  Importing
the submodule instead (the old behaviour) made every such call raise
``AttributeError`` — which is exactly what silently killed several manager
bot buttons and the whole sync pipeline.
"""

from app.services import (
    access_service,
    channel_service,
    sync_service,
    token_service,
    user_service,
)
from app.services.cache_service import cache_service  # noqa: F401  (singleton instance)

__all__ = [
    "access_service",
    "cache_service",
    "channel_service",
    "sync_service",
    "token_service",
    "user_service",
]
