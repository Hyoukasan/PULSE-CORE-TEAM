from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime

from ..integrations.db import db


class AttendanceRecord(db.Model):

    __tablename__ = "attendance_records"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    student_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("students.id"), nullable=False, index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(sa.DateTime, nullable=False, default=datetime.utcnow)

    student: so.Mapped["Student"] = so.relationship(back_populates="attendance_records")
