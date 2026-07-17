"""
Migración única: agrega las dimensiones del papel a la tabla 'stock'.

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'stock' ya existe con datos
reales, las columnas nuevas hay que agregarlas a mano.

Las tres columnas son nullable, así que un simple ALTER TABLE ADD COLUMN
alcanza (no hace falta recrear la tabla ni copiar datos).

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega a 'stock' las columnas largo_cm, ancho_cm y gramaje_grs si faltan.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_stock_pliegos.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# Columnas nuevas de 'stock' con su definición SQL.
# Cantidad se persiste como TEXT (ver money.py), por eso VARCHAR.
COLUMNAS_NUEVAS = [
    ("largo_cm", "VARCHAR"),
    ("ancho_cm", "VARCHAR"),
    ("gramaje_grs", "VARCHAR"),
]


def _columnas_existentes(cur, tabla):
    return [c[1] for c in cur.execute(f"PRAGMA table_info({tabla})").fetchall()]


def main():
    if not os.path.exists(DB_PATH):
        print("No existe viamonte.db, nada para migrar. (Se creará limpia al iniciar el backend.)")
        return

    # 1) Backup fechado
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"viamonte_backup_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup creado en: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 2) Agregar las columnas que falten
    existentes = _columnas_existentes(cur, "stock")
    agregadas = 0
    for nombre, tipo in COLUMNAS_NUEVAS:
        if nombre in existentes:
            print(f"  - {nombre}: ya existe, se omite.")
            continue
        cur.execute(f"ALTER TABLE stock ADD COLUMN {nombre} {tipo}")
        print(f"  + {nombre}: agregada.")
        agregadas += 1

    conn.commit()
    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
