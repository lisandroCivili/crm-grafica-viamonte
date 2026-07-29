"""
Migración única: saca del Kanban el histórico de trabajos entregados.

POR QUÉ ES NECESARIA
--------------------
`models.Base.metadata.create_all()` (main.py) sólo crea tablas que NO existen:
no agrega columnas a una tabla ya creada. Como 'trabajos' ya existe con datos
reales, la columna nueva hay que agregarla a mano.

QUÉ RESUELVE
------------
La columna "Entregado" del tablero mostraba TODOS los trabajos entregados desde
el primer día. A los pocos meses de uso real eso son miles de tarjetas: el
tablero deja de servir para trabajar y el navegador se arrastra dibujándolas.

Ahora el Kanban muestra sólo los entregados de los últimos
models.DIAS_ENTREGADO_EN_TABLERO días, y hay un botón para quitar antes uno que
ya no se quiere ver (columna 'archivado'). Nada se borra: el historial completo
de cada cliente sigue en su ficha.

QUÉ HACE
--------
1. Hace un backup fechado de viamonte.db.
2. Agrega la columna archivado si falta.
3. Normaliza en 0 las filas viejas.
4. Archiva los trabajos que hoy están en 'Entregado'.

POR QUÉ EL PASO 4
-----------------
fecha_entrega existía en el modelo pero no la escribía nadie: los trabajos ya
entregados la tienen en NULL y no hay forma de saber cuándo se entregaron. El
filtro del tablero los dejaría afuera igual (NULL nunca entra en la ventana de
días), pero quedarían fuera por un dato faltante y no por una decisión: no se
podrían devolver al tablero desde ningún lado.

Archivarlos los deja fuera por el mismo mecanismo que el botón, así que si
Facundo quiere alguno de vuelta lo encuentra tildando "Ver historial completo"
y lo restaura. De acá en adelante fecha_entrega se completa sola al entregar.

Es IDEMPOTENTE: se puede correr dos veces sin romper nada. La segunda corrida no
vuelve a archivar nada, porque sólo toca las filas que quedaron en 0.

NOTA: en el servidor (Railway) esto ya no hace falta correrlo a mano. La misma
columna se agrega sola al arrancar el backend (ver arranque.py,
aplicar_migraciones_pendientes) porque ahí no hay consola. Este script sigue
sirviendo para la compu del taller o para forzarla manualmente si hiciera falta.

CÓMO CORRERLO (desde la raíz del proyecto, con el backend apagado):
    python -m migraciones.migracion_archivo_kanban
"""
import os
import shutil
import sqlite3
from datetime import datetime

# Este script vive en migraciones/, pero la base está en la raíz del proyecto:
# de ahí el dirname() de más. Sin él, DB_PATH apuntaría a migraciones/viamonte.db,
# que no existe, y la migración terminaría diciendo "nada para migrar" sin haber
# tocado la base real.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")

COLUMNAS_NUEVAS = [
    ("archivado", "BOOLEAN DEFAULT 0"),
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

    # 3) El default de ALTER TABLE sólo aplica a filas nuevas: las viejas quedan
    # en NULL. Lo dejamos en 0 para que el filtro del tablero no dependa de un
    # NULL ambiguo (mismo criterio que papel_devuelto en migracion_devolucion_papel.py).
    cur.execute("UPDATE trabajos SET archivado = 0 WHERE archivado IS NULL")
    print(f"  · archivado normalizada en {cur.rowcount} fila(s).")

    # 4) El histórico ya entregado sale del tablero. Ver POR QUÉ EL PASO 4 arriba.
    cur.execute("UPDATE trabajos SET archivado = 1 WHERE estado = 'Entregado' AND archivado = 0")
    archivados = cur.rowcount
    print(f"  · {archivados} trabajo(s) entregado(s) quitados del tablero.")

    conn.commit()

    # Los que siguen vivos no se tocan: si este número no es el que Facundo
    # espera ver en el tablero, algo salió mal y conviene saberlo antes de abrir.
    en_curso = cur.execute(
        "SELECT COUNT(*) FROM trabajos WHERE estado IN ('Aprobado', 'En Diseño', 'En Producción')"
    ).fetchone()[0]
    print(f"  · {en_curso} trabajo(s) en curso siguen en el tablero.")

    conn.close()
    print(f"\nMigración completada ({agregadas} columna(s) nueva(s)). Backup en {os.path.basename(backup_path)}.")


if __name__ == "__main__":
    main()
