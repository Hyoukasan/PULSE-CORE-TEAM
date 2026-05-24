from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from datetime import datetime
from typing import Optional

from ..integrations.db import db
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


class Message(db.Model):

    __tablename__ = "messages"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    external_id: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128), unique=True, nullable=True)
    message_type: so.Mapped[str] = so.mapped_column(sa.String(32), nullable=False, default="text")
    text: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    status: so.Mapped[str] = so.mapped_column(sa.String(32), nullable=False, default="pending")
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, nullable=False, default=datetime.utcnow)

    sender: so.Mapped["User"] = so.relationship(
        "User",
        foreign_keys=[sender_id],
        backref="sent_messages",
    )
    recipient: so.Mapped["User"] = so.relationship(
        "User",
        foreign_keys=[recipient_id],
        backref="received_messages",
    )
