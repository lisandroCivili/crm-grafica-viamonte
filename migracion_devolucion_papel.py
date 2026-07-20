"""
Migración única: agrega el flag de devolución de papel a los Trabajos.

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'trabajos' ya existe con datos
reales, la columna nueva hay que agregarla a mano.

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega la columna papel_devuelto si falta.
3. Normaliza en 0 las filas viejas.

QUÉ RESUELVE
------------
Hasta ahora el descuento de papel de una orden impresa era irreversible: si el
trabajo se cancelaba, los pliegos quedaban restados para siempre. Ahora la
cancelación ofrece devolverlos al stock, y papel_devuelto es el guard de
idempotencia que evita devolver dos veces si el trabajo se cancela y reactiva.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_devolucion_papel.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

COLUMNAS_NUEVAS = [
    ("papel_devuelto", "BOOLEAN DEFAULT 0"),
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
    # NULL. Lo dejamos en 0 para que el guard no dependa de un NULL ambiguo
    # (mismo criterio que orden_impresa en migracion_orden_produccion.py).
    cur.execute("UPDATE trabajos SET papel_devuelto = 0 WHERE papel_devuelto IS NULL")
    print(f"  · papel_devuelto normalizada en {cur.rowcount} fila(s).")

    conn.commit()

    # Reporte: trabajos ya cancelados que descontaron papel y nunca lo devolvieron.
    # No los tocamos automáticamente (devolver stock viejo falsearía el historial),
    # pero conviene saber que existen para ajustarlos a mano si corresponde.
    pendientes = cur.execute(
        "SELECT numero_orden, cantidad_pliegos FROM trabajos "
        "WHERE estado = 'Cancelado' AND orden_impresa = 1 AND papel_id IS NOT NULL"
    ).fetchall()
    if pendientes:
        print("\nTrabajos cancelados que ya habían descontado papel (revisar a mano):")
        for numero_orden, pliegos in pendientes:
            print(f"  {numero_orden or 'sin número'}: {pliegos} pliegos")

    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
