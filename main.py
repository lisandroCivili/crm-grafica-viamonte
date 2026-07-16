import models
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import engine
# Importamos todos los routers modulares que creamos
from routers import clientes, trabajos, cheques, gastos, presupuestos, stock, movimientos, notas, auth

# Creamos las tablas físicamente en el archivo 'viamonte.db' al iniciar si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Gráfica Viamonte — API Local",
    description="Backend modularizado para la gestión interna del taller",
    version="2.0",
)

# Configuración de CORS: solo los orígenes desde donde realmente se abre la
# interfaz pueden leer respuestas de la API. Antes estaba en "*", lo que
# permitía que CUALQUIER página web visitada en esta compu leyera la API
# (incluido /api/backup, o sea, descargarse la base entera).
ORIGENES_PERMITIDOS = [
    "http://localhost:5500",   # Live Server de VS Code
    "http://127.0.0.1:5500",   # Live Server (variante 127.0.0.1)
    "null",                    # index.html abierto directamente como archivo (file://)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. A todos los demás les clavamos el patovica en la puerta
app.include_router(clientes.router)
app.include_router(presupuestos.router)
app.include_router(trabajos.router)
app.include_router(stock.router)
app.include_router(gastos.router)
app.include_router(cheques.router)
app.include_router(notas.router)
app.include_router(movimientos.router)
app.include_router(auth.router)  # Incluimos el router de autenticación

# ==========================================
# RUTA DE RESPALDO (BACKUP)
# ==========================================
@app.get("/api/backup")
def descargar_respaldo():
    db_path = "viamonte.db"
    
    # Verificamos que el archivo exista por las dudas
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")
    
    # Armamos un nombre de archivo con la fecha de hoy
    fecha_str = datetime.now().strftime("%d-%m-%Y")
    nombre_archivo = f"respaldo_viamonte_{fecha_str}.db"
    
    # Forzamos la descarga del archivo
    return FileResponse(
        path=db_path, 
        filename=nombre_archivo, 
        media_type='application/octet-stream'
    )

# Modelo de validación para el Login sencillo
class LoginRequest(BaseModel):
    usuario: str
    contrasenia: str


# Endpoint de autenticación fija (hardcodeada) para seguridad del sistema
@app.post("/api/login")
def login(datos: LoginRequest):
    USUARIO_CORRECTO = "admin"
    CLAVE_CORRECTA = "viamonte2026"

    if datos.usuario == USUARIO_CORRECTO and datos.contrasenia == CLAVE_CORRECTA:
        return {"status": "success", "message": "Acceso concedido"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos",
    )


@app.get("/")
def estado_servidor():
    return {
        "status": "online",
        "msg": "El backend de Gráfica Viamonte está marchando de diez.",
    }