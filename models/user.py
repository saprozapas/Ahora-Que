class User:

    def __init__(self, name, birth_date, username, email, password_hash, description=None):        
        self.__name = name
        self.__birth_date = birth_date
        self.__username = username
        self.__email = email
        self.__password_hash = password_hash
        self.__description = description

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
    def get_description(self):
        return self.__description

    def set_name(self, name):
        self.__name = name
    def set_birth_date(self, birth_date):
        self.__birth_date = birth_date
    def set_username(self, username):
        self.__username = username
    def set_description(self, description):
        self.__description = description