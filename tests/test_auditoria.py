"""El registro de quién modificó qué.

Lo que se prueba acá es que el log diga la verdad: que el autor sea quien mandó
el pedido y no el admin de turno, que un pedido que falla no deje rastro de algo
que no pasó, y que un borrado deje constancia aunque la entidad ya no exista.

Los endpoints instrumentados son los de trabajos.py y el login (Etapa A). El
resto de los routers se suma en la Etapa B con este mismo patrón.
"""
from datetime import date, timedelta
from decimal import Decimal

import models
from conftest import cabecera_de, crear_cliente, crear_papel, crear_trabajo, crear_usuario


def asientos(db, entidad=None):
    """Las filas del log, de la más vieja a la más nueva."""
    query = db.query(models.Auditoria)
    if entidad:
        query = query.filter(models.Auditoria.entidad == entidad)
    return query.order_by(models.Auditoria.fecha).all()


def ultimo(db, entidad=None):
    filas = asientos(db, entidad)
    assert filas, "no se asentó nada"
    return filas[-1]


# --- Las tres acciones ------------------------------------------------------

class TestQueSeAsienta:

    def test_un_alta_deja_su_fila(self, client, db):
        cliente = crear_cliente(db, nombre_completo="Juan Pérez")

        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id,
            "descripcion_producto": "Volantes A5",
            "cantidad": 1000,
            "fecha_creacion": str(date.today()),
            "precio_venta": "50000",
            "costo_total_materiales": "20000",
        })
        assert r.status_code == 200

        fila = ultimo(db, "Trabajo")
        assert fila.accion == models.ACCION_ALTA
        assert fila.entidad_id == r.json()["id"]
        assert "Volantes A5" in fila.resumen
        assert "Juan Pérez" in fila.resumen

    def test_una_edicion_guarda_el_antes_y_el_despues(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db), estado="Aprobado")

        r = client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})
        assert r.status_code == 200

        fila = ultimo(db, "Trabajo")
        assert fila.accion == models.ACCION_EDICION
        assert "cantidad: 1000 -> 1500" in fila.detalle

    def test_una_baja_deja_constancia_aunque_el_trabajo_ya_no_exista(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db, nombre_completo="Ana Gómez"))
        trabajo_id = trabajo.id

        assert client.delete(f"/api/trabajos/{trabajo_id}").status_code == 200
        assert db.query(models.Trabajo).count() == 0

        fila = ultimo(db, "Trabajo")
        assert fila.accion == models.ACCION_BAJA
        assert fila.entidad_id == trabajo_id
        assert "Ana Gómez" in fila.resumen

    def test_un_put_que_no_cambia_nada_no_ensucia_el_log(self, client, db):
        """El formulario de edición manda el trabajo entero aunque no se haya
        tocado un solo campo: sin esto, abrir y guardar dejaría una fila."""
        trabajo = crear_trabajo(db, crear_cliente(db), cantidad=1000)

        assert client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1000}).status_code == 200

        assert asientos(db, "Trabajo") == []

    def test_emitir_la_orden_queda_asentado_con_el_numero(self, client, db):
        papel = crear_papel(db, cantidad=Decimal("5000"))
        trabajo = crear_trabajo(db, crear_cliente(db), papel_id=papel.id,
                                cantidad_pliegos=Decimal("100"))

        assert client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden").status_code == 200

        fila = ultimo(db, "Trabajo")
        assert "OP-000001" in fila.detalle

    def test_reimprimir_no_asienta_de_nuevo(self, client, db):
        """La segunda impresión no toca la base: sólo regenera el mismo PDF."""
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        assert len(asientos(db, "Trabajo")) == 1

    def test_iniciar_diseno_deja_la_seña_cobrada(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db), estado="Aprobado")

        r = client.post(f"/api/trabajos/{trabajo.id}/iniciar-diseno",
                        json={"monto": "10000", "metodo": "Efectivo"})
        assert r.status_code == 200

        fila = ultimo(db, "Trabajo")
        assert "estado: Aprobado -> En Diseño" in fila.detalle
        assert "10000" in fila.detalle


