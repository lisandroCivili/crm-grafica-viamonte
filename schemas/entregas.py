from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime

# --- ESQUEMAS PARA ENTREGAS (remitos que pueden combinar varios trabajos) ---
class ItemEntregaCreate(BaseModel):
    trabajo_id: str
    cantidad: int

    @field_validator("cantidad")
    @classmethod
    def _cantidad_positiva(cls, v):
        if v <= 0:
            raise ValueError("La cantidad a entregar tiene que ser mayor a cero.")
        return v


class EntregaCreate(BaseModel):
    cliente_id: str
    items: list[ItemEntregaCreate]

    @model_validator(mode="after")
    def _al_menos_un_item_sin_repetidos(self):
        if not self.items:
            raise ValueError("El remito tiene que tener al menos un trabajo.")
        trabajo_ids = [item.trabajo_id for item in self.items]
        if len(set(trabajo_ids)) != len(trabajo_ids):
            raise ValueError("No se puede repetir el mismo trabajo dos veces en un remito.")
        return self


class ItemEntregaResponse(BaseModel):
    id: str
    entrega_id: str
    trabajo_id: str
    cantidad: int
    numero_remito: str
    fecha: datetime
    model_config = {"from_attributes": True}
