from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# --- ESQUEMAS PARA CLIENTES ---

class ClienteBase(BaseModel):
    nombre_completo: str
    nombre_empresa: Optional[str] = None
    dni_cuit: str
    telefono: str
    frecuencia_recompra_dias: Optional[int] = None

# Esquema para cuando recibimos los datos para CREAR un cliente
class ClienteCreate(ClienteBase):
    pass

# Esquema para cuando DEVOLVEMOS los datos del cliente hacia el front-end
class ClienteResponse(ClienteBase):
    id: str

    # Esto le dice a Pydantic que lea los datos directo desde los modelos de SQLAlchemy
    model_config = {"from_attributes": True}

# Esquema para EDITAR un cliente existente (todos los campos opcionales)
class ClienteUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    nombre_empresa: Optional[str] = None
    dni_cuit: Optional[str] = None
    telefono: Optional[str] = None
    frecuencia_recompra_dias: Optional[int] = None

# --- ESQUEMAS PARA TRABAJOS ---
class TrabajoBase(BaseModel):
    cliente_id: str
    descripcion_producto: str
    cantidad: int
    estado: Optional[str] = "Pendiente de Pago"
    fecha_creacion: date
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None
    precio_venta: Decimal
    costo_total_materiales: Decimal
    forma_pago_heredada: Optional[str] = None

class TrabajoCreate(TrabajoBase):
    pass

class TrabajoUpdate(BaseModel):
    estado: Optional[str] = None
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None
    descripcion_producto: Optional[str] = None
    cantidad: Optional[int] = None
    precio_venta: Optional[Decimal] = None

class TrabajoResponse(TrabajoBase):
    id: str
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA PRESUPUESTOS ---
class PresupuestoBase(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    version_de: Optional[str] = None
    numero_secuencia: Optional[str] = None
    descripcion: str
    cantidad: int
    costo_materiales: Decimal
    detalles_costos: Optional[dict] = None
    margen_ganancia: Decimal
    precio_final: Decimal
    estado: Optional[str] = "Borrador"
    convertido_a_trabajo: Optional[bool] = False
    fecha_creacion: date

class PresupuestoCreate(PresupuestoBase):
    # El backend recalcula costo_materiales y precio_final a partir de
    # detalles_costos y margen_ganancia, así que estos pueden venir en 0.
    costo_materiales: Decimal = Decimal("0")
    precio_final: Decimal = Decimal("0")

class PresupuestoResponse(PresupuestoBase):
    id: str
    model_config = {"from_attributes": True}

# Esquema para EDITAR un presupuesto existente (no se permite tocar convertido_a_trabajo/trabajo_id acá)
class PresupuestoUpdate(BaseModel):
    cliente_id: Optional[str] = None
    descripcion: Optional[str] = None
    cantidad: Optional[int] = None
    detalles_costos: Optional[dict] = None
    margen_ganancia: Optional[Decimal] = None
    estado: Optional[str] = None


# --- ESQUEMAS PARA MOVIMIENTOS ---
class MovimientoCreate(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    monto: Decimal
    tipo: str
    metodo: Optional[str] = None
    descripcion: str

class MovimientoResponse(MovimientoCreate):
    id: str
    fecha: datetime
    model_config = {"from_attributes": True}

# Esquema para EDITAR un movimiento existente (corrección de pagos mal cargados)
class MovimientoUpdate(BaseModel):
    trabajo_id: Optional[str] = None
    monto: Optional[Decimal] = None
    tipo: Optional[str] = None
    metodo: Optional[str] = None
    descripcion: Optional[str] = None


# --- ESQUEMAS PARA NOTAS ---
class NotaCreate(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    texto: str

class NotaResponse(NotaCreate):
    id: str
    fecha_creacion: datetime
    model_config = {"from_attributes": True}

# Esquema para EDITAR una nota existente
class NotaUpdate(BaseModel):
    texto: str


# --- ESQUEMAS PARA GASTOS ---
class GastoBase(BaseModel):
    categoria: str
    concepto: str
    monto: Decimal
    fecha: date
    metodo_pago: str = "Efectivo"
    comprobante: str = "Sin comprobante"
    trabajo_id: Optional[str] = None

class GastoCreate(GastoBase):
    pass

class GastoResponse(GastoBase):
    id: str
    model_config = {"from_attributes": True}

# Esquema para EDITAR un gasto existente
class GastoUpdate(BaseModel):
    categoria: Optional[str] = None
    concepto: Optional[str] = None
    monto: Optional[Decimal] = None
    fecha: Optional[date] = None
    metodo_pago: Optional[str] = None
    comprobante: Optional[str] = None
    trabajo_id: Optional[str] = None


# --- ESQUEMAS PARA STOCK ---
class StockBase(BaseModel):
    nombre: str
    categoria: Optional[str] = "General"
    proveedor: Optional[str] = None
    cantidad: Decimal
    unidad: str
    stock_minimo: Decimal
    costo_unitario: Decimal
    ultima_actualizacion: date

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    proveedor: Optional[str] = None
    unidad: Optional[str] = None
    stock_minimo: Optional[Decimal] = None
    cantidad: Optional[Decimal] = None
    costo_unitario: Optional[Decimal] = None
    ultima_actualizacion: Optional[date] = None
    motivo: Optional[str] = "Ajuste rápido"

class StockResponse(StockBase):
    id: str
    model_config = {"from_attributes": True}

class HistorialStockResponse(BaseModel):
    id: str
    articulo_id: str
    diferencia: Decimal
    motivo: str
    fecha: datetime
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA CHEQUES ---
class ChequeBase(BaseModel):
    cliente_id: Optional[str] = None
    banco: str
    numero: str
    monto: Decimal
    fecha_emision: date
    fecha_cobro: date
    estado: str = "En Cartera"
    destinatario_endoso: Optional[str] = None

class ChequeCreate(ChequeBase):
    pass

class ChequeUpdate(BaseModel):
    cliente_id: Optional[str] = None
    banco: Optional[str] = None
    numero: Optional[str] = None
    monto: Optional[Decimal] = None
    fecha_emision: Optional[date] = None
    fecha_cobro: Optional[date] = None
    estado: Optional[str] = None
    destinatario_endoso: Optional[str] = None

class ChequeResponse(ChequeBase):
    id: str
    model_config = {"from_attributes": True}


# --- ESQUEMA PARA SALDO DE CLIENTE (calculado por el backend) ---
class SaldoResponse(BaseModel):
    cliente_id: str
    total_facturado: Decimal
    total_pagado: Decimal
    saldo: Decimal
