"""Lo que el sistema tiene que dejar listo cada vez que arranca.

Hoy es una sola cosa: que haya con qué entrar. En un servidor la base nace vacía
y no hay consola donde correr migraciones/migracion_usuarios.py (ese script pide
las contraseñas por teclado, que es lo correcto en la compu del taller pero
imposible en un contenedor). Sin esto, el sistema queda deployado y con la
puerta cerrada para todos.
"""
import os

from sqlalchemy.orm import Session

import models
from database import SessionLocal
from seguridad import ROL_ADMIN, ROL_ENCARGADO, ROL_MOSTRADOR, hashear_password

# Quién entra al sistema y de qué variable de entorno sale su contraseña la
# primera vez. Son los mismos tres de migracion_usuarios.py: el nombre es la
# persona y el rol es el puesto.
USUARIOS_INICIALES = [
    ("facundo", ROL_ADMIN, "CLAVE_INICIAL_FACUNDO"),
    ("marcos", ROL_ENCARGADO, "CLAVE_INICIAL_MARCOS"),
    ("lucio", ROL_MOSTRADOR, "CLAVE_INICIAL_LUCIO"),
]


def sembrar_usuarios_iniciales() -> list[str]:
    """Da de alta a los usuarios que falten, contra la base del sistema."""
    db = SessionLocal()
    try:
        return _sembrar(db)
    finally:
        db.close()


def _sembrar(db: Session) -> list[str]:
    """Crea los usuarios que falten y tengan contraseña configurada.

    Se saltea a los que ya existen, así que arrancar mil veces da lo mismo que
    arrancar una: no pisa contraseñas ni roles de nadie.

    Las variables de entorno se borran apenas se verifica que los tres pueden
    entrar. Mientras sigan definidas, un usuario dado de baja y borrado a
    propósito volvería a aparecer en el próximo reinicio.

    Devuelve los nombres creados (para el log). NUNCA se loguea una contraseña.
    """
    creados = []
    for nombre, rol, variable in USUARIOS_INICIALES:
        password = os.getenv(variable)
        if not password:
            continue

        ya_existe = db.query(models.Usuario).filter(models.Usuario.nombre == nombre).first()
        if ya_existe:
            continue

        db.add(models.Usuario(
            nombre=nombre,
            password_hash=hashear_password(password),
            rol=rol,
        ))
        db.commit()
        creados.append(nombre)

    return creados
