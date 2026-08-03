import models
import os
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from arranque import aplicar_migraciones_pendientes, promover_usuarios_por_entorno, sembrar_usuarios_iniciales
from database import engine, BASE_DIR
from rutas import ruta_recurso
from seguridad import solo_admin, usuario_actual
# Importamos todos los routers modulares que creamos
from routers import clientes, trabajos, entregas, cheques, gastos, presupuestos, stock, movimientos, notas, auth, reportes, empleados, asistencia, auditoria

# Creamos las tablas físicamente en el archivo 'viamonte.db' al iniciar si no existen
models.Base.metadata.create_all(bind=engine)

# Una base que ya tenía datos antes de una columna nueva no la recibe sola con
# create_all() (ver arranque.py): sin esto, cualquier deploy que sume una
# columna deja la base de Railway desincronizada y tirando 500 hasta que
# alguien corra la migración a mano.
aplicar_migraciones_pendientes()

# En el servidor la base nace vacía y no hay consola para correr el script que
# da de alta a los usuarios: sin esto, el sistema queda deployado y nadie puede
# entrar. En la compu del taller no hace nada (esas variables no existen ahí).
_usuarios_creados = sembrar_usuarios_iniciales()
if _usuarios_creados:
    print(f"Usuarios dados de alta en este arranque: {', '.join(_usuarios_creados)}")

# Promueve a admin a quien esté listado en PROMOVER_A_ADMIN (ver arranque.py).
# No pisa una baja de rol hecha a propósito salvo que la variable siga puesta.
promover_usuarios_por_entorno()

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
    "http://localhost:8000",   # Backend local
    "http://127.0.0.1:8000",   # Backend local (127.0.0.1)
]

# En Railway, agregar el dominio dinámicamente si existe
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if RAILWAY_DOMAIN:
    ORIGENES_PERMITIDOS.extend([
        f"https://{RAILWAY_DOMAIN}",
        f"http://{RAILWAY_DOMAIN}",
    ])
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    # El token viaja en el header Authorization, no en cookie: la API no
    # necesita ni admite credenciales de navegador.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. A todos los demás les clavamos el patovica en la puerta
app.include_router(clientes.router)
app.include_router(presupuestos.router)
app.include_router(trabajos.router)
app.include_router(entregas.router)
app.include_router(stock.router)
app.include_router(gastos.router)
app.include_router(cheques.router)
app.include_router(notas.router)
app.include_router(movimientos.router)
app.include_router(reportes.router)
app.include_router(empleados.router)
app.include_router(asistencia.router)
app.include_router(auditoria.router)
app.include_router(auth.router)  # Incluimos el router de autenticación

# ==========================================
# RUTA DE RESPALDO (BACKUP)
# ==========================================
# Sólo el dueño: este endpoint entrega el archivo de la base ENTERA (clientes,
# precios, saldos, cheques, sueldos) en un solo pedido. Al vivir fuera de los
# routers se saltea todos los permisos de módulo, así que el candado va acá.
@app.get("/api/backup", dependencies=[Depends(solo_admin)])
def descargar_respaldo():
    import sqlite3
    import tempfile

    from starlette.background import BackgroundTask

    db_path = os.path.join(BASE_DIR, "viamonte.db")

    # Verificamos que el archivo exista por las dudas
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")

    # Con WAL activo (ver database.py), los cambios más recientes viven en
    # viamonte.db-wal y no en el .db: copiar el archivo tal cual con
    # FileResponse podía dejar el respaldo incompleto, o directamente a medio
    # escribir si alguien guardaba algo en el momento de la descarga. La API
    # de backup de sqlite3 hace una copia consistente (incluye el WAL) sin
    # bloquear al resto de la aplicación.
    destino = os.path.join(tempfile.gettempdir(), f"respaldo_viamonte_{os.getpid()}.db")
    origen = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    copia = sqlite3.connect(destino)
    try:
        with copia:
            origen.backup(copia)
    finally:
        origen.close()
        copia.close()

    fecha_str = datetime.now().strftime("%d-%m-%Y")
    return FileResponse(
        path=destino,
        filename=f"respaldo_viamonte_{fecha_str}.db",
        media_type="application/octet-stream",
        background=BackgroundTask(os.remove, destino),
    )

# Queda sin token a propósito: es el healthcheck con el que el servidor decide
# si la app está viva. Si pidiera credenciales, el deploy se marcaría caído.
# No toca la base ni devuelve datos.
@app.get("/api/estado")
def estado_servidor():
    return {
        "status": "online",
        "msg": "El backend de Gráfica Viamonte está marchando de diez.",
    }


# ==========================================
# MANUAL DE USUARIO
# ==========================================
@app.get("/api/manual", response_class=PlainTextResponse,
         dependencies=[Depends(usuario_actual)])
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

    # En producción (Railway) usar 0.0.0.0 y puerto de variable de entorno
    # En desarrollo usar localhost:8000
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))

    # Solo abrir navegador en desarrollo
    if host == "127.0.0.1":
        def abrir_navegador():
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        print("=" * 60)
        print(" Gráfica Viamonte — Sistema iniciando...")
        print(" En unos segundos se va a abrir solo en el navegador.")
        print(" NO CIERRES ESTA VENTANA mientras estés trabajando.")
        print(" Para apagar el sistema, cerrá esta ventana.")
        print("=" * 60)

        threading.Thread(target=abrir_navegador, daemon=True).start()
    else:
        print("=" * 60)
        print(" Gráfica Viamonte — Sistema iniciando en producción...")
        print("=" * 60)

    uvicorn.run(app, host=host, port=port)