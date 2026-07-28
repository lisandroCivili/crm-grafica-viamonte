"""Login y datos de la sesión.

Antes acá vivía un usuario fijo escrito en el código y la respuesta era un
{"acceso": True} que el backend nunca volvía a mirar: cualquiera que conociera
la URL entraba directo a la API sin pasar por el login. Ahora los usuarios están
en la base con la contraseña hasheada y el login devuelve un token que viaja en
cada pedido.

Las piezas de seguridad (hash, token, dependencies) viven en seguridad.py.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from models import ahora_local
from seguridad import crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    nombre = data.usuario.strip().lower()
    usuario = db.query(models.Usuario).filter(models.Usuario.nombre == nombre).first()

    # Un solo mensaje para los tres casos (no existe, contraseña mal, dado de
    # baja): distinguirlos le confirmaría a un desconocido qué nombres de
    # usuario existen de verdad.
    if (
        usuario is None
        or not usuario.activo
        or not verificar_password(data.password, usuario.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    usuario.ultimo_login = ahora_local()
    db.commit()
    db.refresh(usuario)

    return schemas.TokenResponse(access_token=crear_token(usuario), usuario=usuario)


@router.get("/me", response_model=schemas.UsuarioResponse)
def datos_de_la_sesion(usuario: models.Usuario = Depends(usuario_actual)):
    """Quién es el dueño del token guardado en el navegador.

    El frontend lo llama al abrir el sistema: si responde 401, el token venció y
    hay que volver a mostrar el login en vez de arrancar una app que no va a
    poder pedir ningún dato.
    """
    return usuario
