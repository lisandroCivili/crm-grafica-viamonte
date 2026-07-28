"""Consulta del registro de auditoría.

Módulo entero del dueño: el log dice quién hizo cada cosa, incluidos los cambios
de precio y los pagos, y no es algo que el taller tenga por qué leer.

SÓLO HAY GET. No existe POST, PUT ni DELETE a propósito: un registro de
auditoría que se puede editar o borrar desde la misma pantalla que audita no
registra nada. Las filas las escribe auditoria.asentar() desde cada endpoint.
"""
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from seguridad import solo_admin

router = APIRouter(
    prefix="/api/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(solo_admin)],
)

# Cuántas filas trae una consulta sin pedir nada en particular: entra en una
# pantalla sin scrollear una hora y alcanza para "qué pasó hoy".
LIMITE_POR_DEFECTO = 200

# Techo duro. Un rango de fechas amplio sobre un log de meses traería la tabla
# entera a la memoria del servidor (y al navegador) de una sola vez.
LIMITE_MAXIMO = 1000


@router.get("/", response_model=list[schemas.AuditoriaResponse])
def listar_auditoria(
    entidad: str | None = None,
    usuario: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = Query(LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
):
    """Las últimas cosas que pasaron en el sistema, de la más nueva a la más vieja.

    Los filtros se combinan (todos opcionales): entidad ('Trabajo', 'Cliente'…),
    usuario por nombre, y un rango de fechas.
    """
    query = db.query(models.Auditoria)

    if entidad:
        query = query.filter(models.Auditoria.entidad == entidad)

    if usuario:
        # Por nombre y no por id: es lo que se elige en la pantalla, y además es
        # lo único que hay cuando el asiento es un intento de ingreso fallido.
        query = query.filter(models.Auditoria.usuario_nombre == usuario.strip().lower())

    # 'hasta' incluye el día entero: filtrar por la fecha pelada la compara
    # contra las 00:00 y se perdería todo lo hecho ese mismo día.
    if desde:
        query = query.filter(models.Auditoria.fecha >= datetime.combine(desde, time.min))
    if hasta:
        query = query.filter(models.Auditoria.fecha <= datetime.combine(hasta, time.max))

    return query.order_by(models.Auditoria.fecha.desc()).limit(limite).all()
