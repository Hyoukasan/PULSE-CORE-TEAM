from config.database import database as db

class PersonEntity():
    __tablename__ = "core_person"
    
    idPerson = db.Column(db.Integer, primary_key = True, autoincrement = True)
    firstName = db.Column(db.String(50))
    secondName = db.Column(db.String(50))
    lastName = db.Column(db.String(50))
    platform = db.Column(db.String(50))
    usuarios = db.relationship('UserEntity', backref = 'person', uselist = False, lazy = True)
    
    
    def __init__(self, person):
        
        self.idPerson = person.get('idPerson')
        self.firstName = person.get('firstName')
        self.secondName = person.get('secondName')
        self.lastName = person.get('lastName')
        self.lastName = person.get('platform')
        
    def update(self, person):
        
        self.firstName = person.firstName
        self.secondName = person.secondName
        self.lastName = person.lastName
        self.platform = person.platform