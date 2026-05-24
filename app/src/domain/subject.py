from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so

from ..integrations.db import db


class Subject(db.Model):
    """Academic subject within a semester (e.g. Data Structures, semester 2)."""

    __tablename__ = "subjects"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    semester: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, index=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    short_code: so.Mapped[str | None] = so.mapped_column(sa.String(16), nullable=True)

    components: so.Mapped[list["SubjectComponent"]] = so.relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="SubjectComponent.sort_order",
    )

    __table_args__ = (
        sa.UniqueConstraint("semester", "name", name="uq_subjects_semester_name"),
    )
