"""
Cálculos financieros centralizados. Única fuente de verdad para la matemática
del CRM: todo se hace en Decimal y se cuantiza a 2 decimales.

El frontend puede mostrar previews, pero los valores que se persisten y los
saldos que se muestran deben salir de acá.

POLÍTICA DE GASTOS VS. MARGEN
-----------------------------
El costo de un trabajo presupuestado ya está descontado dentro de su margen: la
ganancia es una fracción de lo cobrado, no "cobrado menos costos". Por eso, si
ese mismo papel se carga además como Gasto, el costo quedaría restado dos veces.

La regla es explícita, no automática: un gasto marcado con la categoría
CATEGORIA_COSTO_PRESUPUESTADO, y cuyo trabajo tenga presupuesto, cuenta como
egreso (salió plata de la caja) pero NO resta de la ganancia. Cualquier otro
gasto -alquiler, sueldos, insumos sueltos, o el costo de un trabajo sin
presupuesto- resta normalmente.

La fracción de ganancia se calcula sobre el precio vigente del trabajo y no
sobre el margen original, porque el precio se puede editar después de aprobado
(ver fraccion_ganancia_efectiva).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Iterable, Iterator, Mapping, Optional, Tuple

from money import Q2

CERO = Decimal("0.00")
CIEN = Decimal("100")

# Categoría de gasto cuyo costo YA está contemplado dentro del margen del
# presupuesto del trabajo (el papel, la tinta, el troquel que se presupuestaron).
# No vuelve a restar de la ganancia -si no, el costo se descontaría dos veces-,
# pero sí es plata que salió de la caja y cuenta como egreso.
CATEGORIA_COSTO_PRESUPUESTADO = "Costo Presupuestado"


def _a_fecha(valor):
    """Normaliza datetime/date a date para comparar contra un período."""
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def _metodo_es_cheque(metodo) -> bool:
    """Un pago abonado con cheque no es plata realizada: se sigue por Cheque."""
    return (metodo or "").strip().lower() == "cheque"


def _fecha_realizacion_cheque(ch):
    """Fecha en la que un cheque Recibido convirtió el papel en plata, o None.

    - 'Cobrado': se acreditó, vale su fecha_cobro.
    - 'Endosado': se usó para pagarle a un proveedor. Endosar es un cobro y un
      pago simultáneos: acá se computa la pata de ingreso (la de egreso es el
      Gasto que se registra al endosar), por eso vale su fecha_endoso.
    Cualquier otro estado todavía no realizó nada.
    """
    if getattr(ch, "clasificacion", "Recibido") != "Recibido" or ch.monto is None:
        return None
    estado = getattr(ch, "estado", None)
    if estado == "Cobrado":
        return ch.fecha_cobro
    if estado == "Endosado":
        return getattr(ch, "fecha_endoso", None)
    return None


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


def fraccion_ganancia_efectiva(
    precio_actual: Optional[Decimal],
    costo_congelado: Optional[Decimal],
    margen: Decimal,
) -> Decimal:
    """Fracción de ganancia real de un trabajo, contemplando ediciones de precio.

    El precio de venta se puede editar después de aprobar el presupuesto (un
    descuento al cliente), pero el costo ya está hundido: no baja con el precio.
    Por eso la fracción se recalcula sobre el precio vigente en vez de usar el
    margen original, que dejaría de ser real: (precio - costo) / precio.

    Si el precio nunca se editó el resultado es idéntico a fraccion_ganancia(margen),
    porque precio = costo * (1 + margen/100).

    Puede dar negativo si se vendió por debajo del costo: es una pérdida real y
    se informa como tal.

    Sin costo congelado (presupuesto viejo o de costo cero) se cae al margen del
    presupuesto, que es el comportamiento histórico.
    """
    if costo_congelado is None or Q2(costo_congelado) <= CERO:
        return fraccion_ganancia(margen)
    precio = Q2(precio_actual) if precio_actual is not None else CERO
    if precio <= CERO:
        return Decimal("0")
    return (precio - Q2(costo_congelado)) / precio


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

    El saldo puede dar NEGATIVO y eso es correcto: significa dinero a favor del
    cliente. Pasa cuando un trabajo señado se cancela (sale de total_facturado
    pero su seña sigue contando como pago) o cuando hay un sobrepago. La regla
    del taller es que esa plata queda a cuenta del próximo trabajo: no se
    devuelve ni se pierde, por eso el cálculo la conserva.

    Pendiente en el frontend: mostrar el saldo negativo como "Saldo a favor" en
    verde, no como deuda en rojo con un signo menos.
    """
    total_facturado = CERO
    for t in trabajos:
        if getattr(t, "estado", None) != "Cancelado" and t.precio_venta is not None:
            total_facturado += Q2(t.precio_venta)
    total_facturado = Q2(total_facturado)
    total_pagado = Q2(_monto_pagos(movimientos) + _monto_cheques_recibidos(cheques))
    saldo = Q2(total_facturado - total_pagado)
    return total_facturado, total_pagado, saldo


