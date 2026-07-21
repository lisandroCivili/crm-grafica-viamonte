"""Tests de routers/presupuestos.py.

Cubren el Caso 10: el trabajo que nace de convertir un presupuesto no arrastra
el papel, así que al imprimir su orden no se descuenta nada del stock.
"""
from datetime import date
from decimal import Decimal

import pytest

import models
from conftest import crear_cliente, crear_papel, crear_presupuesto, crear_trabajo


class TestConvertirPresupuesto:

    def test_hereda_los_datos_economicos(self, client, db):
        # Guarda de no-regresión de lo que sí se copia hoy.
        cliente = crear_cliente(db)
        p = crear_presupuesto(db, cliente, precio_final=Decimal("30000"),
                              costo_materiales=Decimal("20000"))

        r = client.post(f"/api/presupuestos/{p.id}/convertir")

        assert r.status_code == 200
        trabajo = r.json()
        assert Decimal(str(trabajo["precio_venta"])) == Decimal("30000")
        assert Decimal(str(trabajo["costo_total_materiales"])) == Decimal("20000")
        assert trabajo["estado"] == "Aprobado"

    def test_no_se_puede_convertir_dos_veces(self, client, db):
        cliente = crear_cliente(db)
        p = crear_presupuesto(db, cliente)

        assert client.post(f"/api/presupuestos/{p.id}/convertir").status_code == 200
        assert client.post(f"/api/presupuestos/{p.id}/convertir").status_code == 409

    def test_exige_cliente_antes_de_convertir(self, client, db):
        p = crear_presupuesto(db)  # Borrador sin cliente asignado.
        r = client.post(f"/api/presupuestos/{p.id}/convertir")
        assert r.status_code == 400


class TestPapelDelPresupuestoConvertido:
    """El presupuesto elige el papel del stock y el trabajo convertido lo hereda.

    Sin esto, el camino más usado del taller —presupuestar, convertir,
    imprimir— nunca descontaba papel: el trabajo nacía con papel_id en NULL,
    la orden salía igual y el stock se desfasaba en silencio.

    Presupuesto sigue guardando además material y gramaje como texto libre:
    eso es lo que se lee en el presupuesto impreso. papel_id existe sólo para
    saber QUÉ descontar del stock, mismo criterio que papel_tipo/papel_id en
    Trabajo.
    """

    def test_el_trabajo_convertido_hereda_el_papel(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        p = crear_presupuesto(db, cliente, papel_id=papel.id,
                              cantidad_pliegos=Decimal("100"))

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]

        trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
        assert trabajo.papel_id == papel.id
        assert trabajo.cantidad_pliegos == Decimal("100.000")

    def test_al_imprimir_la_orden_descuenta_el_stock(self, client, db):
        # El objetivo real del caso: que el flujo completo cierre.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        p = crear_presupuesto(db, cliente, papel_id=papel.id,
                              cantidad_pliegos=Decimal("100"))

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]
        assert client.post(f"/api/trabajos/{trabajo_id}/imprimir-orden").status_code == 200

        db.refresh(papel)
        assert papel.cantidad == Decimal("400.000")

    def test_un_presupuesto_sin_papel_sigue_funcionando(self, client, db):
        # El papel es opcional: lo puede traer el cliente o comprarse en el
        # momento. Un presupuesto sin papel del stock convierte igual.
        cliente = crear_cliente(db)
        p = crear_presupuesto(db, cliente, material="Papel del cliente")

        r = client.post(f"/api/presupuestos/{p.id}/convertir")

        assert r.status_code == 200
        trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == r.json()["id"]).first()
        assert trabajo.papel_id is None

    def test_no_pisa_el_material_en_texto(self, client, db):
        # material/gramaje son lo que se lee en el presupuesto impreso: elegir
        # un papel del stock no los reemplaza.
        cliente = crear_cliente(db)
        papel = crear_papel(db, nombre="Ilustración 150g")
        p = crear_presupuesto(db, cliente, material="Obra 90", gramaje="90",
                              papel_id=papel.id, cantidad_pliegos=Decimal("50"))

        client.post(f"/api/presupuestos/{p.id}/convertir")

        db.refresh(p)
        assert p.material == "Obra 90"
        assert p.gramaje == "90"

    def test_el_camino_manual_si_descuenta(self, client, db):
        # Contraste: cargando el trabajo a mano con papel_id, todo funciona.
        # El agujero es exclusivo de la conversión, no del descuento.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        db.refresh(papel)
        assert papel.cantidad == Decimal("400.000")

    def test_se_puede_completar_el_papel_despues_de_convertir(self, client, db):
        # Sigue valiendo para el presupuesto que se cargó sin papel: el trabajo
        # se completa por PUT antes de imprimir.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        p = crear_presupuesto(db, cliente)

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]
        r = client.put(
            f"/api/trabajos/{trabajo_id}",
            json={"papel_id": papel.id, "cantidad_pliegos": 100},
        )
        assert r.status_code == 200

        client.post(f"/api/trabajos/{trabajo_id}/imprimir-orden")
        db.refresh(papel)
        assert papel.cantidad == Decimal("400.000")


