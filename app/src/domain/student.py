from __future__ import annotations


import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy import ForeignKey

from ..integrations.db import db

class Student(db.Model):

    __tablename__ = "students"

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    group_id: so.Mapped[int] = so.mapped_column(ForeignKey("groups.id"), nullable=False)

    user: so.Mapped["User"] = so.relationship(back_populates="students")
    group: so.Mapped["Group"] = so.relationship(back_populates="students")

