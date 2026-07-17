"""
Migración única: campos financieros del Módulo 4 (Dashboard, Gastos y Cheques).

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'cheques' y 'gastos' ya existen
con datos reales, las columnas nuevas hay que agregarlas a mano.

Todas las columnas nuevas tienen default o son nullable, así que un simple
ALTER TABLE ADD COLUMN alcanza (no hace falta recrear la tabla ni copiar datos).

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega a 'cheques' las columnas clasificacion y trabajo_id si faltan.
3. Agrega a 'gastos' la columna responsable si falta.
4. Normaliza las filas viejas: cheques -> clasificacion 'Recibido';
   gastos -> responsable 'General'.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada.

CÓMO CORRERLO (con el backend apagado):
    python migracion_modulo4_finanzas.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# Columnas nuevas por tabla con su definición SQL.
COLUMNAS_NUEVAS = {
    "cheques": [
        ("clasificacion", "VARCHAR DEFAULT 'Recibido'"),
        ("trabajo_id", "VARCHAR REFERENCES trabajos(id)"),
    ],
    "gastos": [
        ("responsable", "VARCHAR DEFAULT 'General'"),
    ],
}


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
    agregadas = 0
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        existentes = _columnas_existentes(cur, tabla)
        for nombre, tipo in columnas:
            if nombre in existentes:
                print(f"  - {tabla}.{nombre}: ya existe, se omite.")
                continue
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
            print(f"  + {tabla}.{nombre}: agregada.")
            agregadas += 1

    # 3) Normalizar filas viejas: el default de ALTER TABLE sólo aplica a filas
    #    nuevas, las existentes quedan en NULL. Les damos el valor por defecto.
    cur.execute("UPDATE cheques SET clasificacion = 'Recibido' WHERE clasificacion IS NULL")
    print(f"  · cheques.clasificacion normalizada en {cur.rowcount} fila(s).")
    cur.execute("UPDATE gastos SET responsable = 'General' WHERE responsable IS NULL")
    print(f"  · gastos.responsable normalizado en {cur.rowcount} fila(s).")

    conn.commit()
    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
