"""Tests de routers/trabajos.py.

Cubren el Caso 8 (eliminar un trabajo con cheques asociados) y el Caso 6 (doble
clic en "Imprimir orden" descontando el stock dos veces).
"""
import threading
from datetime import date
from decimal import Decimal

import pytest

import models
from calculos import calcular_saldo_cliente, ingresos_reales
from conftest import crear_cheque, crear_cliente, crear_papel, crear_trabajo


def crear_pago(db, cliente, trabajo=None, monto=Decimal("500"), **overrides):
    """Registra un Movimiento de tipo 'Pago' (una seña o un pago a cuenta)."""
    datos = dict(
        cliente_id=cliente.id,
        trabajo_id=trabajo.id if trabajo else None,
        monto=Decimal(str(monto)),
        tipo="Pago",
        metodo="Efectivo",
        descripcion="Seña de test",
    )
    datos.update(overrides)
    pago = models.Movimiento(**datos)
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


def _estado_cliente(db, cliente):
    """(saldo_cliente, ingresos_históricos) para chequear el invariante."""
    trabajos = db.query(models.Trabajo).filter(models.Trabajo.cliente_id == cliente.id).all()
    movimientos = db.query(models.Movimiento).filter(models.Movimiento.cliente_id == cliente.id).all()
    cheques = db.query(models.Cheque).filter(models.Cheque.cliente_id == cliente.id).all()
    _, _, saldo = calcular_saldo_cliente(trabajos, movimientos, cheques)
    ingresos = ingresos_reales(movimientos, cheques, lambda f: True)
    return saldo, ingresos


# --- Caso 8: eliminar un trabajo con cheques --------------------------------

class TestEliminarTrabajo:
    """eliminar_trabajo bloquea trabajos con movimientos, presupuestos y gastos,
    pero los cheques también apuntan al trabajo por FK y no estaban en la lista.
    """

    def test_bloquea_si_el_trabajo_tiene_un_cheque_imputado(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        crear_cheque(db, cliente, trabajo)

        r = client.delete(f"/api/trabajos/{trabajo.id}")

        # Lo importante es que NO sea un 500: el operador tiene que entender
        # por qué no se puede borrar, igual que con pagos o gastos.
        assert r.status_code == 400, f"Se esperaba un 400 explicado, llegó {r.status_code}"
        assert "cheque" in r.json()["detail"].lower()

    def test_el_trabajo_sigue_existiendo_tras_el_rechazo(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        crear_cheque(db, cliente, trabajo)

        client.delete(f"/api/trabajos/{trabajo.id}")

        assert db.query(models.Trabajo).filter(models.Trabajo.id == trabajo.id).first()

    def test_un_cheque_de_otro_trabajo_no_bloquea(self, client, db):
        # El filtro tiene que ser por trabajo_id, no "existe algún cheque".
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        otro = crear_trabajo(db, cliente, descripcion_producto="Otro")
        crear_cheque(db, cliente, otro)

        assert client.delete(f"/api/trabajos/{trabajo.id}").status_code == 200

    def test_un_cheque_sin_trabajo_no_bloquea(self, client, db):
        # Un pago a cuenta con cheque no está atado a ningún trabajo.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        crear_cheque(db, cliente, trabajo=None)

        assert client.delete(f"/api/trabajos/{trabajo.id}").status_code == 200

    def test_borra_un_trabajo_sin_dependencias(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        assert client.delete(f"/api/trabajos/{trabajo.id}").status_code == 200
        assert db.query(models.Trabajo).filter(models.Trabajo.id == trabajo.id).first() is None

    def test_sigue_bloqueando_por_pagos(self, client, db):
        # Guarda de no-regresión: agregar el chequeo de cheques no debe romper
        # los tres motivos que ya se validaban.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        db.add(models.Movimiento(
            cliente_id=cliente.id, trabajo_id=trabajo.id,
            monto=Decimal("100"), tipo="Pago", metodo="Efectivo", descripcion="Seña",
        ))
        db.commit()

        r = client.delete(f"/api/trabajos/{trabajo.id}")
        assert r.status_code == 400
        assert "pagos" in r.json()["detail"].lower()


# --- Papel y pliegos van juntos ---------------------------------------------

class TestPapelDelTrabajo:
    """Elegir papel sin decir cuántos pliegos dejaba el trabajo en un estado que
    no descuenta nada: _descontar_papel saltea el caso y el stock queda
    desfasado sin dar error. Es el mismo síntoma silencioso del presupuesto
    convertido, por eso la regla es la misma en los dos lados.
    """

    def test_rechaza_papel_sin_pliegos_al_crear(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id, "fecha_creacion": str(date.today()),
            "precio_venta": 1000, "papel_id": papel.id,
        })
        assert r.status_code == 400
        assert "pliegos" in r.json()["detail"].lower()

    def test_rechaza_pliegos_sin_papel_al_crear(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id, "fecha_creacion": str(date.today()),
            "precio_venta": 1000, "cantidad_pliegos": 100,
        })
        assert r.status_code == 400
        assert "papel" in r.json()["detail"].lower()

    def test_acepta_un_trabajo_sin_papel(self, client, db):
        # El papel lo trae el cliente o se compra en el momento: los dos campos
        # en null es un estado válido y frecuente.
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id, "fecha_creacion": str(date.today()),
            "precio_venta": 1000,
        })
        assert r.status_code == 200

    def test_acepta_papel_con_pliegos(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id, "fecha_creacion": str(date.today()),
            "precio_venta": 1000, "papel_id": papel.id, "cantidad_pliegos": 100,
        })
        assert r.status_code == 200

    def test_rechaza_papel_sin_pliegos_al_editar(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.put(f"/api/trabajos/{trabajo.id}", json={"papel_id": papel.id})

        assert r.status_code == 400

    def test_se_puede_sacar_el_papel_de_un_trabajo(self, client, db):
        # Limpiar los dos campos a la vez tiene que seguir funcionando: es como
        # se corrige un trabajo al que se le asignó el papel equivocado.
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id,
                               cantidad_pliegos=Decimal("100"))

        r = client.put(f"/api/trabajos/{trabajo.id}",
                       json={"papel_id": None, "cantidad_pliegos": None})

        assert r.status_code == 200
        db.refresh(trabajo)
        assert trabajo.papel_id is None

    def test_un_cambio_que_no_toca_el_papel_no_lo_valida(self, client, db):
        # No-regresión: editar la fecha de entrega de un trabajo sin papel no
        # debe disparar la validación.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.put(f"/api/trabajos/{trabajo.id}", json={"descripcion_producto": "Otra cosa"})

        assert r.status_code == 200


# --- Caso 6: doble clic en imprimir orden -----------------------------------

