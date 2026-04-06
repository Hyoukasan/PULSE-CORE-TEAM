from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime
from typing import Optional

from ..integrations.db import db

class User(db.Model):

    __tablename__ = "users"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), nullable=False,unique=True)
    telegram_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, unique=True, nullable=True)

    role_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("roles.id"), nullable=False)
    role: so.Mapped["Role"] = so.relationship(back_populates="users")
    student_profile: so.Mapped[Optional["Student"]] = so.relationship(
        back_populates="user",
        uselist=False,
    )
    professor_profile: so.Mapped[Optional["Professor"]] = so.relationship(
        back_populates="user",
        uselist=False,
    )

    password_hash: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)

    ban_expires_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, default=None)


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)