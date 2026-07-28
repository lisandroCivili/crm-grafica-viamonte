"""
Migración única: crea la tabla de usuarios y da de alta a los del taller.

POR QUÉ ES NECESARIA
--------------------
Antes el login comparaba contra un usuario y una contraseña escritos en el
código. Ahora los usuarios viven en la base: sin correr esto, nadie puede
entrar al sistema.

A diferencia de las otras migraciones, acá no hay ALTER TABLE: la tabla
'usuarios' es nueva y create_all() la crea sola. Lo que este script agrega es
dar de alta a las personas con su contraseña hasheada.

LAS CONTRASEÑAS SE TIPEAN ACÁ
-----------------------------
Se piden por consola y sólo se guarda el hash. Ninguna contraseña queda escrita
en el repositorio, que es público.

Es IDEMPOTENTE: a los usuarios que ya existen los saltea, así que se puede
correr de nuevo para agregar a alguien sin tocar a los demás.

CÓMO CORRERLO (desde la raíz del proyecto, con el backend apagado):
    python -m migraciones.migracion_usuarios
"""
import getpass
import os
import shutil
from datetime import datetime

from database import Base, SessionLocal, engine
from rutas import DIR_DATOS
from seguridad import ROL_ADMIN, ROL_ENCARGADO, ROL_MOSTRADOR, hashear_password
import models

DB_PATH = os.path.join(DIR_DATOS, "viamonte.db")

# Quién entra al sistema y con qué puesto. El nombre es la persona; el rol es el
# puesto. Para dar de alta a alguien más, se agrega acá y se vuelve a correr.
USUARIOS_INICIALES = [
    ("facundo", ROL_ADMIN),
    ("marcos", ROL_ENCARGADO),
    ("lucio", ROL_MOSTRADOR),
]

LARGO_MINIMO = 4


def _pedir_password(nombre: str, rol: str) -> str:
    """Pide la contraseña dos veces (no se ve al tipearla) hasta que coincidan."""
    while True:
        password = getpass.getpass(f"  Contraseña para '{nombre}' ({rol}): ")
        if len(password) < LARGO_MINIMO:
            print(f"    La contraseña necesita al menos {LARGO_MINIMO} caracteres.")
            continue
        if password != getpass.getpass("  Repetila para confirmar: "):
            print("    No coinciden, probá de nuevo.")
            continue
        return password


def main():
    # Backup antes de tocar nada, igual que el resto de las migraciones. Si la
    # base todavía no existe no hay nada que resguardar: la crea create_all().
    if os.path.exists(DB_PATH):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(DIR_DATOS, f"viamonte_backup_{stamp}.db")
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup creado en: {os.path.basename(backup_path)}\n")

    # Crea las tablas que falten (entre ellas 'usuarios') sin tocar las que ya
    # están. Se usa el modelo en vez de escribir el CREATE TABLE a mano para no
    # tener la definición duplicada en dos lugares.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        creados = 0
        for nombre, rol in USUARIOS_INICIALES:
            existente = db.query(models.Usuario).filter(models.Usuario.nombre == nombre).first()
            if existente:
                print(f"  - {nombre} ({existente.rol}): ya existe, se omite.")
                continue

            password = _pedir_password(nombre, rol)
            db.add(models.Usuario(
                nombre=nombre,
                password_hash=hashear_password(password),
                rol=rol,
            ))
            db.commit()
            print(f"  + {nombre} ({rol}): creado.\n")
            creados += 1

        print(f"Listo: {creados} usuario(s) nuevo(s).")
        if creados:
            print("Ya podés iniciar el sistema y entrar con cualquiera de ellos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
