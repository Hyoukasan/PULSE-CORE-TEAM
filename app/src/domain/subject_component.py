from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db


class SubjectComponent(db.Model):
    """Lab work slot within a subject (LR1, LR2, ...)."""

    __tablename__ = "subject_components"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    subject_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("subjects.id"), nullable=False, index=True
    )
    code: so.Mapped[str] = so.mapped_column(sa.String(16), nullable=False)
    title: so.Mapped[str | None] = so.mapped_column(sa.String(64), nullable=True)
    sort_order: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    subject: so.Mapped["Subject"] = so.relationship(back_populates="components")
    scores: so.Mapped[list["StudentLabScore"]] = so.relationship(
        back_populates="component",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.UniqueConstraint("subject_id", "code", name="uq_subject_components_subject_code"),
    )
