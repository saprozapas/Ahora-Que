class Invitacion:
    def __init__(self, group_id, nombre_grupo, mensaje, nombre_invitante):
        self.__group_id = group_id
        self.__nombre_grupo = nombre_grupo
        self.__mensaje = mensaje
        self.__nombre_invitante = nombre_invitante

    def get_group_id(self):
        return self.__group_id

    def get_nombre_grupo(self):
        return self.__nombre_grupo

    def get_mensaje(self):
        return self.__mensaje

    def get_nombre_invitante(self):
        return self.__nombre_invitante