"""Infraestructura compartida de los tests de routers.

Cada test corre contra una base SQLite propia en un archivo temporal, no contra
viamonte.db. Se usa archivo y no ':memory:' porque los tests de concurrencia
necesitan dos sesiones viendo la misma base, y una base en memoria es privada
de cada conexión.

El PRAGMA de foreign keys se replica acá a propósito: el listener de
database.py está atado a SU engine, así que un engine nuevo nace con las FK
desactivadas y los tests dejarían de ver los errores de integridad que sí
ocurren en producción.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import models
from database import Base, get_db


@pytest.fixture
def db_factory(tmp_path):
    """Devuelve una fábrica de sesiones sobre una base temporal vacía."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _activar_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_factory):
    """TestClient de la app real, con la base apuntando a la temporal."""
    from main import app  # Import tardío: main.py corre create_all al importarse.

    def get_db_test():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_db_test
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db(db_factory):
    """Sesión suelta para preparar datos o verificar el estado final."""
    sesion = db_factory()
    try:
        yield sesion
    finally:
        sesion.close()


# --- Fábricas de datos ------------------------------------------------------
# Crean directamente por ORM y no por la API: lo que se prueba es el endpoint
# bajo test, no el de alta. Devuelven el objeto ya commiteado.

def crear_cliente(db, **overrides):
    datos = dict(nombre_completo="Cliente Test", dni_cuit="20304050607", telefono="1122334455")
    datos.update(overrides)
    cliente = models.Cliente(**datos)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def crear_trabajo(db, cliente, **overrides):
    datos = dict(
        cliente_id=cliente.id,
        descripcion_producto="Volantes A5",
        cantidad=1000,
        estado="Aprobado",
        fecha_creacion=date.today(),
        precio_venta=Decimal("50000"),
        costo_total_materiales=Decimal("20000"),
    )
    datos.update(overrides)
    trabajo = models.Trabajo(**datos)
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def crear_papel(db, **overrides):
    datos = dict(
        nombre="Ilustración 150g",
        cantidad=Decimal("500"),
        unidad="Pliegos",
        costo_unitario=Decimal("100"),
        ultima_actualizacion=date.today(),
    )
    datos.update(overrides)
    papel = models.ArticuloStock(**datos)
    db.add(papel)
    db.commit()
    db.refresh(papel)
    return papel


def crear_cheque(db, cliente, trabajo=None, **overrides):
    datos = dict(
        cliente_id=cliente.id,
        clasificacion="Recibido",
        trabajo_id=trabajo.id if trabajo else None,
        banco="Galicia",
        numero="00012345",
        monto=Decimal("10000"),
        fecha_emision=date.today(),
        fecha_cobro=date.today(),
        estado="En Cartera",
    )
    datos.update(overrides)
    cheque = models.Cheque(**datos)
    db.add(cheque)
    db.commit()
    db.refresh(cheque)
    return cheque


def crear_presupuesto(db, cliente=None, **overrides):
    """cliente es opcional: un presupuesto puede ser un borrador sin cliente."""
    datos = dict(
        cliente_id=cliente.id if cliente else None,
        descripcion="Volantes A5",
        cantidad=1000,
        costo_materiales=Decimal("20000"),
        margen_ganancia=Decimal("50"),
        precio_final=Decimal("30000"),
        estado="Borrador",
        fecha_creacion=date.today(),
    )
    datos.update(overrides)
    presupuesto = models.Presupuesto(**datos)
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)
    return presupuesto
