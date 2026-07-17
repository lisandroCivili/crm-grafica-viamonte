"""
Cálculos financieros centralizados. Única fuente de verdad para la matemática
del CRM: todo se hace en Decimal y se cuantiza a 2 decimales.

El frontend puede mostrar previews, pero los valores que se persisten y los
saldos que se muestran deben salir de acá.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Iterable, Mapping, Optional, Tuple

from money import Q2

CERO = Decimal("0.00")
CIEN = Decimal("100")


def _a_fecha(valor):
    """Normaliza datetime/date a date para comparar contra un período."""
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def _metodo_es_cheque(metodo) -> bool:
    """Un pago abonado con cheque no es plata realizada: se sigue por Cheque."""
    return (metodo or "").strip().lower() == "cheque"


def sumar_detalles_costos(detalles: Optional[Mapping[str, object]]) -> Decimal:
    """Suma los valores del diccionario de costos de un presupuesto."""
    total = CERO
    if not detalles:
        return total
    for valor in detalles.values():
        if valor is None:
            continue
        total += Q2(valor)
    return Q2(total)


def calcular_precio_presupuesto(
    costo_materiales: Decimal, margen_ganancia: Decimal
) -> Tuple[Decimal, Decimal, Decimal]:
    """Devuelve (subtotal, ganancia, precio_final) en Decimal a 2 decimales.

    precio_final = costo_materiales * (1 + margen/100)
    """
    subtotal = Q2(costo_materiales)
    margen = Q2(margen_ganancia)
    ganancia = Q2(subtotal * margen / Decimal("100"))
    precio_final = Q2(subtotal + ganancia)
    return subtotal, ganancia, precio_final


def _monto_pagos(movimientos: Iterable) -> Decimal:
    """Suma los montos de los movimientos de tipo 'Pago'."""
    total = CERO
    for m in movimientos:
        if getattr(m, "tipo", None) == "Pago" and m.monto is not None:
            total += Q2(m.monto)
    return Q2(total)


def _monto_cheques_recibidos(cheques: Iterable) -> Decimal:
    """Suma los cheques recibidos que representan un pago válido del cliente.

    Entregar un cheque salda la deuda; sólo un cheque 'Rechazado' la reabre. Por
    eso cuentan como pago todos los recibidos salvo los rechazados.
    """
    total = CERO
    for ch in cheques:
        if getattr(ch, "clasificacion", "Recibido") != "Recibido":
            continue
        if getattr(ch, "estado", None) == "Rechazado" or ch.monto is None:
            continue
        total += Q2(ch.monto)
    return Q2(total)


def fraccion_ganancia(margen: Decimal) -> Decimal:
    """Fracción de ganancia contenida en cada peso cobrado.

    Equivale a ganancia_presupuesto / precio_final = margen / (100 + margen).
    No se cuantiza acá: es un ratio, se cuantiza el monto final.
    """
    m = Q2(margen)
    denom = CIEN + m
    if denom == 0:
        return Decimal("0")
    return m / denom


def calcular_saldo_trabajo(
    precio_venta: Decimal, movimientos_trabajo: Iterable, cheques_trabajo: Iterable = ()
) -> Decimal:
    """Saldo pendiente de un trabajo = precio_venta - pagos asociados a ese trabajo.

    Cuenta tanto los movimientos de pago como los cheques recibidos del trabajo.
    """
    pagado = _monto_pagos(movimientos_trabajo) + _monto_cheques_recibidos(cheques_trabajo)
    return Q2(Q2(precio_venta) - pagado)


def calcular_saldo_cliente(
    trabajos: Iterable, movimientos: Iterable, cheques: Iterable = ()
) -> Tuple[Decimal, Decimal, Decimal]:
    """Devuelve (total_facturado, total_pagado, saldo) de un cliente.

    total_facturado = suma de precio_venta de trabajos no cancelados.
    total_pagado    = movimientos de tipo 'Pago' + cheques recibidos no rechazados.
    """
    total_facturado = CERO
    for t in trabajos:
        if getattr(t, "estado", None) != "Cancelado" and t.precio_venta is not None:
            total_facturado += Q2(t.precio_venta)
    total_facturado = Q2(total_facturado)
    total_pagado = Q2(_monto_pagos(movimientos) + _monto_cheques_recibidos(cheques))
    saldo = Q2(total_facturado - total_pagado)
    return total_facturado, total_pagado, saldo


def ingresos_reales(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Decimal:
    """Plata efectivamente cobrada en el período.

    = movimientos 'Pago' con método distinto de Cheque (por su fecha)
    + cheques Recibidos en estado 'Cobrado' (por su fecha de cobro).
    """
    total = CERO
    for m in movimientos:
        if getattr(m, "tipo", None) != "Pago" or m.monto is None:
            continue
        if _metodo_es_cheque(getattr(m, "metodo", None)):
            continue
        if en_periodo(_a_fecha(m.fecha)):
            total += Q2(m.monto)
    for ch in cheques:
        if getattr(ch, "clasificacion", "Recibido") != "Recibido":
            continue
        if getattr(ch, "estado", None) != "Cobrado" or ch.monto is None:
            continue
        if en_periodo(_a_fecha(ch.fecha_cobro)):
            total += Q2(ch.monto)
    return Q2(total)


def _cobrado_por_trabajo(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Mapping[str, Decimal]:
    """Plata cobrada en el período, agrupada por trabajo (misma regla que ingresos)."""
    cobrado: dict[str, Decimal] = {}
    for m in movimientos:
        if getattr(m, "tipo", None) != "Pago" or m.monto is None or not m.trabajo_id:
            continue
        if _metodo_es_cheque(getattr(m, "metodo", None)):
            continue
        if en_periodo(_a_fecha(m.fecha)):
            cobrado[m.trabajo_id] = cobrado.get(m.trabajo_id, CERO) + Q2(m.monto)
    for ch in cheques:
        if getattr(ch, "clasificacion", "Recibido") != "Recibido":
            continue
        if getattr(ch, "estado", None) != "Cobrado" or ch.monto is None or not ch.trabajo_id:
            continue
        if en_periodo(_a_fecha(ch.fecha_cobro)):
            cobrado[ch.trabajo_id] = cobrado.get(ch.trabajo_id, CERO) + Q2(ch.monto)
    return cobrado


def ganancia_bruta_realizada(
    presupuestos: Iterable, movimientos: Iterable, cheques: Iterable,
    en_periodo: Callable[[date], bool],
) -> Decimal:
    """Suma de la ganancia proporcional a lo cobrado de cada trabajo.

    Por cada trabajo con presupuesto: cobrado_en_periodo × margen / (100 + margen).
    Un trabajo sin presupuesto asociado no aporta ganancia (su cobro sí es ingreso).
    """
    margen_por_trabajo = {
        p.trabajo_id: p.margen_ganancia for p in presupuestos if p.trabajo_id
    }
    total = CERO
    for trabajo_id, cobrado in _cobrado_por_trabajo(movimientos, cheques, en_periodo).items():
        margen = margen_por_trabajo.get(trabajo_id)
        if margen is None:
            continue
        total += cobrado * fraccion_ganancia(margen)
    return Q2(total)


def total_gastos(gastos: Iterable, en_periodo: Callable[[date], bool]) -> Decimal:
    """Suma de los gastos cuya fecha cae en el período."""
    total = CERO
    for g in gastos:
        if g.monto is not None and en_periodo(_a_fecha(g.fecha)):
            total += Q2(g.monto)
    return Q2(total)
