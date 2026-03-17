from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db

class Role(db.Model):

    __tablename__ = "roles"

    id: so.Mapped[int] = so.mapped_column(sa.Integer(), primary_key=True)
    role: so.Mapped[str] = so.mapped_column(db.String(16), unique=True, nullable=False)

    users: so.Mapped[list["User"]] = so.relationship(back_populates="role")