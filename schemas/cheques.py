from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

import models
from .comun import _validar_monto_no_negativo

# --- ESQUEMAS PARA CHEQUES ---

def _validar_estado_cheque(valor: Optional[str]) -> Optional[str]:
    """Acota el estado a ESTADOS_CHEQUE. Compartido por Create y Update.

    Antes 'estado' era un str libre: se podía crear o dejar un cheque en
    'banana' y ningún cálculo lo reconocía después.
    """
    if valor is not None and valor not in models.ESTADOS_CHEQUE:
        raise ValueError(
            f"Estado inválido: '{valor}'. Válidos: {', '.join(models.ESTADOS_CHEQUE)}."
        )
    return valor


def _completar_fecha_endoso(datos):
    """Un cheque Endosado sin fecha de endoso nunca cuenta como ingreso.

    Endosar equivale a cobrar, y calculos.py usa fecha_endoso para saber cuándo
    se realizó esa plata: sin ella el cheque queda invisible para siempre. Se
    completa acá y no en el router para que valga igual al crear y al editar.
    """
    if datos.estado == "Endosado" and datos.fecha_endoso is None:
        datos.fecha_endoso = date.today()
    return datos


class ChequeBase(BaseModel):
    cliente_id: Optional[str] = None
    clasificacion: str = "Recibido"   # 'Recibido' (de cliente) o 'Emitido' (a proveedor)
    trabajo_id: Optional[str] = None
    banco: str
    numero: str
    monto: Decimal
    fecha_emision: date
    fecha_cobro: date
    estado: str = models.ESTADO_CHEQUE_INICIAL
    destinatario_endoso: Optional[str] = None
    fecha_endoso: Optional[date] = None

    _estado_valido = field_validator("estado")(_validar_estado_cheque)
    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)

    @model_validator(mode="after")
    def completar_fecha_endoso(self):
        return _completar_fecha_endoso(self)

class ChequeCreate(ChequeBase):
    pass

class ChequeUpdate(BaseModel):
    cliente_id: Optional[str] = None
    clasificacion: Optional[str] = None
    trabajo_id: Optional[str] = None
    banco: Optional[str] = None
    numero: Optional[str] = None
    monto: Optional[Decimal] = None
    fecha_emision: Optional[date] = None
    fecha_cobro: Optional[date] = None
    estado: Optional[str] = None
    destinatario_endoso: Optional[str] = None
    fecha_endoso: Optional[date] = None
    # No es una columna del cheque: justifica revertir un estado final
    # (Cobrado / Endosado / Rechazado) y queda asentado en el historial.
    motivo: Optional[str] = None

    _estado_valido = field_validator("estado")(_validar_estado_cheque)
    _monto_valido = field_validator("monto")(_validar_monto_no_negativo)

    @model_validator(mode="after")
    def completar_fecha_endoso(self):
        return _completar_fecha_endoso(self)

class ChequeResponse(ChequeBase):
    id: str
    model_config = {"from_attributes": True}

class HistorialChequeResponse(BaseModel):
    id: str
    cheque_id: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    detalle: str
    fecha: datetime
    model_config = {"from_attributes": True}
