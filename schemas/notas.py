from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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
