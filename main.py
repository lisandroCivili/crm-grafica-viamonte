import models
import os
import sys
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import engine, BASE_DIR
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
    db_path = os.path.join(BASE_DIR, "viamonte.db")
    
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


@app.get("/api/estado")
def estado_servidor():
    return {
        "status": "online",
        "msg": "El backend de Gráfica Viamonte está marchando de diez.",
    }


# ==========================================
# FRONTEND (servido por el propio backend)
# ==========================================
# Cuando corre empaquetado con PyInstaller (--onefile), los archivos que se
# agregan con --add-data se extraen a una carpeta temporal en sys._MEIPASS;
# en desarrollo, usamos la carpeta 'frontend' del proyecto tal cual.
if getattr(sys, "frozen", False):
    FRONTEND_DIR = os.path.join(sys._MEIPASS, "frontend")
else:
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

# Se monta al final y en "/" para que no tape ninguna ruta /api/*: FastAPI
# resuelve las rutas explícitas (los routers de arriba) antes de caer acá.
# html=True hace que "/" sirva index.html automáticamente.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import threading
    import time
    import webbrowser

    import uvicorn

    def abrir_navegador():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")

    print("=" * 60)
    print(" Gráfica Viamonte — Sistema iniciando...")
    print(" En unos segundos se va a abrir solo en el navegador.")
    print(" NO CIERRES ESTA VENTANA mientras estés trabajando.")
    print(" Para apagar el sistema, cerrá esta ventana.")
    print("=" * 60)

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)