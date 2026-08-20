from pydantic import BaseModel
from datetime import datetime

# --- ESQUEMAS PARA ARCHIVOS ADJUNTOS DE UN TRABAJO ---
# No hay ArchivoTrabajoCreate/Update: la subida es multipart (UploadFile), no
# JSON — el router arma la fila directo con lo que trae el archivo.
class ArchivoTrabajoResponse(BaseModel):
    id: str
    trabajo_id: str
    nombre_original: str
    content_type: str
    tamano_bytes: int
    fecha_subida: datetime
    model_config = {"from_attributes": True}
