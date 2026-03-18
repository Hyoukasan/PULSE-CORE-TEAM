from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db

class Professor(db.Model):
    __tablename__ = "professor"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey("users.id"), primary_key=True)

