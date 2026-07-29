"""El registro de quién modificó qué.

Lo que se prueba acá es que el log diga la verdad: que el autor sea quien mandó
el pedido y no el admin de turno, que un pedido que falla no deje rastro de algo
que no pasó, y que un borrado deje constancia aunque la entidad ya no exista.

Están instrumentados los 35 endpoints que modifican la base, de los doce
routers, más el login.
"""
from datetime import date, time, timedelta
from decimal import Decimal

import models
from conftest import (
    cabecera_de,
    crear_cheque,
    crear_cliente,
    crear_empleado,
    crear_papel,
    crear_presupuesto,
    crear_trabajo,
    crear_usuario,
)


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


# --- Los demás módulos ------------------------------------------------------

class TestClientes:

    def test_alta_edicion_y_baja(self, client, db):
        r = client.post("/api/clientes/", json={
            "nombre_completo": "Ana Gómez", "dni_cuit": "20111111112", "telefono": "1122334455",
        })
        cliente_id = r.json()["id"]
        client.put(f"/api/clientes/{cliente_id}", json={"telefono": "1199887766"})
        client.delete(f"/api/clientes/{cliente_id}")

        acciones = [f.accion for f in asientos(db, "Cliente")]
        assert acciones == [models.ACCION_ALTA, models.ACCION_EDICION, models.ACCION_BAJA]
        assert "1122334455 -> 1199887766" in asientos(db, "Cliente")[1].detalle
        assert "Ana Gómez" in asientos(db, "Cliente")[2].resumen


class TestGastos:

    def test_el_monto_queda_en_el_resumen(self, client, db):
        """Un gasto borrado cambia la ganancia del mes: el monto tiene que estar
        en el asiento o no hay forma de explicar la diferencia."""
        r = client.post("/api/gastos/", json={
            "categoria": "Insumos", "concepto": "Tinta negra",
            "monto": 45000, "fecha": str(date.today()),
        })
        client.delete(f"/api/gastos/{r.json()['id']}")

        baja = ultimo(db, "Gasto")
        assert baja.accion == models.ACCION_BAJA
        assert "Tinta negra" in baja.resumen
        assert "45000" in baja.resumen


class TestNotas:

    def test_alta_edicion_y_baja(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/notas/", json={"cliente_id": cliente.id, "texto": "Llamar antes"})
        nota_id = r.json()["id"]
        client.put(f"/api/notas/{nota_id}", json={"texto": "Llamar después de las 18"})
        client.delete(f"/api/notas/{nota_id}")

        filas = asientos(db, "Nota")
        assert [f.accion for f in filas] == [
            models.ACCION_ALTA, models.ACCION_EDICION, models.ACCION_BAJA
        ]
        assert "Llamar antes -> Llamar después de las 18" in filas[1].detalle


class TestEmpleados:

    def test_dar_de_baja_queda_como_edicion(self, client, db):
        """Un empleado no se borra: se le pone activo=False. Sin asiento, dejaría
        de aparecer en la planilla sin que nadie sepa quién lo sacó."""
        empleado = crear_empleado(db, nombre="Eduardo")

        client.put(f"/api/empleados/{empleado.id}", json={"activo": False})

        fila = ultimo(db, "Empleado")
        assert fila.accion == models.ACCION_EDICION
        assert fila.resumen == "Eduardo"
        assert "activo: True -> False" in fila.detalle


class TestMovimientos:

    def test_borrar_un_pago_deja_el_monto_asentado(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/movimientos/", json={
            "cliente_id": cliente.id, "monto": 25000,
            "tipo": "Pago", "metodo": "Efectivo", "descripcion": "Seña",
        })
        client.delete(f"/api/movimientos/{r.json()['id']}")

        baja = ultimo(db, "Movimiento")
        assert baja.accion == models.ACCION_BAJA
        assert "25000" in baja.resumen


