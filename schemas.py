from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import date

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

# --- ESQUEMAS PARA TRABAJOS ---
class TrabajoBase(BaseModel):
    cliente_id: str
    descripcion_producto: str
    cantidad: int
    estado: Optional[str] = "Pendiente de Pago"
    fecha_creacion: date
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None
    precio_venta: float
    costo_total_materiales: float
    monto_abonado: Optional[float] = 0.0
    forma_pago_heredada: Optional[str] = None

class TrabajoCreate(TrabajoBase):
    pass

class TrabajoUpdate(BaseModel):
    # Esquema específico para cuando movemos la tarjetita en el tablero Kanban
    estado: Optional[str] = None
    monto_abonado: Optional[float] = None
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None

class TrabajoResponse(TrabajoBase):
    id: str
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA PRESUPUESTOS ---
class PresupuestoBase(BaseModel):
    cliente_id: str
    detalle_costos_interno: Dict[str, Any] # Recibe el JSON con el desglose
    porcentaje_ganancia: float
    precio_final_neto: float
    fecha_emision: date
    metodo_pago_elegido: str
    recargo_descuento_porcentaje: Optional[float] = 0.0

class PresupuestoCreate(PresupuestoBase):
    pass

class PresupuestoResponse(PresupuestoBase):
    id: str
    numero_secuencia: str
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA CHEQUES ---
class ChequeBase(BaseModel):
    tipo: str # "Recibido" o "Emitido"
    numero_cheque: str
    banco: str
    monto: float
    fecha_cobro: date
    estado: Optional[str] = "Pendiente"

class ChequeCreate(ChequeBase):
    pass

class ChequeUpdate(BaseModel):
    estado: str # Para pasarlo rápido a "Cobrado" o "Rechazado"

class ChequeResponse(ChequeBase):
    id: str
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA GASTOS ---
class GastoBase(BaseModel):
    concepto: str
    categoria: str
    monto: float
    fecha: date

class GastoCreate(GastoBase):
    pass

class GastoResponse(GastoBase):
    id: str
    model_config = {"from_attributes": True}


# --- ESQUEMAS PARA STOCK ---
class StockBase(BaseModel):
    material: str
    cantidad_actual: float
    cantidad_minima: float
    unidad: str

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    # Ideal para sumar insumos cuando llega mercadería o restar cuando sale un trabajo
    cantidad_actual: float 

class StockResponse(StockBase):
    id: str
    model_config = {"from_attributes": True}