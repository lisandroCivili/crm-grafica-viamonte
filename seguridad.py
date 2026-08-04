"""Autenticación: hash de contraseñas, tokens JWT y dependencies de acceso.

Vive en la raíz y no en routers/ porque lo importan tanto el router de auth como
(más adelante) el resto de los routers para pedir un rol. Mismo criterio que
database.py, money.py o rutas.py: infraestructura transversal en la raíz.
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import models
from database import get_db
from rutas import DIR_DATOS

ALGORITMO = "HS256"

# Una jornada laboral. Con una hora, el operario se quedaría afuera en medio del
# día y volvería a tipear la contraseña sin que eso proteja nada más.
HORAS_VALIDEZ_TOKEN = 12

# Roles del sistema. Única fuente de verdad, mismo criterio que ESTADOS_TRABAJO
# en models.py: el alta valida contra esta lista y los permisos se escriben con
# estos nombres. Son PUESTOS, no personas: si cambia quién ocupa el puesto se da
# de baja el usuario y se crea otro con el mismo rol.
ROL_ADMIN = "admin"
ROL_ENCARGADO = "encargado"
ROL_MOSTRADOR = "mostrador"
ROLES = [ROL_ADMIN, ROL_ENCARGADO, ROL_MOSTRADOR]


def _clave_secreta() -> str:
    """Clave con la que se firman los tokens.

    En un servidor se define la variable de entorno SECRET_KEY: su disco es
    efímero y un archivo generado se pierde en cada redeploy. En la compu del
    taller no hay forma cómoda de setear variables de entorno, así que se genera
    una vez y se persiste junto a viamonte.db.

    Lo que NO se puede hacer es generarla en cada arranque: los tokens ya
    emitidos quedarían inválidos y todos volverían a la pantalla de login cada
    vez que se reinicia el sistema.
    """
    del_entorno = os.getenv("SECRET_KEY")
    if del_entorno:
        return del_entorno

    ruta = os.path.join(DIR_DATOS, ".secret_key")
    if os.path.exists(ruta):
        with open(ruta) as f:
            guardada = f.read().strip()
        if guardada:
            return guardada

    clave = os.urandom(32).hex()
    with open(ruta, "w") as f:
        f.write(clave)
    return clave


SECRET_KEY = _clave_secreta()


# ==========================================
# CONTRASEÑAS
# ==========================================

def hashear_password(password: str) -> str:
    """Hash bcrypt de una contraseña. Lo único que se guarda en la base."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hash_guardado: str) -> bool:
    """¿La contraseña tipeada corresponde al hash guardado?

    Un hash corrupto o vacío (una fila cargada a mano, por ejemplo) hace que
    bcrypt levante ValueError. Se trata como 'no coincide': el que intenta
    entrar tiene que ver 'contraseña incorrecta', no un 500.
    """
    try:
        return bcrypt.checkpw(password.encode(), hash_guardado.encode())
    except (ValueError, TypeError):
        return False


# Hash de una contraseña que nadie usa. Existe para gastar el mismo tiempo de
# bcrypt cuando el usuario NO existe: sin esto, esa rama corta antes de llegar
# a bcrypt y responde varias veces más rápido, lo que delata qué nombres de
# usuario son reales aunque el login use un solo mensaje de error para los dos
# casos (ver routers/auth.py).
_HASH_SENUELO = hashear_password("contraseña que no le sirve a nadie")


def verificar_password_constante(password: str, hash_guardado: str | None) -> bool:
    """Como verificar_password, pero tarda lo mismo exista o no el usuario."""
    coincide = verificar_password(password, hash_guardado or _HASH_SENUELO)
    return coincide and hash_guardado is not None


# ==========================================
# TOKENS
# ==========================================

def crear_token(usuario: models.Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario.id,
        "nombre": usuario.nombre,
        "rol": usuario.rol,
        "iat": ahora,
        "exp": ahora + timedelta(hours=HORAS_VALIDEZ_TOKEN),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITMO)


# auto_error=False para devolver siempre el mismo 401 con nuestro texto: con el
# default, la falta del header da un 403 que el frontend no distingue de "no
# tenés permiso" y terminaría mostrando el mensaje equivocado.
_bearer = HTTPBearer(auto_error=False)


def _credenciales_invalidas() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión vencida o inválida. Volvé a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """Usuario dueño del token que viene en el header Authorization.

    Se relee de la base en cada request a propósito: si se lo da de baja, queda
    afuera en el acto en vez de seguir entrando hasta que venza el token.
    """
    if credenciales is None:
        raise _credenciales_invalidas()

    try:
        payload = jwt.decode(credenciales.credentials, SECRET_KEY, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        raise _credenciales_invalidas()

    usuario = db.query(models.Usuario).filter(models.Usuario.id == payload.get("sub")).first()
    if usuario is None or not usuario.activo:
        raise _credenciales_invalidas()
    return usuario


def requiere_rol(*roles: str):
    """Dependency que exige uno de los roles indicados.

    Se declara a nivel de router para marcar el piso del módulo y, cuando hace
    falta endurecer un endpoint puntual, se agrega otra en el decorador:

        router = APIRouter(dependencies=[Depends(requiere_rol(*TODOS_LOS_ROLES))])

        @router.delete("/{id}", dependencies=[Depends(solo_admin)])

    FastAPI SUMA las dependencies del router y las del endpoint (no las
    reemplaza), así que hay que cumplir las dos y gana la más restrictiva.
    """
    def verificar(usuario: models.Usuario = Depends(usuario_actual)) -> models.Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para acceder a esta sección.",
            )
        return usuario

    return verificar


# Atajos para no repetir las mismas tuplas en los doce routers.
TODOS_LOS_ROLES = (ROL_ADMIN, ROL_ENCARGADO, ROL_MOSTRADOR)

solo_admin = requiere_rol(ROL_ADMIN)