class TestImprimirOrden:

    def test_reimprimir_no_vuelve_a_descontar(self, client, db):
        # Idempotencia secuencial: es lo que ya garantizaba orden_impresa.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")
        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        db.refresh(papel)
        assert papel.cantidad == Decimal("400.000")

    def test_conserva_el_numero_de_orden_al_reimprimir(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")
        db.refresh(trabajo)
        primero = trabajo.numero_orden

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")
        db.refresh(trabajo)
        assert trabajo.numero_orden == primero

    def test_deja_un_solo_registro_en_el_historial(self, client, db):
        # El historial de stock es la auditoría: dos descuentos dejan dos filas.
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")
        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        filas = db.query(models.HistorialStock).filter(
            models.HistorialStock.articulo_id == papel.id
        ).all()
        assert len(filas) == 1

    def test_si_no_alcanza_el_papel_la_orden_no_queda_marcada(self, client, db):
        """El reclamo de la impresión se escribe ANTES de descontar el papel.

        Si el descuento corta por falta de stock, ese reclamo tiene que irse con
        la transacción: si quedara, el trabajo tendría número de orden y
        orden_impresa=True sin haber descontado nada, y reintentar ya no
        descontaría nunca.
        """
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("10"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        r = client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")
        assert r.status_code == 400

        db.expire_all()
        t = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo.id).first()
        assert not t.orden_impresa
        assert t.numero_orden is None

    def test_tras_reponer_el_papel_la_orden_sale_y_descuenta(self, client, db):
        # Cierra el ciclo del test anterior: el reintento tiene que funcionar.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("10"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        papel.cantidad = Decimal("500")
        db.commit()

        assert client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden").status_code == 200
        db.expire_all()
        assert db.query(models.ArticuloStock).filter(
            models.ArticuloStock.id == papel.id
        ).first().cantidad == Decimal("400.000")

    def test_forzar_emite_la_orden_aunque_falte_papel(self, client, db):
        # El camino de "se compra en el momento": deja el stock en negativo y
        # lo asienta en el historial.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("10"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        r = client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden?forzar=true")

        assert r.status_code == 200
        db.expire_all()
        assert db.query(models.ArticuloStock).filter(
            models.ArticuloStock.id == papel.id
        ).first().cantidad == Decimal("-90.000")
        historial = db.query(models.HistorialStock).first()
        assert "forzado" in historial.motivo

    def test_doble_clic_simultaneo_descuenta_una_sola_vez(self, client, db, monkeypatch):
        """El doble clic real: dos requests que pasan juntos por el guard.

        orden_impresa se lee y se escribe en pasos separados, así que dos
        requests concurrentes pueden leer ambos False y descontar dos veces.
        La barrera fuerza ese cruce en lugar de esperar que el scheduler lo
        haga: sin ella el test pasaría de casualidad casi siempre.

        Se sincroniza en _generar_numero_orden porque es el primer paso después
        del guard, tanto antes como después del arreglo.
        """
        from routers import trabajos as router_trabajos

        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        original = router_trabajos._generar_numero_orden
        barrera = threading.Barrier(2, timeout=5)

        def generar_sincronizado(sesion):
            numero = original(sesion)
            try:
                barrera.wait()
            except threading.BrokenBarrierError:
                # El otro request ya no llegó hasta acá: quedó frenado antes,
                # que es justamente lo que hace un guard atómico.
                pass
            return numero

        monkeypatch.setattr(router_trabajos, "_generar_numero_orden", generar_sincronizado)

        respuestas = []
        def imprimir():
            respuestas.append(client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden").status_code)

        hilos = [threading.Thread(target=imprimir) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=15)

        db.expire_all()

        # Se afirma sobre el HISTORIAL y no sobre la cantidad: con la carrera
        # abierta las dos sesiones leen el mismo stock y escriben el mismo
        # resultado, así que la cantidad final queda bien de casualidad (una
        # pisa a la otra) mientras el historial registra dos descuentos. Es la
        # peor combinación posible: el papel dice una cosa y la auditoría otra.
        movimientos_papel = db.query(models.HistorialStock).filter(
            models.HistorialStock.articulo_id == papel.id
        ).all()
        assert len(movimientos_papel) == 1, (
            f"Se registraron {len(movimientos_papel)} descuentos para una sola orden: "
            f"{[(str(m.diferencia), m.motivo) for m in movimientos_papel]}. Respuestas: {respuestas}"
        )

        papel_final = db.query(models.ArticuloStock).filter(
            models.ArticuloStock.id == papel.id
        ).first()
        assert papel_final.cantidad == Decimal("400.000")
        assert respuestas.count(200) >= 1, f"Ninguna impresión salió bien: {respuestas}"


# --- Aplicar saldo a favor a un trabajo -------------------------------------

def _saldo_trabajo(db, trabajo):
    """Saldo pendiente de un trabajo directo desde la base (precio - pagos)."""
    pagos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.trabajo_id == trabajo.id, models.Movimiento.tipo == "Pago")
        .all()
    )
    return Decimal(str(trabajo.precio_venta)) - sum((Decimal(str(p.monto)) for p in pagos), Decimal("0"))


