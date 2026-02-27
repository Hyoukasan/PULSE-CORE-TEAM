class Person:

    __idPerson: int
    __firstName: str
    __secondName: str
    __lastName: str
    __platform: str


    @property
    def idperson(self):
        return self.__idPerson

    @idperson.setter
    def idperson(self, value: int):
        self.__idPerson = value

    @property
    def firstname(self):
        return self.__firstName

    @firstname.setter
    def firstname(self, value: str):
        self.__firstName = value

    @property
    def lastname(self):
        return self.__lastName

    @lastname.setter
    def lastname(self, value: str):
        self.__lastName = value

    @property
    def platform(self):
        return self.__platform

    @platform.setter
    def platform(self, value: str):
        self.__platform = value

    @property
    def fullname(self):
        return f"{self.__firstName or None} {self.__lastName or None}"