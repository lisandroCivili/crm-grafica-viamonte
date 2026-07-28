"""
Migración única: agrega los campos del remito (orden de entrega) a Trabajo.

POR QUÉ ES NECESARIA
--------------------
Mismo motivo que migracion_orden_produccion.py: create_all() no agrega columnas
a una tabla que ya existe, y 'trabajos' ya tiene datos reales.

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega remito_impreso, numero_remito y fecha_remito_impreso si faltan.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (desde la raíz del proyecto, con el backend apagado):
    python -m migraciones.migracion_orden_entrega
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

COLUMNAS_NUEVAS = [
    ("remito_impreso", "BOOLEAN DEFAULT 0"),
    ("numero_remito", "VARCHAR"),
    ("fecha_remito_impreso", "DATETIME"),
]


def _columnas_existentes(cur, tabla):
    return [c[1] for c in cur.execute(f"PRAGMA table_info({tabla})").fetchall()]


def main():
    if not os.path.exists(DB_PATH):
        print("No existe viamonte.db, nada para migrar. (Se creará limpia al iniciar el backend.)")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"viamonte_backup_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup creado en: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existentes = _columnas_existentes(cur, "trabajos")
    agregadas = 0
    for nombre, tipo in COLUMNAS_NUEVAS:
        if nombre in existentes:
            print(f"  - {nombre}: ya existe, se omite.")
            continue
        cur.execute(f"ALTER TABLE trabajos ADD COLUMN {nombre} {tipo}")
        print(f"  + {nombre}: agregada.")
        agregadas += 1

    # El default de ALTER TABLE sólo aplica a filas nuevas: las viejas quedan en
    # NULL. Mismo criterio que orden_impresa: dejamos 0 para que el guard de
    # idempotencia del endpoint no dependa de un NULL ambiguo.
    cur.execute("UPDATE trabajos SET remito_impreso = 0 WHERE remito_impreso IS NULL")
    print(f"  · remito_impreso normalizada en {cur.rowcount} fila(s).")

    conn.commit()
    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
