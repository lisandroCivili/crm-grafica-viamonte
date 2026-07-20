"""
Migración única: historial de cheques + fecha de endoso ("Cheques v2").

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. La tabla 'cheques' ya existe con datos
reales, así que la columna nueva hay que agregarla a mano.

(La tabla 'historial_cheques' la crearía create_all() sola por ser nueva, pero
la creamos acá para que la base quede consistente aunque el backend no se haya
reiniciado todavía.)

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Crea la tabla 'historial_cheques' si falta (todo cambio de estado, monto o
   clasificación de un cheque deja asiento: "nunca perder historial del cambio").
3. Agrega a 'cheques' la columna fecha_endoso si falta. Endosar un cheque
   equivale a cobrarlo (realiza la ganancia del trabajo), y los cálculos
   necesitan saber en qué fecha pasó.

Los cheques ya endosados antes de esta migración quedan con fecha_endoso NULL:
los cálculos los ignoran hasta que se les complete la fecha, en vez de imputarlos
a un período equivocado.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_cheques_v2.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# Columnas nuevas de 'cheques' con su definición SQL.
COLUMNAS_NUEVAS = [
    ("fecha_endoso", "DATE"),
]

SQL_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_cheques (
    id VARCHAR NOT NULL PRIMARY KEY,
    cheque_id VARCHAR NOT NULL,
    estado_anterior VARCHAR,
    estado_nuevo VARCHAR,
    detalle VARCHAR NOT NULL,
    fecha DATETIME,
    FOREIGN KEY(cheque_id) REFERENCES cheques (id)
)
"""


def _columnas_existentes(cur, tabla):
    return [c[1] for c in cur.execute(f"PRAGMA table_info({tabla})").fetchall()]


def _tabla_existe(cur, tabla):
    fila = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone()
    return fila is not None


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

    # 2) Tabla de historial
    ya_estaba = _tabla_existe(cur, "historial_cheques")
    cur.execute(SQL_HISTORIAL)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_historial_cheques_id ON historial_cheques (id)")
    print("  - historial_cheques: ya existe, se omite."
          if ya_estaba else "  + historial_cheques: creada.")

    # 3) Agregar las columnas que falten
    existentes = _columnas_existentes(cur, "cheques")
    agregadas = 0
    for nombre, tipo in COLUMNAS_NUEVAS:
        if nombre in existentes:
            print(f"  - {nombre}: ya existe, se omite.")
            continue
        cur.execute(f"ALTER TABLE cheques ADD COLUMN {nombre} {tipo}")
        print(f"  + {nombre}: agregada.")
        agregadas += 1

    # 4) Aviso: endosos viejos sin fecha (no los inventamos, los reportamos)
    pendientes = cur.execute(
        "SELECT COUNT(*) FROM cheques WHERE estado = 'Endosado' AND fecha_endoso IS NULL"
    ).fetchone()[0]
    if pendientes:
        print(f"\n  ATENCIÓN: {pendientes} cheque(s) ya endosados no tienen fecha_endoso.")
        print("  No aportarán ingreso ni ganancia hasta que se les cargue la fecha desde la app.")

    conn.commit()
    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
