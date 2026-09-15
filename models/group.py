class Group:

    def __init__(self, user, name, descripcion, id=None):
        self.__user = user
        self.__name = name
        self.__descripcion = descripcion
        self.__usuarios = []
        self.__id = id

    def get_id(self):
        return self.__id

    def get_name(self):
        return self.__name
    def get_user(self):
        return self.__user
    def set_user(self, user):
        self.__user = user
    def get_usuarios(self):
        return self.__usuarios
    def get_description(self):
        return self.__descripcion
    def add_usuario(self, usuario):
        self.__usuarios.append(usuario)
