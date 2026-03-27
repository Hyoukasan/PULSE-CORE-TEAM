from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db

class Group(db.Model):

    __tablename__ = "groups"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    number: so.Mapped[str] = so.mapped_column(sa.String(16), nullable=False, unique=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(8), nullable=False, unique=True)

    students: so.Mapped[list["Student"]] = so.relationship(back_populates="group")
    professors: so.Mapped[list["Professor"]] = so.relationship(back_populates="group")