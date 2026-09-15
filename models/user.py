class User:

    def __init__(self, name, birth_date, username, email, password_hash, descripcion=None):
        self.__name = name
        self.__birth_date = birth_date
        self.__username = username
        self.__email = email
        self.__password_hash = password_hash
        self.__descripcion = descripcion

    def get_name(self):
        return self.__name
    def get_birth_date(self):
        return self.__birth_date
    def get_username(self):
        return self.__username
    def get_password_hash(self):
        return self.__password_hash
    def get_email(self):
        return self.__email
    def get_descripcion(self):
        return self.__descripcion

    def set_name(self, name):
        self.__name = name
    def set_birth_date(self, birth_date):
        self.__birth_date = birth_date
    def set_username(self, username):
        self.__username = username
    def set_descripcion(self, descripcion):
        self.__descripcion = descripcion