from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db

class Professor(db.Model):
    __tablename__ = "professors"

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    group_is: so.Mapped[str] = so.mapped_column(sa.String(16), sa.ForeignKey("groups.id"), nullable=False)

    group: so.Mapped[list["Group"]] = so.relationship(back_populates="professors")

