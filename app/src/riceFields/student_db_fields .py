from modules.core.domain.models.student_model import Student
from .person_db_fields import PersonDbFields
from ..use_cases import person_usecase
from typing import Dict, Union


class StudentDbFields:

    def __init__(self):
        self.person_db_fields = PersonDbFields()
        #self.person_usecase = person_usecase.PersonUseCase()

    def changeParamS(self, stud: Student, fields: any) -> None:

        if fields.get('idStudent'):
            stud.idStudent = fields.get('idStudent')
        else:
            stud.idStudent = None

        if fields.get('person'):
            stud.person = fields.get('person')
        else:
            stud.person = None

        if fields.get('idGroup'):
            stud.idGroup = fields.get('idGroup')
        else:
            stud.idGroup = None

        if fields.get('email'):
            stud.email = fields.get('email')
        else:
            stud.email = None

        if fields.get('password'):
            stud.password = fields.get('password')
        else:
            stud.password = None

        if fields.get('banStatus'):
            stud.banStatus = fields.get('banStatus')
        else:
            stud.banStatus = None

    def jsonToModel(self, fields: any) -> Student:
        stud = Student()

        if fields.idStudent:
            stud.idStudent = fields.idStudent
        else:
            stud.idStudent = None

        if fields.person:
            stud.person = self.person_db_fields.jsonToModel(fields.person)
        else:
            stud.person = None

        if fields.idGroup:
            stud.idGroup = fields.idGroup
        else:
            stud.idGroup = None

        if fields.email:
            stud.email = fields.email
        else:
            stud.email = None

        if fields.password:
            stud.password = fields.password
        else:
            stud.password = None

        if fields.banStatus:
            stud.banStatus = fields.banStatus
        else:
            stud.banStatus = None

        return stud

        
    def toJson(self, stud: Student) -> Dict[str, Union[str, None]]:
        return {
            "idStudent": stud.idStudent if stud.idStudent is not None else None,
            "person": self.person_factory.toJson(stud.person),
            "idGroup": stud.idGroup,
            "email": stud.email,
            "password": stud.password,
            "banStatus": stud.banStatus
        }
        
    def SaveToJson(self, student: Student) -> Dict[str, Union[str, None]]:
        return {
            "idStudent": student.idStudent if stud.idStudent is not None else None,
            "person": stud.person,
            "idGroup": stud.idGroup,
            "email": stud.email,
            "password": stud.password,
            "banStatus": stud.banStatus
        }