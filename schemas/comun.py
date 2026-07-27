"""Validadores compartidos por los schemas de varias entidades.

Viven una sola vez acá y cada entidad los engancha con field_validator. Antes
estaban todos arriba del schemas.py monolítico.
"""
from typing import Optional
from decimal import Decimal, InvalidOperation


def _validar_detalles_costos(valor: Optional[dict]) -> Optional[dict]:
    """Exige que cada costo del presupuesto sea un número.

    Mapa de costos: {"papel": 1200, "tinta": "350.50"}. Antes era un dict libre
    y un valor vacío o un texto llegaba hasta sumar_detalles_costos, que reventaba
    con InvalidOperation y devolvía un 500 opaco; acá se corta con un 422 que
    dice qué costo está mal.

    Valida SIN convertir: el dict se persiste en una columna JSON, y un Decimal
    no es serializable a JSON. Los valores se guardan como llegaron y es
    calculos.py, con Q2(), el que los pasa a Decimal para operar.

    Un valor en null se acepta: significa "costo no cargado" y calculos.py ya lo
    saltea, así que rechazarlo rompería lo que hoy funciona.
    """
    if valor is None:
        return valor
    for clave, monto in valor.items():
        if monto is None:
            continue
        try:
            importe = Decimal(str(monto))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(
                f"El costo '{clave}' tiene que ser un número (recibido: {monto!r})."
            )
        if importe < 0:
            raise ValueError(f"El costo '{clave}' no puede ser negativo (recibido: {monto!r}).")
    return valor


def _validar_margen(valor: Optional[Decimal]) -> Optional[Decimal]:
    """El margen puede ser negativo, pero no tanto como para dar precio negativo.

    Vender bajo costo es una decisión comercial válida (liquidar un saldo de
    papel, no perder un cliente), y -100% es regalar el trabajo: precio final 0,
    el mismo caso que la reimpresión de cortesía. Más abajo de -100% el precio
    da negativo, o sea pagarle al cliente por llevárselo.

    Importa que se corte acá y no sólo en el precio: convertir_presupuesto crea
    el Trabajo por ORM con el precio_final ya calculado, sin pasar por
    TrabajoCreate. Sin esta validación ese es el camino por el que un importe
    negativo entra a trabajos sin que ningún schema lo mire.
    """
    if valor is not None and valor < Decimal("-100"):
        raise ValueError(
            f"El margen no puede ser menor a -100% (recibido: {valor}%): el precio daría negativo."
        )
    return valor


def _validar_monto_no_negativo(valor: Optional[Decimal]) -> Optional[Decimal]:
    """Rechaza importes negativos. Compartido por trabajos, movimientos,
    gastos y cheques.

    Un importe negativo no existe en el taller y encima invierte el signo de los
    cálculos sin avisar: un gasto negativo aparece como ganancia, un pago
    negativo agranda la deuda del cliente y un precio negativo hace que un
    trabajo entregado figure como plata a favor. calculos.py opera bien con lo
    que recibe, así que la única forma de que no pase es que no llegue a la base.

    El cero sí se acepta: un trabajo de cortesía (una reimpresión por un error
    propio) se factura en 0 y es legítimo. Para plata que entra o sale de verdad
    lo filtran los routers, que ya ignoran los movimientos en 0.
    """
    if valor is not None and valor < 0:
        raise ValueError(f"El importe no puede ser negativo (recibido: {valor}).")
    return valor
