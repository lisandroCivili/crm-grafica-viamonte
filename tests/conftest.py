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
from money import Q2


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


def crear_item(db, presupuesto, **overrides):
    """Agrega un ItemPresupuesto a un presupuesto ya creado y lo commitea."""
    datos = dict(
        presupuesto_id=presupuesto.id,
        orden=len(presupuesto.items),
        descripcion="Volantes A5",
        cantidad=1000,
        precio_unitario=Decimal("30"),
        costo_materiales=Decimal("20000"),
        margen_ganancia=Decimal("50"),
    )
    datos.update(overrides)
    item = models.ItemPresupuesto(**datos)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def crear_presupuesto(db, cliente=None, items=None, **overrides):
    """Crea un presupuesto con sus ítems. cliente es opcional (borrador).

    Retrocompatible: los kwargs de producto/papel/costos que antes vivían en el
    presupuesto (descripcion, cantidad, precio_final, costo_materiales,
    margen_ganancia, detalles_costos, material, gramaje, papel_id,
    cantidad_pliegos) se enrutan a un ÚNICO ítem. precio_final se traduce a
    precio_unitario dividiendo por la cantidad, que es como quedaba antes en el
    PDF. Para varios ítems, pasar items=[dict(...), ...].
    """
    # Campos que ahora viven en el ítem, no en la cabecera. precio_final es un
    # alias histórico que se traduce a precio_unitario más abajo.
    CAMPOS_ITEM = {
        "descripcion", "cantidad", "precio_unitario", "precio_final",
        "costo_materiales", "margen_ganancia", "detalles_costos", "material",
        "gramaje", "papel_id", "cantidad_pliegos",
    }
    item_overrides = {k: overrides.pop(k) for k in list(overrides) if k in CAMPOS_ITEM}

    datos = dict(
        cliente_id=cliente.id if cliente else None,
        estado="Borrador",
        fecha_creacion=date.today(),
    )
    datos.update(overrides)
    presupuesto = models.Presupuesto(**datos)
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)

    if items is None:
        # Un único ítem por defecto, con los overrides retrocompatibles.
        cantidad = item_overrides.get("cantidad", 1000)
        if "precio_unitario" not in item_overrides:
            # precio_final histórico -> precio_unitario, como hacía el PDF.
            precio_final = item_overrides.pop("precio_final", Decimal("30000"))
            item_overrides["precio_unitario"] = Q2(Decimal(str(precio_final)) / cantidad) if cantidad else Decimal(str(precio_final))
        else:
            item_overrides.pop("precio_final", None)
        items = [item_overrides]

    for item_datos in items:
        crear_item(db, presupuesto, **item_datos)

    db.refresh(presupuesto)
    return presupuesto