def _cobros_realizados(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Iterator[Tuple[Optional[str], Decimal]]:
    """Itera (trabajo_id, monto) de cada cobro realizado en el período.

    Un cobro es plata que efectivamente entró:
    - movimientos 'Pago' con método distinto de Cheque, por su fecha;
    - cheques Recibidos ya realizados, 'Cobrado' por su fecha de cobro o
      'Endosado' por su fecha de endoso (ver _fecha_realizacion_cheque).

    El trabajo_id puede venir en None: tanto un pago como un cheque se pueden
    cobrar sin imputar a un trabajo puntual (un pago a cuenta). Esa plata es
    ingreso, pero no aporta ganancia porque no hay presupuesto contra el cual
    calcularla; ver ingresos_sin_imputar.

    Base común de ingresos_reales, ingresos_sin_imputar y _cobrado_por_trabajo,
    para que las tres no se puedan desincronizar.
    """
    for m in movimientos:
        if getattr(m, "tipo", None) != "Pago" or m.monto is None:
            continue
        if _metodo_es_cheque(getattr(m, "metodo", None)):
            continue
        if en_periodo(_a_fecha(m.fecha)):
            yield getattr(m, "trabajo_id", None), Q2(m.monto)
    for ch in cheques:
        fecha = _fecha_realizacion_cheque(ch)
        if fecha is None:
            continue
        if en_periodo(_a_fecha(fecha)):
            yield getattr(ch, "trabajo_id", None), Q2(ch.monto)


def ingresos_reales(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Decimal:
    """Plata efectivamente cobrada en el período, esté imputada a un trabajo o no."""
    total = CERO
    for _, monto in _cobros_realizados(movimientos, cheques, en_periodo):
        total += monto
    return Q2(total)


def ingresos_sin_imputar(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Decimal:
    """Parte de los ingresos del período que no está imputada a ningún trabajo.

    Es plata real que entró, pero que no aporta ganancia: sin trabajo no hay
    presupuesto del cual sacar el costo. Se expone en el dashboard para que esa
    plata quede visible y se pueda imputar después, en vez de desaparecer entre
    la diferencia de ingresos y ganancia.

    Siempre es <= ingresos_reales sobre el mismo período.
    """
    total = CERO
    for trabajo_id, monto in _cobros_realizados(movimientos, cheques, en_periodo):
        if not trabajo_id:
            total += monto
    return Q2(total)


def _cobrado_por_trabajo(
    movimientos: Iterable, cheques: Iterable, en_periodo: Callable[[date], bool]
) -> Mapping[str, Decimal]:
    """Plata cobrada en el período, agrupada por trabajo (misma regla que ingresos).

    Los cobros sin trabajo imputado quedan afuera: no hay a qué sumarlos.
    """
    cobrado: dict[str, Decimal] = {}
    for trabajo_id, monto in _cobros_realizados(movimientos, cheques, en_periodo):
        if not trabajo_id:
            continue
        cobrado[trabajo_id] = cobrado.get(trabajo_id, CERO) + monto
    return cobrado


def ganancia_bruta_realizada(
    presupuestos: Iterable, trabajos: Iterable, movimientos: Iterable,
    cheques: Iterable, en_periodo: Callable[[date], bool],
) -> Decimal:
    """Suma de la ganancia proporcional a lo cobrado de cada trabajo.

    Por cada trabajo con presupuesto: cobrado_en_periodo × fracción de ganancia,
    donde la fracción sale del precio vigente del trabajo y del costo congelado
    en su presupuesto (ver fraccion_ganancia_efectiva).
    Un trabajo sin presupuesto asociado no aporta ganancia (su cobro sí es ingreso).

    El costo se toma del presupuesto y no de Trabajo.costo_total_materiales
    porque un trabajo cargado a mano y vinculado a un presupuesto después tiene
    ese campo en cero, lo que daría una ganancia del 100%.
    """
    datos_por_trabajo = {
        p.trabajo_id: (p.margen_ganancia, p.costo_materiales)
        for p in presupuestos if p.trabajo_id
    }
    precio_por_trabajo = {t.id: t.precio_venta for t in trabajos}

    total = CERO
    for trabajo_id, cobrado in _cobrado_por_trabajo(movimientos, cheques, en_periodo).items():
        datos = datos_por_trabajo.get(trabajo_id)
        if datos is None:
            continue
        margen, costo = datos
        precio = precio_por_trabajo.get(trabajo_id)
        total += cobrado * fraccion_ganancia_efectiva(precio, costo, margen)
    return Q2(total)


def total_gastos(gastos: Iterable, en_periodo: Callable[[date], bool]) -> Decimal:
    """Suma de los gastos cuya fecha cae en el período.

    Son todos los egresos: la plata que realmente salió de la caja, incluidos
    los costos que ya estaban presupuestados.
    """
    total = CERO
    for g in gastos:
        if g.monto is not None and en_periodo(_a_fecha(g.fecha)):
            total += Q2(g.monto)
    return Q2(total)


def total_gastos_operativos(
    gastos: Iterable, en_periodo: Callable[[date], bool],
    ids_trabajos_con_presupuesto: Iterable[str],
) -> Decimal:
    """Gastos del período que restan de la ganancia (alquiler, sueldos, insumos sueltos).

    Quedan afuera los gastos marcados como 'Costo Presupuestado' de un trabajo
    que tiene presupuesto: ese costo ya está descontado dentro del margen, así
    que volver a restarlo lo contaría dos veces.

    Que el trabajo tenga presupuesto es la red de seguridad de la regla: si un
    gasto quedó marcado como costeado pero su trabajo no tiene presupuesto, ese
    costo nunca estuvo dentro de ningún margen y resta normalmente, en vez de
    desaparecer e inflar la ganancia.
    """
    con_presupuesto = set(ids_trabajos_con_presupuesto)
    total = CERO
    for g in gastos:
        if g.monto is None or not en_periodo(_a_fecha(g.fecha)):
            continue
        if g.categoria == CATEGORIA_COSTO_PRESUPUESTADO and g.trabajo_id in con_presupuesto:
            continue
        total += Q2(g.monto)
    return Q2(total)
