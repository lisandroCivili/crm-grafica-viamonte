import models
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from database import engine, BASE_DIR
from rutas import ruta_recurso
# Importamos todos los routers modulares que creamos
from routers import clientes, trabajos, cheques, gastos, presupuestos, stock, movimientos, notas, auth, reportes, empleados, asistencia

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
app.include_router(reportes.router)
app.include_router(empleados.router)
app.include_router(asistencia.router)
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

@app.get("/api/estado")
def estado_servidor():
    return {
        "status": "online",
        "msg": "El backend de Gráfica Viamonte está marchando de diez.",
    }


# ==========================================
# MANUAL DE USUARIO
# ==========================================
@app.get("/api/manual", response_class=PlainTextResponse)
def obtener_manual():
    """Devuelve el manual de usuario en Markdown crudo; el frontend lo renderiza.

    docs/manual_usuario.md es la única fuente de verdad (también se lee como
    archivo normal en el repo). ruta_recurso() la resuelve tanto en desarrollo
    como empaquetada con PyInstaller (ver GraficaViamonte.spec: 'docs' viaja
    junto a 'frontend' como recurso de sólo lectura).
    """
    ruta_manual = ruta_recurso("docs", "manual_usuario.md")
    if not os.path.exists(ruta_manual):
        raise HTTPException(status_code=404, detail="Manual no encontrado")
    with open(ruta_manual, "r", encoding="utf-8") as f:
        return f.read()


# ==========================================
# FRONTEND (servido por el propio backend)
# ==========================================
# Empaquetado con PyInstaller el frontend se extrae a una carpeta temporal; en
# desarrollo es la carpeta 'frontend' del proyecto. Eso lo resuelve rutas.py.
FRONTEND_DIR = ruta_recurso("frontend")

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