# --- El autor es quien mandó el pedido --------------------------------------

class TestQuienLoHizo:

    def test_queda_el_usuario_del_token_y_no_el_admin(self, client, db):
        """Es la razón de ser de todo esto: el `client` viene logueado como
        admin, y si el asiento tomara ese usuario en vez del del header, el log
        diría siempre lo mismo y no serviría para nada."""
        trabajo = crear_trabajo(db, crear_cliente(db))
        encargado = crear_usuario(db, nombre="marcos", rol="encargado")

        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 2000},
                   headers=cabecera_de(encargado))

        fila = ultimo(db, "Trabajo")
        assert fila.usuario_nombre == "marcos"
        assert fila.usuario_id == encargado.id

    def test_el_nombre_sobrevive_a_la_baja_del_usuario(self, client, db):
        """usuario_nombre es el hecho histórico, no un puntero: un usuario dado
        de baja no puede dejar sin autor lo que hizo."""
        trabajo = crear_trabajo(db, crear_cliente(db))
        encargado = crear_usuario(db, nombre="marcos", rol="encargado")
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 2000},
                   headers=cabecera_de(encargado))

        encargado.activo = False
        db.commit()

        assert ultimo(db, "Trabajo").usuario_nombre == "marcos"


# --- El asiento viaja con la transacción ------------------------------------

class TestNoMiente:

    def test_un_404_no_deja_fila(self, client, db):
        assert client.put("/api/trabajos/no-existe", json={"cantidad": 5}).status_code == 404

        assert asientos(db, "Trabajo") == []

    def test_un_400_no_deja_fila(self, client, db):
        """Mandar a producción sin la orden impresa se rechaza: el trabajo no
        cambió, así que el log tampoco puede decir que cambió."""
        trabajo = crear_trabajo(db, crear_cliente(db), estado="Aprobado")

        r = client.put(f"/api/trabajos/{trabajo.id}", json={"estado": "En Producción"})
        assert r.status_code == 400

        assert asientos(db, "Trabajo") == []

    def test_un_borrado_rechazado_no_deja_fila(self, client, db):
        """Un trabajo con pagos no se puede borrar. El asiento se arma antes del
        delete, así que este es el caso donde podría quedar una fila fantasma."""
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        db.add(models.Movimiento(cliente_id=cliente.id, trabajo_id=trabajo.id,
                                 monto=Decimal("1000"), tipo="Pago", descripcion="Seña"))
        db.commit()

        assert client.delete(f"/api/trabajos/{trabajo.id}").status_code == 400

        assert asientos(db, "Trabajo") == []
        assert db.query(models.Trabajo).count() == 1

    def test_una_orden_sin_papel_suficiente_no_deja_fila(self, client, db):
        papel = crear_papel(db, cantidad=Decimal("10"))
        trabajo = crear_trabajo(db, crear_cliente(db), papel_id=papel.id,
                                cantidad_pliegos=Decimal("500"))

        assert client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden").status_code == 400

        assert asientos(db, "Trabajo") == []


# --- Ingresos al sistema ----------------------------------------------------

