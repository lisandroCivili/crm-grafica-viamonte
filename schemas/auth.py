from pydantic import BaseModel, Field

# --- ESQUEMAS PARA AUTENTICACIÓN ---

class LoginRequest(BaseModel):
    usuario: str
    # bcrypt ignora todo lo que pase de 72 bytes. Cortar acá evita la falsa
    # sensación de que una contraseña larguísima protege más de lo que protege.
    password: str = Field(min_length=4, max_length=72)


class UsuarioResponse(BaseModel):
    """Los datos del usuario que el frontend necesita. Nunca el hash."""
    id: str
    nombre: str
    rol: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Lo que devuelve el login: el token y quién entró.

    El usuario viaja junto al token para que el frontend no tenga que decodificar
    el JWT ni pedir /me enseguida sólo para saber qué rol mostrar.
    """
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse
