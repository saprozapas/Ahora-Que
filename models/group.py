class Group:

    def __init__(self, user_id, name, descripcion):
        self.__user_id = user_id
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