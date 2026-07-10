import models
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import engine
# Importamos todos los routers modulares que creamos
from routers import clientes, presupuestos, trabajos

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

# Registro de los Routers en la aplicación principal
app.include_router(clientes.router)
app.include_router(trabajos.router)
app.include_router(presupuestos.router)


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