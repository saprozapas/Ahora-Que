class SolicitudAmistad:
    def __init__(self, id_solicitante, nombre_solicitante, username_solicitante):
        self.__id_solicitante = id_solicitante
        self.__nombre_solicitante = nombre_solicitante
        self.__username_solicitante = username_solicitante

    def get_id_solicitante(self):
        return self.__id_solicitante

    def get_nombre_solicitante(self):
        return self.__nombre_solicitante

    def get_username_solicitante(self):
        return self.__username_solicitante
