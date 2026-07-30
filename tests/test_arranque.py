"""Tests del alta automática de usuarios y de migraciones de esquema al arrancar.

Es lo único que separa un deploy funcionando de uno con la puerta cerrada para
todos, o tirando 500 en cualquier pantalla que toque una columna nueva: en el
servidor la base nace vacía o ya viene con datos reales de antes, y no hay
consola donde correr a mano ni el alta de usuarios ni los ALTER TABLE de
migraciones/.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from datetime import datetime, timezone

import models
from arranque import _migrar_columna_archivado, _migrar_entregas_legado, _sembrar
from conftest import crear_cliente, crear_trabajo, crear_usuario
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


# --- Migración de trabajos.archivado ----------------------------------------
#
# Estos tests no usan el fixture `db` de conftest.py: ese arma la base con
# Base.metadata.create_all(), que ya incluye 'archivado' porque está en
# models.py. Para probar el caso real (una base de Railway de antes de esta
# columna) hay que armar a mano una tabla 'trabajos' vieja, sin ella.

def _sesion_con_esquema_viejo(tmp_path):
    """Una base con 'trabajos' tal como quedaba antes de sumar 'archivado'."""
    engine = create_engine(f"sqlite:///{tmp_path / 'vieja.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE trabajos (
                id TEXT PRIMARY KEY,
                cliente_id TEXT NOT NULL,
                descripcion_producto TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                estado TEXT,
                fecha_creacion DATE NOT NULL,
                precio_venta TEXT NOT NULL,
                costo_total_materiales TEXT NOT NULL
            )
            """
        ))
    return sessionmaker(bind=engine)()


def test_agrega_archivado_si_la_base_no_la_tiene(tmp_path):
    """El caso real: una base de Railway deployada antes de esta columna."""
    db = _sesion_con_esquema_viejo(tmp_path)
    db.execute(text(
        "INSERT INTO trabajos VALUES "
        "('t1', 'c1', 'Tarjetas', 100, 'Entregado', '2026-01-01', '1000.00', '500.00')"
    ))
    db.execute(text(
        "INSERT INTO trabajos VALUES "
        "('t2', 'c1', 'Folletos', 200, 'En Producción', '2026-01-01', '2000.00', '900.00')"
    ))
    db.commit()

    _migrar_columna_archivado(db)

    columnas = {fila[1] for fila in db.execute(text("PRAGMA table_info(trabajos)"))}
    assert "archivado" in columnas

    # El ya entregado sale del tablero; el que sigue en curso, no se toca.
    archivado_por_id = dict(db.execute(text("SELECT id, archivado FROM trabajos")).all())
    assert archivado_por_id == {"t1": 1, "t2": 0}


def test_correr_la_migracion_dos_veces_no_rompe_ni_repite(tmp_path):
    """El servidor reinicia el proceso todo el tiempo: el segundo arranque no
    puede fallar por 'la columna ya existe' ni volver a archivar nada."""
    db = _sesion_con_esquema_viejo(tmp_path)
    db.execute(text(
        "INSERT INTO trabajos VALUES "
        "('t1', 'c1', 'Tarjetas', 100, 'Entregado', '2026-01-01', '1000.00', '500.00')"
    ))
    db.commit()

    _migrar_columna_archivado(db)
    _migrar_columna_archivado(db)  # no debe lanzar

    fila = db.execute(text("SELECT archivado FROM trabajos WHERE id = 't1'")).first()
    assert fila[0] == 1


def test_si_la_columna_ya_existe_no_hace_nada(db):
    """Contra la base normal de tests, que ya nace con 'archivado' (modelo
    actual): no tiene que fallar ni re-archivar nada."""
    _migrar_columna_archivado(db)  # no debe lanzar


# --- Backfill de entregas legadas -------------------------------------------
# El caso real: un Trabajo con numero_remito bajo el modelo viejo (un remito
# por trabajo, sin combinar), de antes de que existieran Entrega/ItemEntrega.

def test_migra_un_trabajo_con_numero_remito_legado(db):
    cliente = crear_cliente(db)
    fecha = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
    trabajo = crear_trabajo(
        db, cliente, cantidad=100,
        numero_remito="RE-000007", fecha_remito_impreso=fecha,
    )

    _migrar_entregas_legado(db)

    entrega = db.query(models.Entrega).filter(models.Entrega.numero_remito == "RE-000007").first()
    assert entrega is not None
    assert entrega.cliente_id == cliente.id
    # SQLite guarda el DateTime sin tzinfo (lo devuelve naive): se compara sin ella.
    assert entrega.fecha == fecha.replace(tzinfo=None)

    items = db.query(models.ItemEntrega).filter(models.ItemEntrega.entrega_id == entrega.id).all()
    assert len(items) == 1
    assert items[0].trabajo_id == trabajo.id
    assert items[0].cantidad == 100


def test_no_migra_trabajos_sin_numero_remito(db):
    cliente = crear_cliente(db)
    crear_trabajo(db, cliente, cantidad=50)  # nunca se imprimió remito

    _migrar_entregas_legado(db)

    assert db.query(models.Entrega).count() == 0


def test_correr_el_backfill_dos_veces_no_duplica(db):
    cliente = crear_cliente(db)
    crear_trabajo(db, cliente, cantidad=100, numero_remito="RE-000009")

    _migrar_entregas_legado(db)
    _migrar_entregas_legado(db)  # no debe lanzar ni duplicar

    assert db.query(models.Entrega).count() == 1
    assert db.query(models.ItemEntrega).count() == 1


def test_dos_trabajos_con_el_mismo_numero_remito_legado_no_tumban_el_arranque(db):
    """El sistema viejo no garantizaba unicidad entre trabajos DISTINTOS
    (_generar_numero_remito leía el máximo y sumaba 1 sin ningún lock): dos
    remitos impresos casi al mismo tiempo podían quedar con el mismo número.
    Entrega.numero_remito ahora es unique, así que sin este resguardo el
    backfill (y el arranque del backend) se caería con un IntegrityError.
    """
    cliente = crear_cliente(db)
    t1 = crear_trabajo(db, cliente, cantidad=50, numero_remito="RE-000005")
    t2 = crear_trabajo(db, cliente, cantidad=30, numero_remito="RE-000005")

    _migrar_entregas_legado(db)  # no debe lanzar

    numeros = {e.numero_remito for e in db.query(models.Entrega).all()}
    assert len(numeros) == 2, f"Se esperaban dos números distintos, hay: {numeros}"
    assert "RE-000005" in numeros
    assert any(n.startswith("RE-000005-DUP-") for n in numeros)

    # Ambos trabajos quedaron migrados (ninguno se perdió por la colisión).
    assert db.query(models.ItemEntrega).filter(models.ItemEntrega.trabajo_id == t1.id).count() == 1
    assert db.query(models.ItemEntrega).filter(models.ItemEntrega.trabajo_id == t2.id).count() == 1
