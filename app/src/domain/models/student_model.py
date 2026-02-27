from .person import Person

class Student:

    __idStudent: int
    __person: Person
    __idGroup: int
    __password: str
    __banStatus: bool

    @property
    def idstudent(self):
        return self.__idStudent

    @idstudent.setter
    def idstudent(self, value: int):
        self.__idStudent = value

    @property
    def person(self):
        return self.__person

    @person.setter
    def person(self, value: Person):
        self.__person = value

    @property
    def idGroup(self):
        return self.__idGroup

    @idGroup.setter
    def idGroup(self, value: int):
        self.__idGroup = value

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, value: str):
        self.__password = value

    @property
    def banStatus(self):
        return self.banStatus

    @banStatus.setter
    def banStatus(self, value: bool):
        self.__banStatus = value