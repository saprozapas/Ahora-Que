class Group:

    def __init__(self, user, name, descripcion):
        self.__user = user
        self.__name = name
        self.__descripcion = descripcion
        self.__usuarios = []
        
    def get_name(self):
        return self.__name
    def get_usuarios(self):
        return self.__usuarios
    def get_descripcion(self):
        return self.__descripcion
    def add_usuario(self, usuario):
        self.__usuarios.append(usuario)
    def get_user(self):
        return self.__user