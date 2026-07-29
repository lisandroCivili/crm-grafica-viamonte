"""Lo que el sistema tiene que dejar listo cada vez que arranca.

Son dos cosas: que haya con qué entrar, y que el esquema de la base esté al
día. En un servidor la base nace vacía o ya viene con datos reales de antes, y
no hay consola donde correr a mano ni migraciones/migracion_usuarios.py (pide
contraseñas por teclado) ni los scripts de migraciones/ que agregan columnas
(ALTER TABLE). Sin esto, el sistema queda deployado y con la puerta cerrada
para todos, o tirando 500 en cualquier pantalla que toque la columna nueva.
"""
import os

from sqlalchemy import text
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


def aplicar_migraciones_pendientes() -> None:
    """Suma al esquema las columnas que create_all() no pudo agregar solo.

    create_all() (main.py) sólo crea tablas que no existen: nunca agrega
    columnas a una tabla ya creada (ver migraciones/README.md). En la compu
    del taller eso se corre a mano, con el backend apagado; en Railway no hay
    consola para eso, así que el propio arranque revisa el esquema real
    contra el que espera el código y aplica lo que falte.
    """
    db = SessionLocal()
    try:
        _migrar_columna_archivado(db)
    finally:
        db.close()


def _migrar_columna_archivado(db: Session) -> None:
    """Agrega trabajos.archivado si la base todavía no la tiene.

    Mismo cambio que migraciones/migracion_archivo_kanban.py (ahí está el
    detalle de negocio de por qué se archivan los ya entregados); se repite
    acá porque el servidor no tiene consola donde invocar ese script a mano.

    Idempotente: si la columna ya existe, no toca nada.
    """
    columnas = {fila[1] for fila in db.execute(text("PRAGMA table_info(trabajos)"))}
    if "archivado" in columnas:
        return

    db.execute(text("ALTER TABLE trabajos ADD COLUMN archivado BOOLEAN DEFAULT 0"))
    db.execute(text("UPDATE trabajos SET archivado = 0 WHERE archivado IS NULL"))
    db.execute(text(
        "UPDATE trabajos SET archivado = 1 WHERE estado = 'Entregado' AND archivado = 0"
    ))
    db.commit()
