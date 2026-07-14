import models
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import engine
from fastapi import Depends
# Importamos todos los routers modulares que creamos
from routers import clientes, trabajos, cheques, gastos, presupuestos, stock, movimientos, notas, auth
from security import verificar_token

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

# 1. El de Auth NO lleva protección (si no, no pueden iniciar sesión)
app.include_router(auth.router)

# 2. A todos los demás les clavamos el patovica en la puerta
app.include_router(clientes.router, dependencies=[Depends(verificar_token)])
app.include_router(presupuestos.router, dependencies=[Depends(verificar_token)])
app.include_router(trabajos.router, dependencies=[Depends(verificar_token)])
app.include_router(stock.router, dependencies=[Depends(verificar_token)])
app.include_router(gastos.router, dependencies=[Depends(verificar_token)])
app.include_router(cheques.router, dependencies=[Depends(verificar_token)])
app.include_router(notas.router, dependencies=[Depends(verificar_token)])
app.include_router(movimientos.router, dependencies=[Depends(verificar_token)])

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