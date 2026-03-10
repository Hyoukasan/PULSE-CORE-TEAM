from werkzeug.security import generate_password_hash, check_password_hash

from ..integrations.db import db

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)


    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    role = db.relationship("Role", back_populates="users")

    username = db.Column(db.String(64), nullable=False,unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    ban_expires_at = db.Column(db.DateTime, default=None, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)