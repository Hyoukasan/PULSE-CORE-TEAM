from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy import ForeignKey

from ..integrations.db import db

class Group(db.Model):

    __tablename__ = "groups"

    id: so.Mapped[int] = so.mapped_column(sa.Integer(), primary_key=True)
    number: so.Mapped[str] = so.mapped_column(sa.String(16), nullable=False, unique=True)

    students: so.Mapped[list["Student"]] = so.relationship(back_populates="group")