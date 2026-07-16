"""
Cálculos financieros centralizados. Única fuente de verdad para la matemática
del CRM: todo se hace en Decimal y se cuantiza a 2 decimales.

El frontend puede mostrar previews, pero los valores que se persisten y los
saldos que se muestran deben salir de acá.
"""
from decimal import Decimal
from typing import Iterable, Mapping, Optional, Tuple

from money import Q2

CERO = Decimal("0.00")


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


def calcular_saldo_trabajo(precio_venta: Decimal, movimientos_trabajo: Iterable) -> Decimal:
    """Saldo pendiente de un trabajo = precio_venta - pagos asociados a ese trabajo."""
    return Q2(Q2(precio_venta) - _monto_pagos(movimientos_trabajo))


def calcular_saldo_cliente(trabajos: Iterable, movimientos: Iterable) -> Tuple[Decimal, Decimal, Decimal]:
    """Devuelve (total_facturado, total_pagado, saldo) de un cliente.

    total_facturado = suma de precio_venta de trabajos no cancelados.
    total_pagado    = suma de movimientos de tipo 'Pago'.
    """
    total_facturado = CERO
    for t in trabajos:
        if getattr(t, "estado", None) != "Cancelado" and t.precio_venta is not None:
            total_facturado += Q2(t.precio_venta)
    total_facturado = Q2(total_facturado)
    total_pagado = _monto_pagos(movimientos)
    saldo = Q2(total_facturado - total_pagado)
    return total_facturado, total_pagado, saldo
