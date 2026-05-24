from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db


class StudentLabScore(db.Model):
    """Score for a student on a specific lab (subject component)."""

    __tablename__ = "student_lab_scores"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    student_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("students.id"), nullable=False, index=True
    )
    component_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("subject_components.id"), nullable=False, index=True
    )
    semester: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, index=True)
    score: so.Mapped[float | None] = so.mapped_column(sa.Float, nullable=True)
    updated_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    student: so.Mapped["Student"] = so.relationship(back_populates="lab_scores")
    component: so.Mapped["SubjectComponent"] = so.relationship(back_populates="scores")

    __table_args__ = (
        sa.UniqueConstraint(
            "student_id",
            "semester",
            "component_id",
            name="uq_student_lab_scores_student_semester_component",
        ),
    )
