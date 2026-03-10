from ..integrations.db import db

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    role = db.relationship("Role", back_populates="users")

    username = db.Column(db.String(80), nullable=False,unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