class TestAplicarSaldoFavor:
    """El saldo a favor de un cliente (seña de un trabajo cancelado, pago a
    cuenta) se aplica a un trabajo re-imputando los pagos existentes, sin crear
    plata: el saldo neto del cliente y los ingresos no cambian.
    """

    def test_credito_de_cancelado_cubre_exacto(self, client, db):
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("500"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        saldo_antes, ingresos_antes = _estado_cliente(db, cliente)
        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("500.00")
        assert Decimal(r.json()["saldo_pendiente_restante"]) == Decimal("0.00")

        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("0")
        saldo_despues, ingresos_despues = _estado_cliente(db, cliente)
        assert saldo_despues == saldo_antes  # invariante: no se crea plata
        assert ingresos_despues == ingresos_antes

    def test_credito_menor_que_el_precio_deja_saldo(self, client, db):
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("300"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("300"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("300.00")
        assert Decimal(r.json()["saldo_pendiente_restante"]) == Decimal("200.00")

        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("200")

    def test_credito_mayor_parte_el_pago(self, client, db):
        # La seña de 800 de un trabajo cancelado cubre los 500 del nuevo y deja
        # 300 de saldo a favor: el movimiento se parte en 500 (al nuevo) + 300.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("800"))
        pago = crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("800"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        saldo_antes, ingresos_antes = _estado_cliente(db, cliente)
        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("500.00")

        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("0")
        # El movimiento original quedó reducido a los 300 restantes.
        db.refresh(pago)
        assert Decimal(str(pago.monto)) == Decimal("300.00")
        assert pago.trabajo_id == cancelado.id
        # Se creó exactamente un movimiento nuevo, imputado al trabajo nuevo.
        del_nuevo = (
            db.query(models.Movimiento)
            .filter(models.Movimiento.trabajo_id == nuevo.id, models.Movimiento.tipo == "Pago")
            .all()
        )
        assert len(del_nuevo) == 1
        assert Decimal(str(del_nuevo[0].monto)) == Decimal("500.00")

        saldo_despues, ingresos_despues = _estado_cliente(db, cliente)
        assert saldo_despues == saldo_antes == Decimal("-300.00")  # sigue habiendo 300 a favor
        assert ingresos_despues == ingresos_antes

    def test_credito_de_pago_sin_imputar(self, client, db):
        cliente = crear_cliente(db)
        crear_pago(db, cliente, trabajo=None, monto=Decimal("400"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("400.00")

        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("100")

    def test_sin_credito_disponible_devuelve_400(self, client, db):
        cliente = crear_cliente(db)
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 400
        assert "saldo a favor" in r.json()["detail"].lower()

    def test_no_toca_credito_de_un_trabajo_vivo(self, client, db):
        # Un pago imputado a otro trabajo NO cancelado no es crédito movible.
        cliente = crear_cliente(db)
        otro_vivo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=otro_vivo, monto=Decimal("500"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 400
        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("500")  # intacto

    def test_trabajo_ya_pago_devuelve_400(self, client, db):
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("500"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=nuevo, monto=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        assert r.status_code == 400
        assert "pago" in r.json()["detail"].lower()

    def test_no_se_aplica_a_un_trabajo_cancelado(self, client, db):
        cliente = crear_cliente(db)
        crear_pago(db, cliente, trabajo=None, monto=Decimal("500"))
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{cancelado.id}/aplicar-saldo-favor")
        assert r.status_code == 400
        assert "cancelado" in r.json()["detail"].lower()


# --- Aplicar saldo a favor: casos extremos ----------------------------------

def _suma_pagos(db, cliente):
    """Total de la caja del cliente: suma de todos sus Movimiento 'Pago'.

    El invariante más fuerte del flujo: aplicar saldo a favor mueve plata entre
    trabajos, nunca la crea ni la destruye. Este total tiene que quedar igual.
    """
    pagos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.cliente_id == cliente.id, models.Movimiento.tipo == "Pago")
        .all()
    )
    return sum((Decimal(str(p.monto)) for p in pagos), Decimal("0"))


class TestAplicarSaldoFavorExtremos:
    """Casos límite: el sistema tiene que atajar cada uno (normalmente con un 400)
    sin descuadrar la caja. La regla de oro es que la suma de pagos del cliente
    nunca cambia: aplicar saldo a favor re-imputa plata existente, no la inventa.
    """

    def test_trabajo_ya_pagado_deuda_cero(self, client, db):
        # Reintentar sobre un trabajo con deuda 0 no debe re-aplicar nada.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("500"))
        pagado = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=pagado, monto=Decimal("500"))

        caja_antes = _suma_pagos(db, cliente)
        r = client.post(f"/api/trabajos/{pagado.id}/aplicar-saldo-favor")

        assert r.status_code == 400
        assert "pago" in r.json()["detail"].lower()
        db.expire_all()
        assert _suma_pagos(db, cliente) == caja_antes

    def test_cliente_deudor_no_tiene_saldo_para_aplicar(self, client, db):
        # El cliente DEBE plata (pagó sólo parte de un trabajo vivo). Ese pago
        # parcial no es crédito movible: está cubriendo trabajo activo.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        crear_pago(db, cliente, trabajo=trabajo, monto=Decimal("100"))

        caja_antes = _suma_pagos(db, cliente)
        r = client.post(f"/api/trabajos/{trabajo.id}/aplicar-saldo-favor")

        assert r.status_code == 400
        assert "saldo a favor" in r.json()["detail"].lower()
        db.expire_all()
        assert _saldo_trabajo(db, trabajo) == Decimal("400")  # sigue debiendo 400
        assert _suma_pagos(db, cliente) == caja_antes

    def test_trabajo_cancelado_rechaza_antes_de_tocar_nada(self, client, db):
        cliente = crear_cliente(db)
        crear_pago(db, cliente, trabajo=None, monto=Decimal("500"))
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))

        caja_antes = _suma_pagos(db, cliente)
        r = client.post(f"/api/trabajos/{cancelado.id}/aplicar-saldo-favor")

        assert r.status_code == 400
        assert "cancelado" in r.json()["detail"].lower()
        db.expire_all()
        assert _suma_pagos(db, cliente) == caja_antes

    def test_cheque_mas_grande_que_la_deuda_no_se_parte(self, client, db):
        # El único crédito es un cheque físico de 800; la deuda es 500. Un cheque
        # no se puede partir, así que no se aplica nada y no se descuadra la caja.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("800"))
        cheque = crear_cheque(db, cliente, trabajo=cancelado, monto=Decimal("800"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")

        assert r.status_code == 400
        assert "cheque" in r.json()["detail"].lower()
        db.expire_all()
        db.refresh(cheque)
        assert cheque.trabajo_id == cancelado.id  # el cheque no se movió
        assert _saldo_trabajo(db, nuevo) == Decimal("500")  # sigue debiendo todo

    def test_cheque_entero_que_entra_se_reimputa(self, client, db):
        # Un cheque que sí entra dentro de la deuda se re-imputa completo.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("500"))
        cheque = crear_cheque(db, cliente, trabajo=cancelado, monto=Decimal("500"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")

        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("500.00")
        db.expire_all()
        db.refresh(cheque)
        assert cheque.trabajo_id == nuevo.id

    def test_credito_partido_entre_dos_pagos_cubre_exacto(self, client, db):
        # Dos señas de trabajos cancelados (300 y 400) cubren una deuda de 500:
        # la primera entera, la segunda partida. La caja no se mueve.
        cliente = crear_cliente(db)
        canc1 = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("300"))
        canc2 = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("400"))
        crear_pago(db, cliente, trabajo=canc1, monto=Decimal("300"))
        crear_pago(db, cliente, trabajo=canc2, monto=Decimal("400"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        caja_antes = _suma_pagos(db, cliente)
        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")

        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("500.00")
        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("0")
        assert _suma_pagos(db, cliente) == caja_antes  # 700, intacta

    def test_pago_indivisible_en_cheque_no_bloquea_lo_que_si_entra(self, client, db):
        # Hay un mov chico (200) y un cheque grande (800). Se aplica lo del mov y
        # el cheque se deja quieto: aplicación parcial segura, sin error.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("1000"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("200"))
        cheque = crear_cheque(db, cliente, trabajo=cancelado, monto=Decimal("800"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")

        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monto_aplicado"]) == Decimal("200.00")
        db.expire_all()
        db.refresh(cheque)
        assert cheque.trabajo_id == cancelado.id  # el cheque no se tocó
        assert _saldo_trabajo(db, nuevo) == Decimal("300")

    def test_no_consume_saldo_a_favor_de_otro_cliente(self, client, db):
        # Robo de identidad: el trabajo del Cliente A no puede tocar el crédito
        # del Cliente B. El filtro es por cliente_id.
        cliente_a = crear_cliente(db, dni_cuit="11111111")
        cliente_b = crear_cliente(db, dni_cuit="22222222")
        canc_b = crear_trabajo(db, cliente_b, estado="Cancelado", precio_venta=Decimal("500"))
        pago_b = crear_pago(db, cliente_b, trabajo=canc_b, monto=Decimal("500"))
        trabajo_a = crear_trabajo(db, cliente_a, precio_venta=Decimal("500"))

        r = client.post(f"/api/trabajos/{trabajo_a.id}/aplicar-saldo-favor")

        assert r.status_code == 400  # A no tiene crédito propio
        db.expire_all()
        db.refresh(pago_b)
        assert pago_b.trabajo_id == canc_b.id  # el pago de B no se movió
        assert Decimal(str(pago_b.monto)) == Decimal("500.00")
        assert _saldo_trabajo(db, trabajo_a) == Decimal("500")

    def test_doble_submit_secuencial_no_duplica(self, client, db):
        # Dos POST seguidos (doble clic): el segundo tiene que rebotar porque el
        # trabajo ya quedó pago. La caja no se descuadra.
        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("800"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("800"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        caja_antes = _suma_pagos(db, cliente)

        r1 = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")
        r2 = client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor")

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 400  # ya está pago
        db.expire_all()
        assert _saldo_trabajo(db, nuevo) == Decimal("0")
        assert _suma_pagos(db, cliente) == caja_antes  # 800, sin duplicar

    def test_doble_submit_concurrente_no_descuadra_la_caja(self, client, db, monkeypatch):
        """El doble clic real: dos requests que cruzan la lectura del saldo juntos.

        El saldo pendiente se lee y la plata se mueve en pasos separados. Sin un
        candado, dos requests concurrentes leen ambos el mismo crédito y lo
        aplican dos veces: la caja termina con más plata imputada que la que
        existe. La barrera fuerza ese cruce sincronizando en calcular_saldo_trabajo
        (la lectura del saldo pendiente), en vez de confiar en el scheduler.
        """
        from routers import trabajos as router_trabajos

        cliente = crear_cliente(db)
        cancelado = crear_trabajo(db, cliente, estado="Cancelado", precio_venta=Decimal("800"))
        crear_pago(db, cliente, trabajo=cancelado, monto=Decimal("800"))
        nuevo = crear_trabajo(db, cliente, precio_venta=Decimal("500"))
        caja_antes = _suma_pagos(db, cliente)

        original = router_trabajos.calcular_saldo_trabajo
        barrera = threading.Barrier(2, timeout=5)

        def saldo_sincronizado(*args, **kwargs):
            resultado = original(*args, **kwargs)
            try:
                barrera.wait()
            except threading.BrokenBarrierError:
                # El otro request quedó frenado antes: es justo lo que hace un
                # candado que gana uno solo.
                pass
            return resultado

        monkeypatch.setattr(router_trabajos, "calcular_saldo_trabajo", saldo_sincronizado)

        respuestas = []

        def aplicar():
            respuestas.append(
                client.post(f"/api/trabajos/{nuevo.id}/aplicar-saldo-favor").status_code
            )

        hilos = [threading.Thread(target=aplicar) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=15)

        db.expire_all()
        # Lo crítico: la caja no se descuadra. La suma de pagos sigue en 800
        # aunque dos requests hayan corrido a la vez.
        assert _suma_pagos(db, cliente) == caja_antes, (
            f"La caja se descuadró: antes {caja_antes}, después {_suma_pagos(db, cliente)}. "
            f"Respuestas: {respuestas}"
        )
        # Y el saldo se aplicó una sola vez: exactamente una respuesta 200.
        assert respuestas.count(200) == 1, f"Se esperaba una sola aplicación exitosa: {respuestas}"
        assert _saldo_trabajo(db, nuevo) == Decimal("0")
