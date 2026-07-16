"""
Migración única: pasa los montos de la base de FLOAT (REAL) a DECIMAL (TEXT).

POR QUÉ ES NECESARIA
--------------------
Las columnas de dinero se crearon originalmente como Float, así que en SQLite
quedaron con "afinidad REAL". Aunque ahora el modelo use el TypeDecorator Money
(que guarda TEXT), SQLite volvería a convertir el TEXT a float por la afinidad
vieja de la columna. Por eso no alcanza con reescribir valores: hay que
RECREAR las tablas con el esquema nuevo (columnas VARCHAR/TEXT) y copiar los datos.

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Lee todos los datos de una copia de la base vieja.
3. Borra viamonte.db y crea las tablas nuevas (esquema Decimal) con create_all.
4. Reinserta cada fila convirtiendo los montos a Decimal cuantizado (str exacto).

CÓMO CORRERLO (una sola vez, con el backend apagado):
    python migracion_decimal.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

from money import Q2, Q3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

# Columnas de DINERO (2 decimales) por tabla.
MONEY_COLS = {
    "trabajos": ["precio_venta", "costo_total_materiales"],
    "movimientos": ["monto"],
    "presupuestos": ["costo_materiales", "margen_ganancia", "precio_final"],
    "gastos": ["monto"],
    "cheques": ["monto"],
    "stock": ["costo_unitario"],
}

# Columnas de CANTIDAD de stock (3 decimales) por tabla.
CANTIDAD_COLS = {
    "stock": ["cantidad", "stock_minimo"],
    "historial_stock": ["diferencia"],
}


def _leer_tabla(conn, tabla):
    """Devuelve (columnas, filas) de una tabla; [] si la tabla no existe."""
    cur = conn.cursor()
    existe = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone()
    if not existe:
        return [], []
    cur.execute(f"SELECT * FROM {tabla}")
    columnas = [d[0] for d in cur.description]
    filas = cur.fetchall()
    return columnas, filas


def _convertir(tabla, columna, valor):
    """Convierte un valor de dinero/cantidad al string Decimal exacto."""
    if valor is None:
        return None
    if columna in MONEY_COLS.get(tabla, []):
        return str(Q2(valor))
    if columna in CANTIDAD_COLS.get(tabla, []):
        return str(Q3(valor))
    return valor


def main():
    if not os.path.exists(DB_PATH):
        print("No existe viamonte.db, nada para migrar. (Se creará limpia al iniciar el backend.)")
        return

    # 1) Backup fechado
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"viamonte_backup_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup creado en: {backup_path}")

    # 2) Leer TODOS los datos de una copia estable de la base vieja
    copia_vieja = os.path.join(BASE_DIR, f"viamonte_pre_decimal_{stamp}.db")
    shutil.copy2(DB_PATH, copia_vieja)

    conn_old = sqlite3.connect(copia_vieja)
    tablas = [
        r[0]
        for r in conn_old.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    datos = {t: _leer_tabla(conn_old, t) for t in tablas}
    conn_old.close()

    # 3) Borrar la base y recrear el esquema nuevo (Money = TEXT)
    os.remove(DB_PATH)
    import models  # noqa: F401  (registra los modelos)
    from database import engine

    models.Base.metadata.create_all(bind=engine)
    print("Tablas recreadas con el esquema Decimal.")

    # 4) Reinsertar fila por fila, respetando solo las columnas que existen en el esquema nuevo
    conn_new = sqlite3.connect(DB_PATH)
    cur_new = conn_new.cursor()

    for tabla, (columnas_viejas, filas) in datos.items():
        if not filas:
            continue
        # Columnas del esquema nuevo para esta tabla
        info = cur_new.execute(f"PRAGMA table_info({tabla})").fetchall()
        if not info:
            # Tabla que ya no existe en el esquema nuevo: la salteamos
            print(f"  - {tabla}: no existe en el esquema nuevo, se omite.")
            continue
        columnas_nuevas = [c[1] for c in info]
        comunes = [c for c in columnas_viejas if c in columnas_nuevas]

        placeholders = ", ".join(["?"] * len(comunes))
        col_list = ", ".join(comunes)
        sql = f"INSERT INTO {tabla} ({col_list}) VALUES ({placeholders})"

        for fila in filas:
            fila_dict = dict(zip(columnas_viejas, fila))
            valores = [_convertir(tabla, c, fila_dict[c]) for c in comunes]
            cur_new.execute(sql, valores)

        print(f"  - {tabla}: {len(filas)} filas migradas.")

    conn_new.commit()
    conn_new.close()
    print("Migración completada. Revisá los importes y luego podés borrar los archivos de respaldo.")


if __name__ == "__main__":
    main()
