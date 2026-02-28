from .person import Person

class Student(Person):

    __idStudent: int
    __idGroup: int
    __password: str
    __banStatus: int

    @property
    def idstudent(self):
        return self.__idStudent

    @idstudent.setter
    def idstudent(self, value: int):
        self.__idStudent = value

    @property
    def idGroup(self):
        return self.__idGroup

    @idGroup.setter
    def idGroup(self, value: int):
        self.__idGroup = value

    @property
    def password(self):
        return self.__passwor

    @password.setter
    def password(self, value: str):
        self.__password = value

    @property
    def banStatus(self):
        return self.banStatus

    @banStatus.setter
    def banStatus(self, value: int):
        self.__banStatus = value