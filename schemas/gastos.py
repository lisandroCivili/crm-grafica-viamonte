from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
from decimal import Decimal

from .comun import _validar_monto_no_negativo

# --- ESQUEMAS PARA GASTOS ---
class GastoBase(BaseModel):
    categoria: str
    concepto: str
    monto: Decimal
    fecha: date
    metodo_pago: str = "Efectivo"
    comprobante: str = "Sin comprobante"
    responsable: str = "General"
    trabajo_id: Optional[str] = None

    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)

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
    responsable: Optional[str] = None
    trabajo_id: Optional[str] = None

    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)