class TestIngresos:

    def test_un_ingreso_queda_asentado(self, client, db):
        crear_usuario(db, nombre="facundo", rol="admin", password="clave1234")

        r = client.post("/api/auth/login", json={"usuario": "facundo", "password": "clave1234"})
        assert r.status_code == 200

        fila = ultimo(db, "Sesión")
        assert fila.accion == models.ACCION_INGRESO
        assert fila.usuario_nombre == "facundo"

    def test_un_intento_fallido_queda_asentado_sin_autor(self, client, db):
        crear_usuario(db, nombre="facundo", rol="admin", password="clave1234")

        r = client.post("/api/auth/login", json={"usuario": "facundo", "password": "equivocada"})
        assert r.status_code == 401

        fila = ultimo(db, "Sesión")
        assert fila.accion == models.ACCION_INGRESO_FALLIDO
        assert fila.usuario_id is None
        assert "facundo" in fila.resumen

    def test_falla_tambien_con_un_usuario_inventado(self, client, db):
        r = client.post("/api/auth/login", json={"usuario": "nadie", "password": "loquesea"})
        assert r.status_code == 401

        assert ultimo(db, "Sesión").accion == models.ACCION_INGRESO_FALLIDO

    def test_la_contraseña_no_queda_en_ninguna_parte(self, client, db):
        """Lo más importante de todo el archivo: el log se lee desde una pantalla
        y una contraseña filtrada ahí queda a la vista de cualquiera que la tenga
        abierta. Vale para el intento fallido (donde suele ser un tipeo de la
        contraseña real) y para el ingreso exitoso."""
        crear_usuario(db, nombre="facundo", rol="admin", password="secreta-999")
        client.post("/api/auth/login", json={"usuario": "facundo", "password": "secreta-999"})
        client.post("/api/auth/login", json={"usuario": "facundo", "password": "secreta-998"})

        todo = " ".join(
            f"{f.usuario_nombre} {f.accion} {f.entidad} {f.resumen} {f.detalle or ''}"
            for f in asientos(db)
        )
        assert "secreta-99" not in todo


# --- La consulta ------------------------------------------------------------

class TestConsulta:

    def test_devuelve_lo_mas_nuevo_primero(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 2000})

        filas = client.get("/api/auditoria/").json()

        assert "1500 -> 2000" in filas[0]["detalle"]

    def test_filtra_por_entidad(self, client, db):
        crear_usuario(db, nombre="facundo", rol="admin", password="clave1234")
        client.post("/api/auth/login", json={"usuario": "facundo", "password": "clave1234"})
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})

        filas = client.get("/api/auditoria/?entidad=Sesión").json()

        assert [f["entidad"] for f in filas] == ["Sesión"]

    def test_filtra_por_usuario(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db))
        encargado = crear_usuario(db, nombre="marcos", rol="encargado")
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500},
                   headers=cabecera_de(encargado))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 2000})

        filas = client.get("/api/auditoria/?usuario=marcos").json()

        assert len(filas) == 1
        assert filas[0]["usuario_nombre"] == "marcos"

    def test_el_rango_de_fechas_incluye_el_dia_de_hoy_entero(self, client, db):
        """Filtrar por la fecha pelada compara contra las 00:00: sin resolverlo,
        buscar 'hasta hoy' perdía todo lo hecho hoy."""
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})
        hoy = date.today()

        assert len(client.get(f"/api/auditoria/?desde={hoy}&hasta={hoy}").json()) == 1

    def test_un_rango_viejo_no_devuelve_nada(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})
        anteayer = date.today() - timedelta(days=2)

        assert client.get(f"/api/auditoria/?hasta={anteayer}").json() == []

    def test_respeta_el_limite(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db))
        for cantidad in (1500, 2000, 2500):
            client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": cantidad})

        assert len(client.get("/api/auditoria/?limite=2").json()) == 2

    def test_no_deja_pedir_mas_del_techo(self, client, db):
        assert client.get("/api/auditoria/?limite=99999").status_code == 422


# --- El log no se toca ------------------------------------------------------

class TestSoloLectura:

    def test_no_hay_forma_de_escribirlo_ni_de_borrarlo(self, client, db):
        """Un registro de auditoría que se puede editar desde la misma pantalla
        que audita no registra nada. Estos endpoints no existen y no tienen que
        aparecer nunca."""
        trabajo = crear_trabajo(db, crear_cliente(db))
        client.put(f"/api/trabajos/{trabajo.id}", json={"cantidad": 1500})
        fila_id = ultimo(db, "Trabajo").id

        assert client.post("/api/auditoria/", json={}).status_code == 405
        assert client.put(f"/api/auditoria/{fila_id}", json={}).status_code == 405
        assert client.delete(f"/api/auditoria/{fila_id}").status_code == 405

        assert db.query(models.Auditoria).count() == 1
