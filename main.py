from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import models
from database import engine

# Creamos las tablas físicamente en el archivo SQLite al arrancar
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gráfica Viamonte API Local", version="1.0")

# Permitimos que nuestro HTML local se conecte al servidor de Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo de datos para validar el Login sencillo usando Pydantic
class LoginRequest(BaseModel):
    usuario: str
    contrasenia: str

# Endpoint de autenticación hardcodeado para seguridad mínima
@app.post("/api/login")
def login(datos: LoginRequest):
    USUARIO_CORRECTO = "admin"
    CLAVE_CORRECTA = "gviamonte2000"
    
    if datos.usuario == USUARIO_CORRECTO and datos.contrasenia == CLAVE_CORRECTA:
        return {"status": "success", "message": "Acceso concedido"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos"
    )

@app.get("/")
def read_root():
    return {"status": "online", "msg": "Servidor backend de Gráfica Viamonte corriendo localmente."}