"""Tests del login y de las piezas de seguridad.

Lo que más se cuida acá es que la puerta no se abra por caminos laterales: un
usuario dado de baja, un token vencido o retocado a mano, o un rol que no
alcanza. Antes esto no existía: el backend devolvía un {"acceso": True} que
nunca volvía a mirar, y cualquiera podía saltearse el login entrando directo a
la API.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

import models
import seguridad
from conftest import crear_usuario


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, usuario, password):
    return client.post("/api/auth/login", json={"usuario": usuario, "password": password})


# --- Login ------------------------------------------------------------------

class TestLogin:

    def test_devuelve_token_y_rol_con_credenciales_correctas(self, client, db):
        crear_usuario(db, nombre="lisandro", rol="admin", password="secreta123")

        r = login(client, "lisandro", "secreta123")

        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer"
        assert r.json()["access_token"]
        assert r.json()["usuario"]["nombre"] == "lisandro"
        assert r.json()["usuario"]["rol"] == "admin"

    def test_no_devuelve_el_hash_de_la_contrasena(self, client, db):
        crear_usuario(db, nombre="lisandro", password="secreta123")

        r = login(client, "lisandro", "secreta123")

        assert "password_hash" not in r.json()["usuario"]

    def test_rechaza_la_contrasena_incorrecta(self, client, db):
        crear_usuario(db, nombre="lisandro", password="secreta123")

        assert login(client, "lisandro", "otracosa").status_code == 401

    def test_rechaza_un_usuario_que_no_existe(self, client, db):
        assert login(client, "fantasma", "secreta123").status_code == 401

    def test_rechaza_un_usuario_dado_de_baja(self, client, db):
        """Aunque la contraseña sea la correcta: dar de baja tiene que dejar
        afuera, si no la baja es puramente decorativa."""
        crear_usuario(db, nombre="exempleado", password="secreta123", activo=False)

        assert login(client, "exempleado", "secreta123").status_code == 401

    def test_el_nombre_no_distingue_mayusculas_ni_espacios(self, client, db):
        """El usuario tipea como le sale; el nombre se guarda normalizado."""
        crear_usuario(db, nombre="marcos", password="secreta123")

        assert login(client, "  MARCOS ", "secreta123").status_code == 200

    def test_guarda_la_contrasena_hasheada(self, client, db):
        crear_usuario(db, nombre="lisandro", password="secreta123")

        guardado = db.query(models.Usuario).filter(models.Usuario.nombre == "lisandro").first()
        assert guardado.password_hash != "secreta123"
        assert seguridad.verificar_password("secreta123", guardado.password_hash)

    def test_registra_el_ultimo_login(self, client, db):
        usuario = crear_usuario(db, nombre="lisandro", password="secreta123")
        assert usuario.ultimo_login is None

        login(client, "lisandro", "secreta123")

        db.refresh(usuario)
        assert usuario.ultimo_login is not None


# --- Datos de la sesión (/me) -----------------------------------------------

class TestSesion:

    def test_devuelve_el_usuario_del_token(self, client, db):
        crear_usuario(db, nombre="marcos", rol="encargado", password="secreta123")
        token = login(client, "marcos", "secreta123").json()["access_token"]

        r = client.get("/api/auth/me", headers=headers(token))

        assert r.status_code == 200
        assert r.json()["nombre"] == "marcos"
        assert r.json()["rol"] == "encargado"

    def test_rechaza_el_pedido_sin_header(self, client, db):
        # El client del conftest viene logueado como admin: para probar que sin
        # credenciales no se entra, hay que sacarle el header.
        del client.headers["Authorization"]

        assert client.get("/api/auth/me").status_code == 401

    def test_rechaza_un_token_retocado(self, client, db):
        crear_usuario(db, nombre="lucio", rol="mostrador", password="secreta123")
        token = login(client, "lucio", "secreta123").json()["access_token"]

        # Se le cambia el PRIMER caracter de la firma. Tocar el último no sirve:
        # la firma son 32 bytes en 43 caracteres base64url, y los últimos bits
        # del último caracter no representan nada, así que cambiarlo suele dar
        # exactamente los mismos bytes y el token sigue siendo válido.
        cabecera, payload, firma = token.split(".")
        otra_firma = ("a" if firma[0] != "a" else "b") + firma[1:]

        adulterado = f"{cabecera}.{payload}.{otra_firma}"

        assert client.get("/api/auth/me", headers=headers(adulterado)).status_code == 401

    def test_rechaza_un_token_firmado_con_otra_clave(self, client, db):
        """El caso que importa de verdad: alguien se fabrica un token con el rol
        que quiere. Sin verificar la firma, entraría como admin."""
        usuario = crear_usuario(db, nombre="lucio", rol="mostrador")
        falso = jwt.encode(
            {"sub": usuario.id, "rol": "admin",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "otra-clave-cualquiera",
            algorithm=seguridad.ALGORITMO,
        )

        assert client.get("/api/auth/me", headers=headers(falso)).status_code == 401

    def test_rechaza_un_token_vencido(self, client, db):
        usuario = crear_usuario(db, nombre="lucio")
        vencido = jwt.encode(
            {"sub": usuario.id, "rol": usuario.rol,
             "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            seguridad.SECRET_KEY,
            algorithm=seguridad.ALGORITMO,
        )

        assert client.get("/api/auth/me", headers=headers(vencido)).status_code == 401

    def test_el_token_deja_de_servir_si_dan_de_baja_al_usuario(self, client, db):
        """El token sigue siendo válido y sin vencer, pero el usuario ya no
        trabaja acá. Por eso se relee de la base en cada pedido."""
        usuario = crear_usuario(db, nombre="exempleado", password="secreta123")
        token = login(client, "exempleado", "secreta123").json()["access_token"]
        assert client.get("/api/auth/me", headers=headers(token)).status_code == 200

        usuario.activo = False
        db.commit()

        assert client.get("/api/auth/me", headers=headers(token)).status_code == 401


# --- Roles ------------------------------------------------------------------

class TestRequiereRol:
    """requiere_rol() todavía no la usa ningún router (los permisos por módulo
    son el paso siguiente), así que se la prueba directo."""

    def test_deja_pasar_al_rol_habilitado(self, db):
        usuario = crear_usuario(db, nombre="lisandro", rol="admin")

        verificar = seguridad.requiere_rol("admin")

        assert verificar(usuario=usuario) is usuario

    def test_deja_pasar_si_es_uno_de_varios_roles(self, db):
        usuario = crear_usuario(db, nombre="marcos", rol="encargado")

        verificar = seguridad.requiere_rol("admin", "encargado")

        assert verificar(usuario=usuario) is usuario

    def test_corta_al_rol_que_no_corresponde(self, db):
        usuario = crear_usuario(db, nombre="lucio", rol="mostrador")

        verificar = seguridad.requiere_rol("admin")

        with pytest.raises(HTTPException) as error:
            verificar(usuario=usuario)
        assert error.value.status_code == 403
