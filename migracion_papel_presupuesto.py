"""
Migración única: agrega el papel del stock a los Presupuestos.

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'presupuestos' ya existe con
datos, las columnas nuevas hay que agregarlas a mano.

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega las columnas papel_id y cantidad_pliegos si faltan.

QUÉ RESUELVE
------------
El presupuesto guardaba el papel sólo como texto libre (material, gramaje), que
sirve para leerlo impreso pero no identifica un artículo del stock. Al
convertirlo, el trabajo nacía con papel_id en NULL, y al imprimir su orden no se
descontaba nada: el camino más usado del taller —presupuestar, convertir,
imprimir— dejaba el stock desfasado sin dar ningún error.

Con estas columnas el presupuesto elige el papel del stock y el trabajo lo
hereda al convertirse.

Las columnas quedan en NULL para los presupuestos ya cargados, que es lo
correcto: no sabemos qué papel del stock les correspondía. Los que ya se
convirtieron no se tocan; si a alguno hay que descontarle papel, se le asigna
al TRABAJO antes de imprimir la orden.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_papel_presupuesto.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# cantidad_pliegos va como TEXT porque el TypeDecorator Cantidad (money.py)
# persiste los decimales como texto para no perder precisión con el float de
# SQLite. Mismo tipo que la columna homónima de 'trabajos'.
COLUMNAS_NUEVAS = [
    ("papel_id", "VARCHAR REFERENCES stock(id)"),
    ("cantidad_pliegos", "TEXT"),
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
    existentes = _columnas_existentes(cur, "presupuestos")
    agregadas = 0
    for nombre, tipo in COLUMNAS_NUEVAS:
        if nombre in existentes:
            print(f"  - {nombre}: ya existe, se omite.")
            continue
        cur.execute(f"ALTER TABLE presupuestos ADD COLUMN {nombre} {tipo}")
        print(f"  + {nombre}: agregada.")
        agregadas += 1

    conn.commit()
    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
