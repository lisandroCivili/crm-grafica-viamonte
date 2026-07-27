"""Validación del papel de una orden/presupuesto, en un módulo compartido.

Estas reglas las usan por igual el alta de trabajo y el alta de presupuesto: el
presupuesto le pasa el papel al trabajo al convertirse, así que si divergieran, un
presupuesto válido podría producir un trabajo inválido. Vivían en
routers/trabajos.py y routers/presupuestos.py las importaba desde ahí (un import
de router a router); movidas a este módulo plano —al nivel de calculos.py y
money.py— ese acoplamiento desaparece.

_descontar_papel y _devolver_papel se quedan en routers/trabajos.py: hoy nadie más
las usa, así que sólo se movió lo realmente compartido.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from money import Q3


def buscar_papel(db: Session, papel_id: str) -> models.ArticuloStock:
    """Trae el artículo de stock y verifica que sea papel medido en pliegos.

    El selector de papel históricamente listaba TODO el stock, así que nada
    impedía vincular una orden a un bidón de tinta y restarle "3 pliegos".
    Las compras por Kg ya se normalizan a "Pliegos" en stock.py, así que la
    validación no deja afuera al papel comprado por peso.
    """
    articulo = (
        db.query(models.ArticuloStock)
        .filter(models.ArticuloStock.id == papel_id)
        .first()
    )
    if not articulo:
        raise HTTPException(status_code=404, detail="El papel indicado no existe en el stock.")

    if articulo.unidad != "Pliegos":
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{articulo.nombre}' se mide en {articulo.unidad}, no en pliegos. "
                "Elegí un papel del stock."
            ),
        )
    return articulo


def validar_pliegos(cantidad_pliegos) -> None:
    """Los pliegos son unidades físicas: no existe medio pliego.

    Sólo se aplica sobre lo que entra por la API. _descontar_papel no lo usa
    porque hay trabajos históricos con cantidades fraccionarias y el descuento
    no debe romperse por eso.
    """
    if cantidad_pliegos is None:
        return

    pliegos = Q3(cantidad_pliegos)
    if pliegos <= Decimal("0"):
        raise HTTPException(status_code=400, detail="La cantidad de pliegos debe ser mayor a cero.")
    if pliegos != pliegos.to_integral_value():
        raise HTTPException(
            status_code=400,
            detail=f"La cantidad de pliegos debe ser un número entero (recibido: {pliegos}).",
        )


def validar_papel(db: Session, papel_id, cantidad_pliegos) -> None:
    """Valida el papel elegido, si se eligió uno. Compartido con presupuestos.

    Los dos campos van juntos: un papel sin pliegos no descuenta nada (el guard
    de _descontar_papel lo saltea) y el stock queda desfasado en silencio, que
    es el mismo síntoma que tenía el presupuesto convertido. Pliegos sin papel
    no tienen a qué aplicarse.

    Dejar los dos en null sí es válido: significa que el papel lo trae el
    cliente o se compra en el momento, y entonces no hay nada que descontar.
    """
    if papel_id and cantidad_pliegos is None:
        raise HTTPException(
            status_code=400,
            detail="Elegiste un papel del stock: indicá cuántos pliegos consume, si no la orden no puede descontarlo.",
        )
    if cantidad_pliegos is not None and not papel_id:
        raise HTTPException(
            status_code=400,
            detail="Cargaste una cantidad de pliegos pero no elegiste de qué papel del stock descontarlos.",
        )
    if papel_id:
        buscar_papel(db, papel_id)
        validar_pliegos(cantidad_pliegos)
