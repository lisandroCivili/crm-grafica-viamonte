"""Qué puede tocar cada puesto.

El mapa de permisos vive repartido en los `dependencies=` de cada router, así
que acá está escrito de nuevo como tabla: si alguien afloja un permiso sin
querer, este archivo lo canta.

Los roles son puestos, no personas (ver ROLES en seguridad.py):
  admin      -> el dueño de la gráfica
  encargado  -> taller: producción, stock y la planilla de asistencia
  mostrador  -> atención: clientes, trabajos, stock y los gastos del día
"""
import pytest

import models
from conftest import cabecera_rol, crear_cliente, crear_papel, crear_trabajo

ADMIN, ENCARGADO, MOSTRADOR = "admin", "encargado", "mostrador"
EMPLEADOS = [ENCARGADO, MOSTRADOR]


# --- Acceso por módulo ------------------------------------------------------

# (path, roles que SÍ entran). Un GET representativo por módulo: lo que se está
# probando es el permiso del router, no cada endpoint.
LECTURAS = [
    ("/api/clientes/",           [ADMIN, ENCARGADO, MOSTRADOR]),
    ("/api/trabajos/",           [ADMIN, ENCARGADO, MOSTRADOR]),
    ("/api/stock/",              [ADMIN, ENCARGADO, MOSTRADOR]),
    ("/api/clientes/saldos",     [ADMIN]),
    ("/api/movimientos/",        [ADMIN]),
    ("/api/cheques/",            [ADMIN]),
    ("/api/presupuestos/",       [ADMIN]),
    ("/api/reportes/dashboard",  [ADMIN]),
    ("/api/gastos/",             [ADMIN, MOSTRADOR]),
    ("/api/asistencia/planilla", [ADMIN, ENCARGADO]),
    ("/api/empleados/",          [ADMIN, ENCARGADO]),
    ("/api/backup",              [ADMIN]),
]


@pytest.mark.parametrize("path,permitidos", LECTURAS)
@pytest.mark.parametrize("rol", [ADMIN, ENCARGADO, MOSTRADOR])
def test_acceso_por_modulo(client, db, path, permitidos, rol):
    r = client.get(path, headers=cabecera_rol(db, rol))

    if rol in permitidos:
        assert r.status_code == 200, f"{rol} debería poder entrar a {path}"
    else:
        assert r.status_code == 403, f"{rol} NO debería poder entrar a {path}"


def test_sin_token_es_401_y_no_403(client, db):
    """Los dos significan cosas distintas para el frontend: con 401 vuelve a
    pedir usuario y contraseña, con 403 avisa que no le corresponde."""
    del client.headers["Authorization"]

    assert client.get("/api/clientes/").status_code == 401


def test_el_healthcheck_no_pide_token(client, db):
    """Es con lo que el servidor decide si la app está viva. Si pidiera
    credenciales, el deploy quedaría marcado como caído."""
    del client.headers["Authorization"]

    assert client.get("/api/estado").status_code == 200


# --- Borrar es sólo del dueño -----------------------------------------------

class TestBorrado:

    def test_no_borran_clientes(self, client, db):
        cliente = crear_cliente(db)

        r = client.delete(f"/api/clientes/{cliente.id}", headers=cabecera_rol(db, MOSTRADOR))

        assert r.status_code == 403
        assert db.query(models.Cliente).count() == 1

    def test_no_borran_trabajos(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db))

        r = client.delete(f"/api/trabajos/{trabajo.id}", headers=cabecera_rol(db, ENCARGADO))

        assert r.status_code == 403
        assert db.query(models.Trabajo).count() == 1

    def test_no_borran_articulos_de_stock(self, client, db):
        papel = crear_papel(db)

        r = client.delete(f"/api/stock/{papel.id}", headers=cabecera_rol(db, ENCARGADO))

        assert r.status_code == 403
        assert db.query(models.ArticuloStock).count() == 1


# --- El precio de los trabajos ----------------------------------------------

