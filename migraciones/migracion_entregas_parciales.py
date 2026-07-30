"""
Migración única: entregas parciales / remitos combinados.

POR QUÉ ES NECESARIA
--------------------
El remito pasó a modelarse aparte, en las tablas 'entregas' (el remito:
cliente, número, fecha) e 'items_entrega' (una fila por trabajo incluido),
porque un remito puede combinar varios trabajos del mismo cliente en una sola
entrega física (ej: el cliente retira parte de dos pedidos distintos en la
misma visita). Ver models.py (clases Entrega / ItemEntrega) y
trabajos_comun.py.

A diferencia de las otras migraciones, acá NO hay ALTER TABLE: 'entregas' e
'items_entrega' son tablas nuevas y create_all() las crea solas. Lo que este
script agrega es el BACKFILL: cada Trabajo que ya tenía un numero_remito bajo
el modelo viejo (una columna por trabajo, sin combinar) se convierte en un
Entrega con un solo ItemEntrega, para no perder el historial de remitos ya
emitidos en producción.

Los campos legacy de Trabajo (remito_impreso/numero_remito/fecha_remito_impreso)
quedan intactos después de correr esto: se leen, no se tocan ni se borran (ver
el comentario en models.py sobre por qué se conservan congelados — la tabla
'trabajos' tiene FKs entrantes de otras cinco tablas y recrearla es un riesgo
innecesario para ganar prolijidad de esquema).

Es IDEMPOTENTE: sólo migra los trabajos que todavía no tienen ningún
ItemEntrega asociado, así que correrlo de nuevo no duplica nada.

CÓMO CORRERLO (desde la raíz del proyecto, con el backend apagado):
    python -m migraciones.migracion_entregas_parciales

NOTA SOBRE RAILWAY: igual que migracion_archivo_kanban, el backfill se corre
solo en cada arranque del backend (ver arranque.py, aplicar_migraciones_pendientes)
porque ahí no hay consola. Este script sigue sirviendo para la compu del
taller o para forzarlo a mano si hiciera falta.
"""
import os
import shutil
from datetime import datetime, time

# Este script vive en migraciones/, pero la base está en la raíz del proyecto:
# de ahí el dirname() de más. Sin él, DB_PATH apuntaría a migraciones/viamonte.db,
# que no existe, y la migración terminaría diciendo "nada para migrar" sin haber
# tocado la base real.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "viamonte.db")


def main():
    if not os.path.exists(DB_PATH):
        print("No existe viamonte.db, nada para migrar. (Se creará limpia al iniciar el backend.)")
        return

    # 1) Backup fechado, mismo criterio que el resto de las migraciones.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"viamonte_backup_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup creado en: {os.path.basename(backup_path)}")

    import models
    from database import Base, SessionLocal, engine

    # 2) Crea 'entregas'/'items_entrega' si todavía no existen. No toca
    # ninguna tabla ya creada: create_all() nunca altera esquemas existentes.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        migrados = _migrar(db, models)
        print(f"Migrados {migrados} remito(s) legado(s).")
    finally:
        db.close()

    print(f"\nMigración completada. Backup en {os.path.basename(backup_path)}.")


def _migrar(db, models) -> int:
    """Backfill propiamente dicho. Devuelve cuántos trabajos migró.

    Commitea trabajo por trabajo: si uno falla (ver el catch de abajo), no se
    pierde lo que ya se migró antes en la misma corrida.
    """
    from sqlalchemy.exc import IntegrityError

    candidatos = db.query(models.Trabajo).filter(models.Trabajo.numero_remito.isnot(None)).all()

    migrados = 0
    for trabajo in candidatos:
        ya_migrado = db.query(models.ItemEntrega).filter(
            models.ItemEntrega.trabajo_id == trabajo.id
        ).first()
        if ya_migrado:
            continue

        # fecha_remito_impreso es DateTime; fecha_creacion es sólo Date (la
        # columna Entrega.fecha es DateTime, así que si no hay hora registrada
        # se completa con medianoche del día de creación).
        fecha = trabajo.fecha_remito_impreso or datetime.combine(trabajo.fecha_creacion, time.min)
        numero = trabajo.numero_remito

        try:
            entrega = models.Entrega(cliente_id=trabajo.cliente_id, numero_remito=numero, fecha=fecha)
            db.add(entrega)
            db.flush()
        except IntegrityError:
            # El sistema viejo no garantizaba unicidad de numero_remito entre
            # trabajos DISTINTOS (_generar_numero_remito leía el máximo y
            # sumaba 1 sin ningún lock). Si dos remitos se imprimieron casi al
            # mismo tiempo históricamente, pueden compartir número: se marca el
            # duplicado con un sufijo en vez de perder el trabajo o cortar acá
            # toda la migración.
            db.rollback()
            numero = f"{trabajo.numero_remito}-DUP-{trabajo.id[:8]}"
            entrega = models.Entrega(cliente_id=trabajo.cliente_id, numero_remito=numero, fecha=fecha)
            db.add(entrega)
            db.flush()
            print(f"  ⚠️  Remito legado duplicado: trabajo {trabajo.id} migrado como {numero}.")

        db.add(models.ItemEntrega(
            entrega_id=entrega.id,
            trabajo_id=trabajo.id,
            cantidad=trabajo.cantidad,
        ))
        db.commit()
        migrados += 1

    return migrados


if __name__ == "__main__":
    main()
