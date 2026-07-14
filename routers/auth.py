from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
import security

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Credenciales fijas para el taller
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "viamonte2026"

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != USUARIO_ADMIN or form_data.password != PASSWORD_ADMIN:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    
    token = security.crear_token_acceso(data={"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}