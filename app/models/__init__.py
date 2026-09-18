"""SQLAlchemy models package.

Importing this package registers every model on ``Base.metadata`` so that
Alembic autogenerate and ``Base.metadata.create_all`` see them.
"""

from app.models.bot_token import BotToken
from app.models.channel import Channel
from app.models.message_log import MessageLog
from app.models.sync_link import SyncLink
from app.models.user import User

__all__ = [
    "BotToken",
    "Channel",
    "MessageLog",
    "SyncLink",
    "User",
]