class TestPrecioDeTrabajos:
    """Lo que ve el taller del Kanban. No alcanza con no pintarlo en pantalla:
    el precio viaja en el JSON y se lee desde el navegador."""

    def test_el_dueno_ve_precio_y_costo(self, client, db):
        crear_trabajo(db, crear_cliente(db))

        trabajo = client.get("/api/trabajos/").json()[0]

        assert trabajo["precio_venta"] == "50000.00"
        assert trabajo["costo_total_materiales"] == "20000.00"

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_los_empleados_no_reciben_precio_ni_costo(self, client, db, rol):
        crear_trabajo(db, crear_cliente(db))

        trabajo = client.get("/api/trabajos/", headers=cabecera_rol(db, rol)).json()[0]

        assert trabajo["precio_venta"] is None
        assert trabajo["costo_total_materiales"] is None
        # El resto del trabajo sí lo necesitan: es su pantalla de producción.
        assert trabajo["descripcion_producto"] == "Volantes A5"
        assert trabajo["cantidad"] == 1000

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_editar_un_trabajo_no_le_pisa_el_precio(self, client, db, rol):
        """El caso que rompía de verdad: el formulario de edición manda el
        trabajo entero, y como el campo de precio va oculto llegaba vacío. Sin
        esto, corregir unas tintas le borraba el precio al trabajo."""
        trabajo = crear_trabajo(db, crear_cliente(db))

        r = client.put(
            f"/api/trabajos/{trabajo.id}",
            json={"tintas": "4/4", "precio_venta": 1},
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 200
        db.refresh(trabajo)
        assert trabajo.tintas == "4/4"          # el cambio real sí se guardó
        assert str(trabajo.precio_venta) == "50000.00"   # el precio quedó intacto

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_no_dan_de_alta_trabajos(self, client, db, rol):
        """Crear un trabajo exige ponerle precio, así que es del dueño."""
        cliente = crear_cliente(db)

        r = client.post(
            "/api/trabajos/",
            json={
                "cliente_id": cliente.id,
                "descripcion_producto": "Volantes",
                "cantidad": 100,
                "fecha_creacion": "2026-07-28",
                "precio_venta": 1000,
            },
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 403
        assert db.query(models.Trabajo).count() == 0


# --- Lo que el taller sí tiene que poder hacer ------------------------------

class TestFlujoDelTaller:
    """La contracara: los permisos no pueden dejar al taller sin trabajar."""

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_pueden_dar_de_alta_un_cliente(self, client, db, rol):
        r = client.post(
            "/api/clientes/",
            json={"nombre_completo": "Cliente Nuevo", "dni_cuit": "20111222333", "telefono": "1155667788"},
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 200

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_pueden_iniciar_el_diseno_cobrando_la_sena(self, client, db, rol):
        """Es el mostrador el que recibe la seña cuando el cliente aprueba."""
        trabajo = crear_trabajo(db, crear_cliente(db))

        r = client.post(
            f"/api/trabajos/{trabajo.id}/iniciar-diseno",
            json={"monto": 5000, "metodo": "Efectivo"},
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 200
        db.refresh(trabajo)
        assert trabajo.estado == "En Diseño"
        assert db.query(models.Movimiento).count() == 1

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_pueden_imprimir_la_orden_y_descontar_papel(self, client, db, rol):
        papel = crear_papel(db)
        trabajo = crear_trabajo(db, crear_cliente(db), papel_id=papel.id, cantidad_pliegos=100)

        r = client.post(
            f"/api/trabajos/{trabajo.id}/imprimir-orden",
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 200
        db.refresh(papel)
        assert papel.cantidad == 400   # tenía 500

    @pytest.mark.parametrize("rol", EMPLEADOS)
    def test_pueden_escribir_notas_en_la_ficha(self, client, db, rol):
        cliente = crear_cliente(db)

        r = client.post(
            "/api/notas/",
            json={"cliente_id": cliente.id, "texto": "Llamar antes de entregar"},
            headers=cabecera_rol(db, rol),
        )

        assert r.status_code == 200

    def test_el_mostrador_carga_gastos(self, client, db):
        r = client.post(
            "/api/gastos/",
            json={"categoria": "Flete", "concepto": "Envío centro", "monto": 8000, "fecha": "2026-07-28"},
            headers=cabecera_rol(db, MOSTRADOR),
        )

        assert r.status_code == 200

    def test_el_encargado_guarda_la_planilla_de_asistencia(self, client, db):
        from conftest import crear_empleado

        empleado = crear_empleado(db)

        r = client.post(
            "/api/asistencia/planilla",
            json={
                "fecha": "2026-07-28",
                "filas": [{"empleado_id": empleado.id, "hora_entrada": "08:00", "hora_salida": "17:00"}],
            },
            headers=cabecera_rol(db, ENCARGADO),
        )

        assert r.status_code == 200
