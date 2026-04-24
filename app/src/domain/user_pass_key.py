import sqlalchemy as sa
import sqlalchemy.orm as so
from ..integrations.db import db

class UserPassKey(db.Model):
    __tablename__ = "user_pass_keys"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), unique=True, nullable=False)
    pass_key: so.Mapped[str] = so.mapped_column(sa.String(128), unique=True, nullable=False)
