from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db

class Professor(db.Model):
    __tablename__ = "professors"

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    group_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("groups.id"), nullable=False)

    user: so.Mapped["User"] = so.relationship(back_populates="professor_profile")
    group: so.Mapped["Group"] = so.relationship(back_populates="professors")

