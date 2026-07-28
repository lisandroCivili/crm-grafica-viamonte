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
from auditoria import asentar
from database import get_db
from models import ahora_local
from seguridad import crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Cómo se llama esto en el registro de auditoría.
ENTIDAD = "Sesión"

# El nombre tipeado en un intento fallido se guarda para poder ver que alguien
# está probando nombres, pero es texto de un desconocido: se recorta para que no
# se pueda usar el log como depósito de lo que se le ocurra.
LARGO_MAXIMO_NOMBRE = 50


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
        # El intento queda asentado sin autor (no hay usuario al que apuntar) y
        # con el nombre tipeado como resumen. LA CONTRASEÑA NO SE GUARDA NUNCA,
        # ni siquiera cuando es evidente que fue un error de tipeo: el log se lee
        # desde una pantalla y quedaría a la vista de quien la tenga abierta.
        #
        # Necesita su propio commit porque el 401 de abajo corta el endpoint: sin
        # esto, la sesión se cierra sin escribir y el intento se pierde justo en
        # el caso en que más interesa verlo.
        asentar(db, None, models.ACCION_INGRESO_FALLIDO, ENTIDAD, None,
                f"intento con el nombre '{nombre[:LARGO_MAXIMO_NOMBRE]}'")
        db.commit()
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    usuario.ultimo_login = ahora_local()
    asentar(db, usuario, models.ACCION_INGRESO, ENTIDAD, usuario.id,
            f"{usuario.nombre} ({usuario.rol}) entró al sistema")
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
