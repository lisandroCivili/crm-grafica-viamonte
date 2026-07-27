from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

from .comun import _validar_monto_no_negativo

# --- ESQUEMAS PARA MOVIMIENTOS ---
class MovimientoCreate(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    monto: Decimal
    tipo: str
    metodo: Optional[str] = None
    descripcion: str

    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)

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

    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)
