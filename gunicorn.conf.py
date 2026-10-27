"""Configuración de gunicorn para Render.

Gunicorn lee este archivo solo (está en la carpeta desde donde se lo arranca), así que no hace falta cambiar el
comando de inicio (`gunicorn app:app`). Cada pedido pasa casi todo el tiempo esperando a la base de datos, por eso se
usan hilos: con un solo proceso "sync" cada espera frena a todos los demás usuarios.
"""

import os

bind = "0.0.0.0:" + os.environ.get("PORT", "10000")

# Pocos procesos (la instancia de Render es chica) y muchos hilos (el trabajo es esperar a la base).
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "8"))

# Carga la app una vez y la comparte con los procesos: arranca más rápido y gasta menos memoria.
preload_app = True

# Mantiene abiertas las conexiones del navegador (Render las corta a los ~75 s) y no deja colgado un pedido lento.
keepalive = 75
timeout = 60
graceful_timeout = 20

# Un proceso que lleva mucho tiempo vivo se recicla de a poco: evita que la memoria crezca sin parar.
max_requests = 1500
max_requests_jitter = 150

# El log de acceso de gunicorn duplica el que ya imprime la app.
accesslog = None
