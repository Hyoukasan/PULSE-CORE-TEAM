from __future__ import annotations


import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy import ForeignKey
from typing import Optional

from ..integrations.db import db

class Student(db.Model):

    __tablename__ = "students"

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    group_id: so.Mapped[int] = so.mapped_column(ForeignKey("groups.id"), nullable=False)
    pass_id: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), unique=True, nullable=True)
    missed_passes: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    user: so.Mapped["User"] = so.relationship(back_populates="student_profile")
    group: so.Mapped["Group"] = so.relationship(back_populates="students")
    attendance_records: so.Mapped[list["AttendanceRecord"]] = so.relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="joined",
    )

