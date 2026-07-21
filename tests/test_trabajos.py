"""Tests de routers/trabajos.py.

Cubren el Caso 8 (eliminar un trabajo con cheques asociados) y el Caso 6 (doble
clic en "Imprimir orden" descontando el stock dos veces).
"""
import threading
from decimal import Decimal

import pytest

import models
from conftest import crear_cheque, crear_cliente, crear_papel, crear_trabajo


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
