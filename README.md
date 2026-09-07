# Ahora-Que

Ahora-Que es un proyecto de aplicación web pensado para ayudar a grupos de personas a decidir juntos qué plan hacer. La idea principal es simplificar la organización de actividades sociales y recreativas considerando la disponibilidad de cada miembro, el presupuesto, el tiempo disponible y la ubicación.

## ¿De qué trata la app?

La aplicación permite que los usuarios:

- creen una cuenta e inicien sesión
- formen grupos con otros usuarios
- propongan planes o actividades
- vean cuánta gente está disponible para participar
- reciban recomendaciones basadas en varios criterios
- filtrar opciones según el tipo de grupo o contexto
- calificar los planes realizados
- consultar el historial de planes previos
- responder encuestas relacionadas con experiencias grupales

## Objetivo principal

El proyecto busca automatizar la recomendación de planes en base a datos del grupo, como:

- cantidad de personas disponibles
- presupuesto total o estimado
- horarios disponibles
- duración del plan
- distancia o cercanía del lugar
- tipo de plan: solo, con amigos, familia, pareja, etc.

La intención es que la app sugiera opciones útiles y realistas, evitando que la decisión sea improvisada o conflictiva.

## Funcionalidades previstas

### 1. Autenticación
- Registro de usuarios
- Inicio de sesión
- Cierre de sesión

### 2. Grupos
- Crear grupos entre usuarios
- Determinar automáticamente cuánta gente puede participar en un plan

### 3. Propuesta de planes
- Los usuarios pueden crear sus propios planes o sugerencias
- Los planes pueden tener distintos criterios de precio, ubicacion y duración

### 4. Recomendación por IA
- La aplicación evaluará condiciones del grupo para sugerir la mejor opción posible
- Se tomarán en cuenta presupuesto, horarios, disponibilidad y tiempo

### 5. Filtros
- Precio: CUSTOM, FREE, LOW, MID, HIGH
- Distancia: CUSTOM, NEARBY, FAR AWAY
- Tipo de grupo: SOLO, AMIGOS, FAMILIA, PAREJA, etc.

### 6. Calificaciones y historial
- Cada plan puede recibir puntaje con estrellas
- Se conserva un historial con los planes realizados y las valoraciones

### 7. Encuestas
- Se pueden generar encuestas para evaluar la experiencia grupal

## Estructura del repositorio

Este repositorio está organizado en módulos básicos para una aplicación Flask:

- `app.py`: punto de entrada principal de la app
- `database.py`: conexión a la base de datos
- `models/`: modelos de datos, como el usuario
- `routes/`: rutas y blueprints de la aplicación
- `services/`: lógica de negocio, por ejemplo autenticación
- `templates/`: plantillas HTML para la interfaz
- `static/`: archivos estáticos como CSS, JS e imágenes

## Tecnologías esperadas

El proyecto está basado en Python con Flask y usa PostgreSQL/Supabase para persistencia.

## Estado actual

El repositorio tiene una base inicial con:

- estructura de Flask
- conexión a base de datos
- modelo de usuario
- registro de usuarios en una ruta de autenticación
- archivos base para continuar desarrollando la aplicación

Todavía faltan varias partes del sistema para completarse, pero la base sirve como punto de partida para implementar la funcionalidad principal del proyecto.

## Resumen breve

Ahora-Que busca convertirse en una herramienta para decidir en grupo qué hacer, reduciendo la fricción de coordinar disponibilidad, presupuesto y preferencias, y usando recomendaciones inteligentes para facilitar la elección.
