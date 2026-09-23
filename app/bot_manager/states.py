"""Lightweight per-user state machine for the manager bot.

A simple in-memory FSM keyed by ``(platform, user_id)``. For a multi-worker
deployment this should be replaced by a Redis-backed FSM (e.g. aiogram's FSM
or a custom key/value store); for the single-process MVP it is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class States:
    """Known conversation states."""

    IDLE = "idle"
    AWAIT_CHANNEL_PLATFORM = "await_channel_platform"
    AWAIT_CHANNEL_ID = "await_channel_id"
    AWAIT_SOURCE_SELECT = "await_source_select"
    AWAIT_DEST_SELECT = "await_dest_select"
    AWAIT_LINK_TOGGLE = "await_link_toggle"
    CONFIRM_DELETE_CHANNEL = "confirm_delete_channel"


@dataclass
class UserContext:
    """Transient data associated with a user conversation."""

    state: str = States.IDLE
    data: dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """In-memory store of per-user conversation contexts."""

    def __init__(self) -> None:
        self._users: dict[tuple[str, str], UserContext] = {}

    def _key(self, platform: str, user_id: str) -> tuple[str, str]:
        return (platform, user_id)

    def get(self, platform: str, user_id: str) -> UserContext:
        """Return the context for a user, creating it on demand."""
        key = self._key(platform, user_id)
        if key not in self._users:
            self._users[key] = UserContext()
        return self._users[key]

    def set_state(
        self,
        platform: str,
        user_id: str,
        state: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Set the state, replacing any stale context data from a previous flow.

        Data is *replaced* (not merged) so that e.g. a leftover ``source_id``
        from an interrupted ``/adddest`` flow can never leak into a fresh
        ``/setsource`` flow.

        ``data`` is an explicit dict (not ``**kwargs``) on purpose: a
        ``**data`` signature collides with the ``platform``/``user_id``
        parameter names — ``set_state(p, u, s, platform="bale")`` raised a
        ``TypeError`` that silently killed the platform-picker buttons.
        """
        ctx = self.get(platform, user_id)
        ctx.state = state
        ctx.data.clear()
        if data:
            ctx.data.update(data)

    def reset(self, platform: str, user_id: str) -> None:
        """Clear the user's state and data."""
        ctx = self.get(platform, user_id)
        ctx.state = States.IDLE
        ctx.data.clear()


state_machine = StateMachine()
