class User:

    def __init__(self, name, birth_date, username, password_hash):
        self.__name = name
        self.__birth_date = birth_date
        self.__username = username
        self.__password_hash = password_hash

    def get_name(self):
        return self.__name
    def get_birth_date(self):
        return self.__birth_date
    def get_username(self):
        return self.__username
    def get_password_hash(self):
        return self.__password_hash