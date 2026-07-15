# from fastapi import APIRouter
# from fastapi.responses import FileResponse
# import os
# from datetime import datetime

# router = APIRouter(prefix="/api/respaldo", tags=["Respaldo"])

# @router.get("/descargar")
# def descargar_backup():
#     db_path = "viamonte.db"
    
#     # Verificamos que el archivo exista por las dudas
#     if not os.path.exists(db_path):
#         return {"error": "Base de datos no encontrada"}
    
#     # Le armamos un nombre lindo con la fecha de hoy
#     fecha_str = datetime.now().strftime("%d-%m-%Y")
#     nombre_archivo = f"respaldo_viamonte_{fecha_str}.db"
    
#     # FileResponse le dice al navegador "descargá este archivo, no lo intentes leer"
#     return FileResponse(path=db_path, filename=nombre_archivo, media_type='application/octet-stream')