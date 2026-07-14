import models
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
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

# Configuración de CORS: Permite que tu archivo HTML de la interfaz
# se comunique con el servidor de Python sin bloqueos de seguridad
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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