from .base import Person

class Student:

    __idStudent: int
    __person: Person
    __idGroup: int
    __password: str
    __banned: bool

    @property
    def idstudent(self):
        return self.__idStudent

    @idstudent.setter
    def idstudent(self, value: int):
        self.__idStudent = value

    @property
    def person(self):
        return self.__person

