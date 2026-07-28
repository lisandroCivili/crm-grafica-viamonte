"""Tests del alta automática de usuarios al arrancar.

Es lo único que separa un deploy funcionando de uno con la puerta cerrada para
todos: en el servidor la base nace vacía y no hay consola donde correr el script
que da de alta a la gente.
"""
import pytest

import models
from arranque import _sembrar
from conftest import crear_usuario
from seguridad import verificar_password


@pytest.fixture
def con_claves(monkeypatch):
    """Las tres variables de entorno cargadas, como quedan en el servidor."""
    monkeypatch.setenv("CLAVE_INICIAL_FACUNDO", "clave-del-dueño")
    monkeypatch.setenv("CLAVE_INICIAL_MARCOS", "clave-del-encargado")
    monkeypatch.setenv("CLAVE_INICIAL_LUCIO", "clave-del-mostrador")


@pytest.fixture
def sin_claves(monkeypatch):
    """Ninguna variable definida: es como corre en la compu del taller."""
    for variable in ("CLAVE_INICIAL_FACUNDO", "CLAVE_INICIAL_MARCOS", "CLAVE_INICIAL_LUCIO"):
        monkeypatch.delenv(variable, raising=False)


def test_crea_los_tres_puestos_en_una_base_vacia(db, con_claves):
    creados = _sembrar(db)

    assert creados == ["facundo", "marcos", "lucio"]
    roles = {u.nombre: u.rol for u in db.query(models.Usuario).all()}
    assert roles == {"facundo": "admin", "marcos": "encargado", "lucio": "mostrador"}


def test_la_contrasena_queda_hasheada_y_sirve_para_entrar(db, con_claves):
    _sembrar(db)

    facundo = db.query(models.Usuario).filter(models.Usuario.nombre == "facundo").first()
    assert facundo.password_hash != "clave-del-dueño"
    assert verificar_password("clave-del-dueño", facundo.password_hash)


def test_sin_variables_no_crea_nada(db, sin_claves):
    """En la compu del taller los usuarios se dan de alta con el script, que
    pide las contraseñas por teclado. Acá no tiene que meterse."""
    assert _sembrar(db) == []
    assert db.query(models.Usuario).count() == 0


def test_arrancar_dos_veces_no_duplica_ni_pisa(db, con_claves):
    """El servidor reinicia el proceso todo el tiempo (cada deploy, cada
    restart): el segundo arranque no puede tocar lo que ya está."""
    _sembrar(db)

    assert _sembrar(db) == []
    assert db.query(models.Usuario).count() == 3


def test_no_le_cambia_la_contrasena_a_quien_ya_existe(db, con_claves):
    """Si Facundo cambió su contraseña, un reinicio no puede volverla atrás."""
    crear_usuario(db, nombre="facundo", rol="admin", password="la-que-el-eligio")

    creados = _sembrar(db)

    assert "facundo" not in creados
    facundo = db.query(models.Usuario).filter(models.Usuario.nombre == "facundo").first()
    assert verificar_password("la-que-el-eligio", facundo.password_hash)


def test_crea_solo_los_que_tienen_variable_definida(db, sin_claves, monkeypatch):
    """Para dar de alta a uno solo más adelante, alcanza con su variable."""
    monkeypatch.setenv("CLAVE_INICIAL_LUCIO", "clave-del-mostrador")

    assert _sembrar(db) == ["lucio"]
    assert db.query(models.Usuario).count() == 1
