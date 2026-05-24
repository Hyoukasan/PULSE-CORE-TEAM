from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db


class LectureSession(db.Model):
    """Scheduled lecture date for a semester (column headers in attendance sheet)."""

    __tablename__ = "lecture_sessions"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    semester: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, index=True)
    session_date: so.Mapped[sa.Date] = so.mapped_column(sa.Date, nullable=False)

    attendance_records: so.Mapped[list["AttendanceRecord"]] = so.relationship(
        back_populates="lecture_session",
    )

    __table_args__ = (
        sa.UniqueConstraint("semester", "session_date", name="uq_lecture_sessions_semester_date"),
    )