class TestValidacionDelPapelEnPresupuesto:
    """Mismas reglas que en Trabajo: el papel tiene que existir, medirse en
    pliegos y la cantidad ser un entero positivo.

    Sin esto un presupuesto podría apuntar a un bidón de tinta o a un artículo
    inexistente, y el error recién aparecería al convertir o al imprimir, lejos
    de donde se cargó el dato.
    """

    def test_rechaza_un_papel_inexistente(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id, "descripcion": "V", "cantidad": 10,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "papel_id": "no-existe", "cantidad_pliegos": 100,
        })
        assert r.status_code == 404

    def test_rechaza_un_articulo_que_no_se_mide_en_pliegos(self, client, db):
        cliente = crear_cliente(db)
        tinta = crear_papel(db, nombre="Tinta negra", unidad="Litros")
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id, "descripcion": "V", "cantidad": 10,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "papel_id": tinta.id, "cantidad_pliegos": 100,
        })
        assert r.status_code == 400
        assert "pliegos" in r.json()["detail"].lower()

    @pytest.mark.parametrize("pliegos", [0, -5, 10.5])
    def test_rechaza_cantidades_de_pliegos_invalidas(self, client, db, pliegos):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id, "descripcion": "V", "cantidad": 10,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "papel_id": papel.id, "cantidad_pliegos": pliegos,
        })
        assert r.status_code == 400

    def test_rechaza_un_papel_sin_pliegos(self, client, db):
        # Es el Caso 10 en chico: se elige el papel, no se dice cuánto, y el
        # descuento se saltea sin avisar.
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id, "descripcion": "V", "cantidad": 10,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "papel_id": papel.id,
        })
        assert r.status_code == 400
        assert "pliegos" in r.json()["detail"].lower()

    def test_rechaza_pliegos_sin_papel(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id, "descripcion": "V", "cantidad": 10,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "cantidad_pliegos": 100,
        })
        assert r.status_code == 400
        assert "papel" in r.json()["detail"].lower()

    def test_tambien_valida_al_editar(self, client, db):
        cliente = crear_cliente(db)
        p = crear_presupuesto(db, cliente)
        r = client.put(f"/api/presupuestos/{p.id}",
                       json={"papel_id": "no-existe", "cantidad_pliegos": 100})
        assert r.status_code == 404

    def test_se_puede_asignar_el_papel_al_editar(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        p = crear_presupuesto(db, cliente)

        r = client.put(f"/api/presupuestos/{p.id}",
                       json={"papel_id": papel.id, "cantidad_pliegos": 100})

        assert r.status_code == 200
        db.refresh(p)
        assert p.papel_id == papel.id


class TestBorrarPapelUsadoPorUnPresupuesto:
    """eliminar_articulo sólo miraba trabajos.

    Un papel referenciado por un presupuesto podía borrarse, y la conversión
    posterior terminaba en IntegrityError: el mismo 500 opaco del Caso 8.
    """

    def test_no_se_puede_borrar_un_papel_presupuestado(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        crear_presupuesto(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        r = client.delete(f"/api/stock/{papel.id}")

        assert r.status_code == 400
        assert "presupuesto" in r.json()["detail"].lower()

    def test_el_papel_sigue_existiendo_tras_el_rechazo(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        crear_presupuesto(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.delete(f"/api/stock/{papel.id}")

        assert db.query(models.ArticuloStock).filter(
            models.ArticuloStock.id == papel.id
        ).first()

    def test_un_papel_libre_se_puede_borrar(self, client, db):
        papel = crear_papel(db)
        assert client.delete(f"/api/stock/{papel.id}").status_code == 200

    def test_sigue_bloqueando_por_trabajos(self, client, db):
        # No-regresión del chequeo que ya existía.
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        r = client.delete(f"/api/stock/{papel.id}")
        assert r.status_code == 400
        assert "trabajos" in r.json()["detail"].lower()
