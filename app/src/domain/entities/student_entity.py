from ..config.database import database as db
from .models.student_model import Student


class studentEntity(Student, db.Model):
    __tablename__ = "core_student"

    idUser = db.Column(db.Integer, primary_key=True)
    idGroup = db.Column(db.Integer)
    email = db.Column(db.String(50))
    password = db.Column(db.String(350))
    banStatus = db.Column(db.Integer)
    person_id = db.Column(db.Integer, db.ForeignKey('core_person.idPerson'))

    def __init__(self, person):

        self.idUser = person.get('idUser')
        self.email = person.get('email')
        self.password = person.get('password')
        self.banStatus = person.get('banStatus')
        self.person_id = person.get('person')
        

    def update(self, person):

        self.email = person.email
        self.password = person.password
        self.banStatus = person.banStatus
        self.person_id = person.person