from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# --- ESQUEMAS DE AUDITORÍA ---
# Sólo hay Response: el log lo escribe el backend desde auditoria.asentar() y no
# se puede crear ni editar por API. Por eso no existen AuditoriaCreate ni Update.


class AuditoriaResponse(BaseModel):
    id: str
    fecha: datetime
    # En null sólo cuando el asiento es un intento de ingreso fallido: ahí no hay
    # usuario, pero usuario_nombre igual dice qué nombre se tipeó.
    usuario_id: Optional[str] = None
    usuario_nombre: str
    accion: str
    entidad: str
    entidad_id: Optional[str] = None
    resumen: str
    detalle: Optional[str] = None

    model_config = {"from_attributes": True}
