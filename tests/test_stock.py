"""Tests de routers/stock.py.

Cubren el Caso 7: una compra de papel por Kg cuyo peso no llega a medio pliego
se redondea a cero y da de alta un artículo fantasma.
"""
from decimal import Decimal

import pytest

import models
from conftest import crear_papel

# Un pliego de 70x100 cm en 150 grs pesa 0.105 kg (70*100*150/10.000.000).
# Con esas medidas, menos de 0.0525 kg redondea a cero pliegos.
PLIEGO_70x100 = dict(largo_cm=70, ancho_cm=100, gramaje_grs=150)


def item_kg(peso, **overrides):
    datos = dict(
        nombre="Ilustración 150g",
        unidad="Kg",
        peso_total_kg=peso,
        costo_total=50000,
        **PLIEGO_70x100,
    )
    datos.update(overrides)
    return datos


class TestCompraPorKg:

    def test_convierte_el_peso_a_pliegos_enteros(self, client, db):
        # 52.5 kg / 0.105 kg por pliego = 500 pliegos exactos.
        r = client.post("/api/stock/compras", json=[item_kg("52.5")])

        assert r.status_code == 201
        articulo = r.json()[0]
        assert Decimal(str(articulo["cantidad"])) == Decimal("500.000")
        assert articulo["unidad"] == "Pliegos"

    def test_redondea_al_pliego_mas_cercano(self, client, db):
        # El paquete real tiene pliegos enteros: el desvío es del peso nominal.
        r = client.post("/api/stock/compras", json=[item_kg("52.6")])

        assert Decimal(str(r.json()[0]["cantidad"])) == Decimal("501.000")

    def test_reparte_el_costo_total_entre_los_pliegos(self, client, db):
        r = client.post("/api/stock/compras", json=[item_kg("52.5", costo_total=50000)])

        assert Decimal(str(r.json()[0]["costo_unitario"])) == Decimal("100.00")


class TestCompraQueRedondeaACero:
    """Un peso menor a medio pliego da cero pliegos.

    Hoy la compra se acepta: se da de alta un artículo con cantidad 0, se
    asienta un movimiento de historial de 0 y la plata gastada desaparece
    (costo_unitario no se puede calcular sin dividir por cero). Queda un
    artículo fantasma en la lista de stock y nadie se entera de que la carga
    estaba mal.
    """

    def test_rechaza_la_compra_en_vez_de_crear_un_articulo_vacio(self, client, db):
        r = client.post("/api/stock/compras", json=[item_kg("0.05")])

        assert r.status_code == 400, f"Se aceptó una compra de 0 pliegos ({r.status_code})"

    def test_el_error_explica_los_numeros(self, client, db):
        # La causa casi siempre es un dato mal tipeado (mm en vez de cm, grs en
        # vez de kg): el mensaje tiene que dejar ver cuál.
        detalle = client.post("/api/stock/compras", json=[item_kg("0.05")]).json()["detail"]

        assert "0.105" in detalle  # peso de un pliego
        assert "0.05" in detalle   # lo que se compró

    def test_no_deja_ningun_articulo_dado_de_alta(self, client, db):
        client.post("/api/stock/compras", json=[item_kg("0.05")])

        assert db.query(models.ArticuloStock).count() == 0

    def test_no_deja_asientos_en_el_historial(self, client, db):
        client.post("/api/stock/compras", json=[item_kg("0.05")])

        assert db.query(models.HistorialStock).count() == 0

    def test_una_recompra_a_cero_no_toca_el_articulo(self, client, db):
        # Peor que el alta: acá el artículo existe y la compra le suma 0,
        # dejando un asiento inútil en la auditoría de un papel real.
        papel = crear_papel(db, cantidad=Decimal("500"), **PLIEGO_70x100)

        r = client.post("/api/stock/compras", json=[
            item_kg("0.05", articulo_id=papel.id, nombre=None)
        ])

        assert r.status_code == 400
        db.refresh(papel)
        assert papel.cantidad == Decimal("500.000")
        assert db.query(models.HistorialStock).count() == 0

    def test_arrastra_el_carrito_entero(self, client, db):
        # Una compra es una transacción: si un ítem no cierra, no entra ninguno.
        r = client.post("/api/stock/compras", json=[
            item_kg("52.5", nombre="Papel bueno"),
            item_kg("0.05", nombre="Papel mal cargado"),
        ])

        assert r.status_code == 400
        assert "2" in r.json()["detail"]  # identifica el ítem culpable
        assert db.query(models.ArticuloStock).count() == 0

    def test_el_error_no_confunde_con_el_de_datos_faltantes(self, client, db):
        # Redondear a cero no es lo mismo que no cargar las medidas.
        detalle = client.post("/api/stock/compras", json=[item_kg("0.05")]).json()["detail"]

        assert "faltan" not in detalle.lower()


class TestValidacionesDeCompraQueYaExistian:
    """No-regresión: el arreglo no debe tapar los errores que ya se detectaban."""

    def test_exige_las_medidas_para_comprar_por_kg(self, client, db):
        r = client.post("/api/stock/compras", json=[
            dict(nombre="Papel", unidad="Kg", peso_total_kg="10", costo_total=1000)
        ])
        assert r.status_code == 400
        assert "faltan" in r.json()["detail"].lower()

    def test_rechaza_medidas_en_cero(self, client, db):
        r = client.post("/api/stock/compras", json=[item_kg("10", largo_cm=0)])
        assert r.status_code == 400
        assert "mayores a cero" in r.json()["detail"]

    def test_rechaza_cantidad_cero_en_una_compra_por_unidades(self, client, db):
        r = client.post("/api/stock/compras", json=[
            dict(nombre="Tinta negra", unidad="Litros", cantidad=0, costo_total=1000)
        ])
        assert r.status_code == 400
        assert "mayor a cero" in r.json()["detail"]

    def test_una_compra_vacia_no_pasa(self, client, db):
        assert client.post("/api/stock/compras", json=[]).status_code == 400
