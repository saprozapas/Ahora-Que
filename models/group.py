class Group:
    def __init__(self, name, descripcion, id=None):
        self.__name = name
        self.__descripcion = descripcion
        self.__id = id

    def get_id(self):
        return self.__id

    def get_name(self):
        return self.__name

    def get_description(self):
        return self.__descripcion
