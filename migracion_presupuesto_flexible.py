"""
Migración única: presupuestos flexibles.

POR QUÉ ES NECESARIA
--------------------
Dos cambios sobre la tabla 'presupuestos':
  1. 'cliente_id' pasa de NOT NULL a nullable (para guardar borradores sin
     cliente asignado todavía).
  2. Se agregan las columnas 'material' (tipo de papel) y 'gramaje' (g/m²).

Agregar columnas nullable se puede con ALTER TABLE, pero SQLite NO permite
sacar el NOT NULL de una columna existente con ALTER: hay que RECREAR la tabla.
Como 'presupuestos' ya existe con datos reales, seguimos el mismo criterio que
migracion_decimal.py: leer los datos, dropear la tabla, recrearla desde los
modelos (create_all, que ya trae el esquema nuevo) y reinsertar las filas.

Se toca SOLO la tabla 'presupuestos'. Ninguna otra tabla la referencia por FK;
el único FK entrante es su auto-referencia 'version_de', que se recrea igual.

Es IDEMPOTENTE: si 'cliente_id' ya es nullable y 'material'/'gramaje' existen,
informa y sale sin tocar nada.

CÓMO CORRERLO (una sola vez, con el backend apagado):
    python migracion_presupuesto_flexible.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")


def _info_columnas(cur, tabla):
    """Devuelve la lista de filas de PRAGMA table_info (o [] si no existe)."""
    return cur.execute(f"PRAGMA table_info({tabla})").fetchall()


def _ya_migrada(info):
    """True si cliente_id ya es nullable y material/gramaje ya existen."""
    nombres = {c[1] for c in info}
    # PRAGMA table_info: col[3] == notnull (1 = NOT NULL).
    cliente = next((c for c in info if c[1] == "cliente_id"), None)
    cliente_nullable = cliente is not None and cliente[3] == 0
    return cliente_nullable and "material" in nombres and "gramaje" in nombres


def main():
    if not os.path.exists(DB_PATH):
        print("No existe viamonte.db, nada para migrar. (Se creará limpia al iniciar el backend.)")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    info = _info_columnas(cur, "presupuestos")
    if not info:
        conn.close()
        print("La tabla 'presupuestos' no existe todavía; se creará al iniciar el backend.")
        return

    if _ya_migrada(info):
        conn.close()
        print("La tabla 'presupuestos' ya está migrada (cliente_id nullable + material/gramaje). Nada que hacer.")
        return

    # 1) Backup fechado
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"viamonte_backup_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup creado en: {backup_path}")

    # 2) Leer todos los datos actuales de 'presupuestos'
    cur.execute("SELECT * FROM presupuestos")
    columnas_viejas = [d[0] for d in cur.description]
    filas = cur.fetchall()
    print(f"Leídas {len(filas)} fila(s) de 'presupuestos'.")

    # 3) Dropear la tabla vieja
    cur.execute("PRAGMA foreign_keys=OFF")
    cur.execute("DROP TABLE presupuestos")
    conn.commit()
    conn.close()

    # 4) Recrear el esquema nuevo desde los modelos (create_all no toca las
    #    tablas existentes; como 'presupuestos' ya no existe, la crea de cero
    #    con cliente_id nullable + material + gramaje).
    import models  # noqa: F401  (registra los modelos)
    from database import engine

    models.Base.metadata.create_all(bind=engine)
    print("Tabla 'presupuestos' recreada con el esquema nuevo.")

    # 5) Reinsertar las filas viejas (solo columnas que siguen existiendo)
    conn_new = sqlite3.connect(DB_PATH)
    cur_new = conn_new.cursor()
    columnas_nuevas = [c[1] for c in _info_columnas(cur_new, "presupuestos")]
    comunes = [c for c in columnas_viejas if c in columnas_nuevas]

    if filas:
        placeholders = ", ".join(["?"] * len(comunes))
        col_list = ", ".join(comunes)
        sql = f"INSERT INTO presupuestos ({col_list}) VALUES ({placeholders})"
        for fila in filas:
            fila_dict = dict(zip(columnas_viejas, fila))
            cur_new.execute(sql, [fila_dict[c] for c in comunes])
        conn_new.commit()

    print(f"Reinsertadas {len(filas)} fila(s). Columnas nuevas (material/gramaje) quedan en NULL.")
    conn_new.close()
    print(f"\nMigración completada. Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