class TestStock:

    def test_un_ajuste_de_cantidad_dice_quien_lo_hizo(self, client, db):
        """Es lo que HistorialStock no puede contestar: registra el movimiento y
        el motivo, pero no la persona."""
        papel = crear_papel(db, cantidad=Decimal("500"))
        marcos = crear_usuario(db, nombre="marcos", rol="encargado")

        client.patch(f"/api/stock/{papel.id}",
                     json={"cantidad": 320, "motivo": "Recuento"},
                     headers=cabecera_de(marcos))

        fila = ultimo(db, "Stock")
        assert fila.usuario_nombre == "marcos"
        # El valor nuevo se lee de la sesión, antes de que el tipo Cantidad le
        # ponga los tres decimales al guardar: en el log queda '320' y no
        # '320.000'. Es cosmético y no vale ensuciar el router por eso.
        assert "cantidad: 500.000 -> 320" in fila.detalle
        # El historial de dominio sigue funcionando igual que antes: el asiento
        # de auditoría se suma, no lo reemplaza.
        assert db.query(models.HistorialStock).count() == 1

    def test_editar_sin_cambiar_nada_no_asienta(self, client, db):
        """El PATCH pisa ultima_actualizacion en cada llamada: si contara como
        cambio, abrir y guardar dejaría una fila que no dice nada."""
        papel = crear_papel(db)

        client.patch(f"/api/stock/{papel.id}", json={})

        assert asientos(db, "Stock") == []

    def test_una_compra_de_varios_items_deja_una_fila_por_item(self, client, db):
        r = client.post("/api/stock/compras", json=[
            {"nombre": "Obra 90g", "unidad": "Pliegos", "cantidad": 100, "costo_total": 10000},
            {"nombre": "Ilustración 150g", "unidad": "Pliegos", "cantidad": 200, "costo_total": 30000},
        ])
        assert r.status_code == 201

        assert len(asientos(db, "Stock")) == 2


class TestAsistencia:

    def test_una_fila_por_planilla_y_no_una_por_empleado(self, client, db):
        """El encargado guarda el día entero varias veces por jornada. Una fila
        por empleado convertiría el log en una lista de la que no se saca nada."""
        juan = crear_empleado(db, nombre="Juan")
        pedro = crear_empleado(db, nombre="Pedro")

        r = client.post("/api/asistencia/planilla", json={
            "fecha": str(date.today()),
            "filas": [
                {"empleado_id": juan.id, "hora_entrada": "08:00:00", "hora_salida": "17:00:00"},
                {"empleado_id": pedro.id, "observaciones": "franco"},
            ],
        })
        assert r.status_code == 200

        filas = asientos(db, "Asistencia")
        assert len(filas) == 1
        assert "Juan: 08:00:00 a 17:00:00" in filas[0].detalle
        assert "Pedro: franco" in filas[0].detalle


class TestPresupuestos:

    def test_convertir_nombra_los_trabajos_que_salieron(self, client, db):
        presupuesto = crear_presupuesto(db, crear_cliente(db), items=[
            {"descripcion": "Volantes A5", "cantidad": 1000, "precio_unitario": Decimal("30")},
            {"descripcion": "Tarjetas", "cantidad": 500, "precio_unitario": Decimal("40")},
        ])

        r = client.post(f"/api/presupuestos/{presupuesto.id}/convertir")
        assert r.status_code == 200

        fila = ultimo(db, "Presupuesto")
        assert "1000x Volantes A5" in fila.detalle
        assert "500x Tarjetas" in fila.detalle

    def test_reemplazar_los_items_queda_asentado(self, client, db):
        """Los ítems son una relación, no columnas: sin tratarlos aparte, la
        edición más típica de un presupuesto no dejaría rastro."""
        presupuesto = crear_presupuesto(db, crear_cliente(db))

        r = client.put(f"/api/presupuestos/{presupuesto.id}", json={
            "items": [{"descripcion": "Otra cosa", "cantidad": 200, "precio_unitario": 50}],
        })
        assert r.status_code == 200

        assert "ítems reemplazados (1)" in ultimo(db, "Presupuesto").detalle


class TestCheques:

    def test_un_cambio_de_estado_dice_quien_y_con_que_motivo(self, client, db):
        cheque = crear_cheque(db, crear_cliente(db), estado="Cobrado")

        r = client.patch(f"/api/cheques/{cheque.id}",
                         json={"estado": "Rechazado", "motivo": "lo devolvió el banco"})
        assert r.status_code == 200

        fila = ultimo(db, "Cheque")
        assert "Estado Cobrado -> Rechazado" in fila.detalle
        assert "lo devolvió el banco" in fila.detalle
        assert "Galicia" in fila.resumen

    def test_borrar_un_cheque_deja_rastro_aunque_su_historial_se_vaya(self, client, db):
        """El HistorialCheque se borra con el cheque (sin padre queda huérfano).
        El asiento de auditoría es lo único que sobrevive."""
        cheque = crear_cheque(db, crear_cliente(db))

        assert client.delete(f"/api/cheques/{cheque.id}").status_code == 200
        assert db.query(models.HistorialCheque).count() == 0

        baja = ultimo(db, "Cheque")
        assert baja.accion == models.ACCION_BAJA
        assert baja.entidad_id == cheque.id


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
