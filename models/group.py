class Group:

    def __init__(self, name, usuarios):
        self.__name = name
        self.__usuarios = usuarios
        
    def get_name(self):
        return self.__name
    def get_usuarios(self):
        return self.__usuarios