from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models, schemas
from database import get_db
from calculos import ingresos_reales, ganancia_bruta_realizada, total_gastos

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
    """
    en_periodo = _predicado_periodo(filtro)

    trabajos = db.query(models.Trabajo).all()
    presupuestos = db.query(models.Presupuesto).all()
    movimientos = db.query(models.Movimiento).all()
    cheques = db.query(models.Cheque).all()
    gastos = db.query(models.Gasto).all()

    ingresos = ingresos_reales(movimientos, cheques, en_periodo)
    egresos = total_gastos(gastos, en_periodo)
    ganancia_bruta = ganancia_bruta_realizada(presupuestos, movimientos, cheques, en_periodo)
    ganancia_neta = ganancia_bruta - egresos

    trabajos_pendientes = sum(1 for t in trabajos if t.estado in ESTADOS_PENDIENTES)

    # Trabajos que no aportan ganancia porque no tienen presupuesto asociado.
    ids_con_presupuesto = {p.trabajo_id for p in presupuestos if p.trabajo_id}
    trabajos_sin_presupuesto = sum(
        1 for t in trabajos
        if t.estado != "Cancelado" and t.id not in ids_con_presupuesto
    )

    return schemas.DashboardResponse(
        ingresos=ingresos,
        egresos=egresos,
        ganancia_neta=ganancia_neta,
        trabajos_pendientes=trabajos_pendientes,
        trabajos_sin_presupuesto=trabajos_sin_presupuesto,
    )
