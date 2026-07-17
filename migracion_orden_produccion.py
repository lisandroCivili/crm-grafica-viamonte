"""
Migración única: convierte los Trabajos en Órdenes de Producción.

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'trabajos' ya existe con datos
reales, los campos nuevos de la boleta hay que agregarlos a mano.

A diferencia de migracion_decimal.py, acá NO hace falta recrear las tablas:
todas las columnas nuevas son nullable o con default, así que un simple
ALTER TABLE ADD COLUMN alcanza y es mucho más seguro (no se copian datos).

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega las columnas de la orden de producción que falten.
3. Unifica el estado 'Pendiente de Pago' en 'Aprobado'.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_orden_produccion.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# Columnas nuevas de 'trabajos' con su definición SQL.
# Money y Cantidad se persisten como TEXT (ver money.py), por eso VARCHAR.
COLUMNAS_NUEVAS = [
    ("medida_terminado", "VARCHAR"),
    ("medida_pliego", "VARCHAR"),
    ("corte_pliego", "VARCHAR"),
    ("tintas", "VARCHAR"),
    ("troquelado", "VARCHAR"),
    ("barniz", "VARCHAR"),
    ("otros", "TEXT"),
    ("papel_tipo", "VARCHAR"),
    ("papel_id", "VARCHAR REFERENCES stock(id)"),
    ("cantidad_pliegos", "VARCHAR"),
    ("orden_impresa", "BOOLEAN DEFAULT 0"),
    ("numero_orden", "VARCHAR"),
    ("fecha_orden_impresa", "DATETIME"),
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

    # El default de ALTER TABLE sólo aplica a filas nuevas: las viejas quedan
    # en NULL. Dejamos orden_impresa en 0 para que el guard de idempotencia
    # no dependa de un NULL ambiguo.
    cur.execute("UPDATE trabajos SET orden_impresa = 0 WHERE orden_impresa IS NULL")
    print(f"  · orden_impresa normalizada en {cur.rowcount} fila(s).")

    # 3) Unificar el estado viejo. 'Pendiente de Pago' venía del default de
    #    schemas.py, que no coincidía con el de models.py ('Aprobado'), y el
    #    Kanban no sabía renderizarlo.
    cur.execute("UPDATE trabajos SET estado = 'Aprobado' WHERE estado = 'Pendiente de Pago'")
    print(f"  · {cur.rowcount} trabajo(s) pasaron de 'Pendiente de Pago' a 'Aprobado'.")

    conn.commit()

    # Reporte final del estado de la tabla
    print("\nEstados actuales en 'trabajos':")
    for estado, total in cur.execute(
        "SELECT estado, COUNT(*) FROM trabajos GROUP BY estado ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {estado}: {total}")

    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
