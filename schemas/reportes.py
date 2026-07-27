from pydantic import BaseModel
from decimal import Decimal

# --- ESQUEMAS DE REPORTES E INFORMES ---

# Fila del "Informe general de trabajos a clientes". Se arma a partir de los
# presupuestos, cruzando el trabajo asociado (si ya se convirtió). Los campos
# vienen listos para renderizar en la tabla del PDF; "Pendiente"/"-"/"" según
# corresponda para los presupuestos que todavía no son trabajo.
class InformeTrabajoRow(BaseModel):
    nro_trabajo: str
    fecha_entrada: str
    cliente: str
    descripcion_material: str
    gramaje: str
    colores: str
    cantidad: int
    fecha_entrega: str
    dias_produccion: str
    estado: str
    cobrado: bool
    observaciones: str


# --- ESQUEMA PARA SALDO DE CLIENTE (calculado por el backend) ---
class SaldoResponse(BaseModel):
    cliente_id: str
    total_facturado: Decimal
    total_pagado: Decimal
    saldo: Decimal


# --- ESQUEMA PARA EL DASHBOARD (KPIs financieros calculados por el backend) ---
class MorosoResponse(BaseModel):
    trabajo_id: str
    descripcion_producto: str
    saldo_pendiente: Decimal


class DashboardResponse(BaseModel):
    # Plata realmente cobrada en el período (pagos no-cheque + cheques cobrados).
    ingresos: Decimal
    # Parte de esos ingresos que no está imputada a ningún trabajo. Es plata real
    # que entró pero que no aporta ganancia (sin trabajo no hay presupuesto del
    # cual sacar el costo). Se expone para que quede visible y se pueda imputar
    # después, en vez de perderse entre ingresos y ganancia.
    ingresos_sin_imputar: Decimal = Decimal("0")
    # Gastos del período: toda la plata que salió de la caja.
    egresos: Decimal
    # Parte de los egresos que NO resta de la ganancia porque su costo ya estaba
    # contemplado en el margen de un presupuesto. Se expone para poder explicar
    # en el dashboard por qué la ganancia no es ingresos - egresos.
    costos_presupuestados: Decimal = Decimal("0")
    # Suma de la ganancia proporcional a lo cobrado de cada trabajo con
    # presupuesto, menos los gastos del período que sí restan.
    ganancia_neta: Decimal
    # Conteos actuales (snapshot, no dependen del período).
    trabajos_pendientes: int
    trabajos_sin_presupuesto: int
    # Trabajos entregados del período con saldo sin cobrar (incluye cheques
    # recibidos no rechazados como pago, igual que el saldo de la ficha).
    plata_en_la_calle: Decimal = Decimal("0")
    morosos: list[MorosoResponse] = []
