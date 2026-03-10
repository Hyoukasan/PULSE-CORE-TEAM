from ..integrations.db import db

class Role(db.Model):

    __tablename__ = "roles"

    id = db.Column(db.Integer(), primary_key=True)
    user_role = db.Column(db.String(), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")
    title = db.Column(db.String(100))