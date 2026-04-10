from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime
from typing import Optional

from ..integrations.db import db


class AttendanceExcuse(db.Model):

    __tablename__ = "attendance_excuses"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), nullable=False, index=True)
    reason: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    file_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(255), nullable=True)
    timestamp: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, nullable=False, default=datetime.utcnow)
