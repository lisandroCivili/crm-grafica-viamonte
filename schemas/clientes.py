from pydantic import BaseModel
from typing import Optional

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
