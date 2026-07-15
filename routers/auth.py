from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginData(BaseModel):
    usuario: str
    password: str

@router.post("/login")
def login_simple(data: LoginData):
    # Credenciales fijas para la compu del local
    if data.usuario == "admin" and data.password == "viamonte2026":
        return {"acceso": True}
    
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")