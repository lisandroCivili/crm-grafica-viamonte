"""Tests de routers/entregas.py.

POST /api/entregas crea un remito (una o varias filas, cada una de un trabajo
del mismo cliente) y lo emite en PDF; GET /api/entregas/{id}/pdf reimprime uno
ya emitido sin efectos. A diferencia de imprimir-orden, acá no hay guard de
"primera vez": cada llamada es un remito real y puede haber varios.
"""
import threading

import models
from conftest import agregar_item_entrega, crear_cliente, crear_entrega, crear_trabajo


class TestRegistrarEntrega:

    def test_numeracion_correlativa_entre_remitos(self, client, db):
        cliente = crear_cliente(db)
        t1 = crear_trabajo(db, cliente, cantidad=100)
        t2 = crear_trabajo(db, cliente, cantidad=100)

        r1 = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": t1.id, "cantidad": 50}]})
        r2 = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": t2.id, "cantidad": 50}]})

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        entregas = db.query(models.Entrega).order_by(models.Entrega.numero_remito).all()
        assert [e.numero_remito for e in entregas] == ["RE-000001", "RE-000002"]

    def test_devuelve_el_pdf_del_remito(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)

        r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo.id, "cantidad": 50}]})

        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"

    def test_404_si_el_cliente_no_existe(self, client, db):
        trabajo = crear_trabajo(db, crear_cliente(db), cantidad=100)

        r = client.post("/api/entregas", json={"cliente_id": "no-existe", "items": [{"trabajo_id": trabajo.id, "cantidad": 10}]})

        assert r.status_code == 404

    def test_404_si_un_trabajo_no_existe(self, client, db):
        cliente = crear_cliente(db)

        r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": "no-existe", "cantidad": 10}]})

        assert r.status_code == 404

    def test_400_si_el_trabajo_no_es_de_ese_cliente(self, client, db):
        cliente = crear_cliente(db)
        otro_cliente = crear_cliente(db, nombre_completo="Otro Cliente", dni_cuit="20111222333")
        trabajo_de_otro = crear_trabajo(db, otro_cliente, cantidad=100)

        r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo_de_otro.id, "cantidad": 10}]})

        assert r.status_code == 400

    def test_422_sin_items(self, client, db):
        cliente = crear_cliente(db)

        r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": []})

        assert r.status_code == 422

    def test_422_con_el_mismo_trabajo_repetido(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)

        r = client.post("/api/entregas", json={
            "cliente_id": cliente.id,
            "items": [{"trabajo_id": trabajo.id, "cantidad": 10}, {"trabajo_id": trabajo.id, "cantidad": 20}],
        })

        assert r.status_code == 422

    def test_rechaza_si_excede_el_saldo_sin_forzar(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)
        crear_entrega(db, trabajo, cantidad=80, numero_remito="RE-000001")

        r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo.id, "cantidad": 30}]})

        assert r.status_code == 400
        assert db.query(models.ItemEntrega).filter(models.ItemEntrega.trabajo_id == trabajo.id).count() == 1

    def test_forzar_permite_exceder_el_saldo(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)
        crear_entrega(db, trabajo, cantidad=80, numero_remito="RE-000001")

        r = client.post("/api/entregas?forzar=true", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo.id, "cantidad": 30}]})

        assert r.status_code == 200, r.text
        total = sum(i.cantidad for i in db.query(models.ItemEntrega).filter(models.ItemEntrega.trabajo_id == trabajo.id).all())
        assert total == 110

    def test_cantidad_entregada_del_trabajo_suma_las_entregas(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)

        client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo.id, "cantidad": 20}]})
        client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo.id, "cantidad": 30}]})

        r = client.get("/api/trabajos/")
        cuerpo = next(t for t in r.json() if t["id"] == trabajo.id)
        assert cuerpo["cantidad_entregada"] == 50
        assert len(cuerpo["entregas"]) == 2

    def test_remito_combinado_crea_un_solo_encabezado_con_varias_filas(self, client, db):
        """El caso que motivó el rediseño: el cliente retira parte de dos
        trabajos distintos en la misma visita, y se emite un solo remito."""
        cliente = crear_cliente(db)
        t1 = crear_trabajo(db, cliente, cantidad=50, descripcion_producto="Cajas")
        t2 = crear_trabajo(db, cliente, cantidad=30, descripcion_producto="Volantes")

        r = client.post("/api/entregas", json={
            "cliente_id": cliente.id,
            "items": [
                {"trabajo_id": t1.id, "cantidad": 20},
                {"trabajo_id": t2.id, "cantidad": 15},
            ],
        })

        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"

        entregas = db.query(models.Entrega).all()
        assert len(entregas) == 1
        items = db.query(models.ItemEntrega).filter(models.ItemEntrega.entrega_id == entregas[0].id).all()
        assert len(items) == 2
        assert {(i.trabajo_id, i.cantidad) for i in items} == {(t1.id, 20), (t2.id, 15)}
        # Ambos trabajos quedan con el mismo número de remito (mismo evento).
        assert all(i.numero_remito == entregas[0].numero_remito for i in items)

    def test_remito_combinado_pasa_los_400_solo_de_los_que_exceden(self, client, db):
        cliente = crear_cliente(db)
        t1 = crear_trabajo(db, cliente, cantidad=50)
        t2 = crear_trabajo(db, cliente, cantidad=30)
        crear_entrega(db, t2, cantidad=25, numero_remito="RE-000001")  # a t2 le quedan 5

        r = client.post("/api/entregas", json={
            "cliente_id": cliente.id,
            "items": [
                {"trabajo_id": t1.id, "cantidad": 20},   # ok
                {"trabajo_id": t2.id, "cantidad": 10},   # excede (quedan 5)
            ],
        })

        assert r.status_code == 400
        # No se crea nada de este intento: ni la fila de t1, que sí entraba.
        assert db.query(models.ItemEntrega).filter(models.ItemEntrega.trabajo_id == t1.id).count() == 0

    def test_limite_de_items_por_remito(self, client, db):
        cliente = crear_cliente(db)
        trabajos = [crear_trabajo(db, cliente, cantidad=10) for _ in range(7)]

        r = client.post("/api/entregas", json={
            "cliente_id": cliente.id,
            "items": [{"trabajo_id": t.id, "cantidad": 5} for t in trabajos],
        })

        assert r.status_code == 400

    def test_doble_clic_simultaneo_no_duplica_numero(self, client, db, monkeypatch):
        """Dos remitos concurrentes que leen el mismo 'último número' antes de
        que cualquiera confirme el suyo: la unicidad de numero_remito arbitra,
        y el que pierde reintenta con un número nuevo (ambos remitos son
        válidos y deben persistir, a diferencia de imprimir_orden).
        """
        from routers import entregas as router_entregas

        cliente = crear_cliente(db)
        t1 = crear_trabajo(db, cliente, cantidad=1000)
        t2 = crear_trabajo(db, cliente, cantidad=1000)

        original = router_entregas._generar_numero_remito
        barrera = threading.Barrier(2, timeout=5)

        def generar_sincronizado(sesion):
            numero = original(sesion)
            try:
                barrera.wait()
            except threading.BrokenBarrierError:
                pass
            return numero

        monkeypatch.setattr(router_entregas, "_generar_numero_remito", generar_sincronizado)

        respuestas = []
        def entregar(trabajo_id):
            r = client.post("/api/entregas", json={"cliente_id": cliente.id, "items": [{"trabajo_id": trabajo_id, "cantidad": 100}]})
            respuestas.append(r.status_code)

        hilos = [threading.Thread(target=entregar, args=(t.id,)) for t in (t1, t2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=15)

        assert respuestas.count(200) == 2, f"Respuestas: {respuestas}"

        entregas = db.query(models.Entrega).all()
        assert len(entregas) == 2
        assert len({e.numero_remito for e in entregas}) == 2, (
            f"Dos remitos terminaron con el mismo número: {[e.numero_remito for e in entregas]}"
        )


class TestReimprimirEntrega:

    def test_reimprimir_no_crea_fila_nueva(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)
        item = crear_entrega(db, trabajo, cantidad=50, numero_remito="RE-000001")

        r = client.get(f"/api/entregas/{item.entrega_id}/pdf")

        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert db.query(models.Entrega).count() == 1
        assert db.query(models.ItemEntrega).count() == 1

    def test_reimprimir_trae_todas_las_filas_del_remito_combinado(self, client, db):
        cliente = crear_cliente(db)
        t1 = crear_trabajo(db, cliente, cantidad=50)
        t2 = crear_trabajo(db, cliente, cantidad=30)
        item1 = crear_entrega(db, t1, cliente=cliente, cantidad=20, numero_remito="RE-000001")
        agregar_item_entrega(db, item1.entrega, t2, 15)

        r = client.get(f"/api/entregas/{item1.entrega_id}/pdf")

        assert r.status_code == 200, r.text

    def test_404_si_la_entrega_no_existe(self, client, db):
        r = client.get("/api/entregas/no-existe/pdf")

        assert r.status_code == 404
