from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models, schemas
from database import get_db
from calculos import (
    ingresos_reales, ganancia_bruta_realizada, total_gastos,
    total_gastos_operativos, calcular_saldo_trabajo,
)

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])

# Trabajos que siguen "vivos" en el taller (no entregados ni cancelados).
ESTADOS_PENDIENTES = {"Aprobado", "En Diseño", "En Producción"}


def _predicado_periodo(filtro: str):
    """Devuelve una función en_periodo(fecha) -> bool según el filtro elegido.

    Mismos valores que el selector del dashboard: este_mes, mes_pasado,
    este_anio, historico. Cualquier otro valor se trata como histórico.
    """
    hoy = date.today()
    if filtro == "este_mes":
        return lambda f: bool(f) and f.month == hoy.month and f.year == hoy.year
    if filtro == "mes_pasado":
        mes = hoy.month - 1
        anio = hoy.year
        if mes < 1:
            mes = 12
            anio -= 1
        return lambda f: bool(f) and f.month == mes and f.year == anio
    if filtro == "este_anio":
        return lambda f: bool(f) and f.year == hoy.year
    return lambda f: True  # histórico


@router.get("/dashboard", response_model=schemas.DashboardResponse)
def dashboard(filtro: str = "este_mes", db: Session = Depends(get_db)):
    """KPIs financieros del dashboard, calculados por el backend.

    Los ingresos son plata realmente cobrada (pagos no-cheque + cheques
    cobrados) y la ganancia es proporcional a lo cobrado de cada trabajo con
    presupuesto, menos los gastos. Una consulta por tabla y cruce en memoria.

    Egresos y ganancia usan totales de gasto distintos a propósito: egresos es
    toda la plata que salió, mientras que la ganancia no descuenta los costos
    ya contemplados en un presupuesto (estarían restados dos veces). La
    diferencia se expone en costos_presupuestados para poder explicarla.
    """
    en_periodo = _predicado_periodo(filtro)

    trabajos = db.query(models.Trabajo).all()
    presupuestos = db.query(models.Presupuesto).all()
    movimientos = db.query(models.Movimiento).all()
    cheques = db.query(models.Cheque).all()
    gastos = db.query(models.Gasto).all()

    ids_con_presupuesto = {p.trabajo_id for p in presupuestos if p.trabajo_id}

    ingresos = ingresos_reales(movimientos, cheques, en_periodo)
    egresos = total_gastos(gastos, en_periodo)
    gastos_operativos = total_gastos_operativos(gastos, en_periodo, ids_con_presupuesto)
    costos_presupuestados = egresos - gastos_operativos
    ganancia_bruta = ganancia_bruta_realizada(
        presupuestos, trabajos, movimientos, cheques, en_periodo
    )
    ganancia_neta = ganancia_bruta - gastos_operativos

    trabajos_pendientes = sum(1 for t in trabajos if t.estado in ESTADOS_PENDIENTES)

    # Trabajos que no aportan ganancia porque no tienen presupuesto asociado.
    trabajos_sin_presupuesto = sum(
        1 for t in trabajos
        if t.estado != "Cancelado" and t.id not in ids_con_presupuesto
    )

    # Morosos: trabajos entregados del período con saldo sin cobrar. El saldo
    # incluye cheques recibidos no rechazados, igual que la ficha del cliente.
    movs_por_trabajo = defaultdict(list)
    for m in movimientos:
        if m.trabajo_id:
            movs_por_trabajo[m.trabajo_id].append(m)

    cheques_por_trabajo = defaultdict(list)
    for ch in cheques:
        if ch.trabajo_id:
            cheques_por_trabajo[ch.trabajo_id].append(ch)

    plata_en_la_calle = Decimal("0")
    morosos = []
    for t in trabajos:
        if t.estado != "Entregado" or not en_periodo(t.fecha_creacion):
            continue
        saldo = calcular_saldo_trabajo(t.precio_venta, movs_por_trabajo[t.id], cheques_por_trabajo[t.id])
        if saldo > 0:
            plata_en_la_calle += saldo
            morosos.append(schemas.MorosoResponse(
                trabajo_id=t.id,
                descripcion_producto=t.descripcion_producto,
                saldo_pendiente=saldo,
            ))

    return schemas.DashboardResponse(
        ingresos=ingresos,
        egresos=egresos,
        costos_presupuestados=costos_presupuestados,
        ganancia_neta=ganancia_neta,
        trabajos_pendientes=trabajos_pendientes,
        trabajos_sin_presupuesto=trabajos_sin_presupuesto,
        plata_en_la_calle=plata_en_la_calle,
        morosos=morosos,
    )
