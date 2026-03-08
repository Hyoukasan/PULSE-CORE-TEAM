
from ..integrations.db import db

class User(db.Model):

    __tablename__ = "users"

    id = db.Collumn(db.Intager, primary_key=True)
    username = db.Collumn(db.String(80),nullable=False,enique=True)

