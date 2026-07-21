"""Tests de routers/presupuestos.py.

Cubren el Caso 10: el trabajo que nace de convertir un presupuesto no arrastra
el papel, así que al imprimir su orden no se descuenta nada del stock.
"""
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
    """El camino más usado del taller —presupuestar y convertir— nunca descuenta
    papel, porque el trabajo nace sin papel_id.

    Presupuesto guarda el papel como texto libre (material, gramaje), que sirve
    para leer el presupuesto pero no identifica un artículo del stock. Trabajo
    necesita papel_id (FK a stock) y cantidad_pliegos para que imprimir-orden
    descuente. Esos dos campos no existen en Presupuesto, así que la conversión
    no tiene de dónde copiarlos.
    """

    def test_el_trabajo_convertido_nace_sin_papel(self, client, db):
        # Caracteriza el estado actual: no es lo deseable, pero es lo que hay.
        cliente = crear_cliente(db)
        p = crear_presupuesto(db, cliente, material="Ilustración", gramaje="150")

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]

        trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
        assert trabajo.papel_id is None
        assert trabajo.cantidad_pliegos is None

    def test_imprimir_su_orden_no_toca_el_stock(self, client, db):
        """La consecuencia real: la orden sale, el papel se usa, el stock no baja.

        Nadie ve un error. El stock se va desfasando de la realidad sin que
        quede rastro de por qué.
        """
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        p = crear_presupuesto(db, cliente, material="Ilustración", gramaje="150")

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]
        r = client.post(f"/api/trabajos/{trabajo_id}/imprimir-orden")

        assert r.status_code == 200  # La orden se emite igual.
        db.refresh(papel)
        assert papel.cantidad == Decimal("500.000")  # Y el stock no se entera.

    def test_el_camino_manual_si_descuenta(self, client, db):
        # Contraste: cargando el trabajo a mano con papel_id, todo funciona.
        # El agujero es exclusivo de la conversión, no del descuento.
        cliente = crear_cliente(db)
        papel = crear_papel(db, cantidad=Decimal("500"))
        trabajo = crear_trabajo(db, cliente, papel_id=papel.id, cantidad_pliegos=Decimal("100"))

        client.post(f"/api/trabajos/{trabajo.id}/imprimir-orden")

        db.refresh(papel)
        assert papel.cantidad == Decimal("400.000")

    def test_se_puede_completar_el_papel_antes_de_imprimir(self, client, db):
        """Paliativo disponible hoy: asignar el papel por PUT tras convertir.

        Mientras Presupuesto no tenga los campos, este es el único camino para
        que un trabajo convertido descuente stock. Que funcione es importante:
        es lo que hay que hacer a mano en cada conversión.
        """
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

    @pytest.mark.xfail(
        strict=True,
        reason="Caso 10 sin resolver: Presupuesto no tiene papel_id ni "
               "cantidad_pliegos, así que la conversión no puede heredarlos. "
               "Arreglarlo es un cambio de modelo (columnas nuevas + schemas + "
               "el form de presupuesto), pendiente de aprobación.",
    )
    def test_deberia_heredar_el_papel_del_presupuesto(self, client, db):
        cliente = crear_cliente(db)
        papel = crear_papel(db)
        p = crear_presupuesto(db, cliente)
        # Así se vería si Presupuesto guardara el papel del stock:
        p.papel_id = papel.id
        p.cantidad_pliegos = Decimal("100")
        db.commit()

        trabajo_id = client.post(f"/api/presupuestos/{p.id}/convertir").json()["id"]

        trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
        assert trabajo.papel_id == papel.id
        assert trabajo.cantidad_pliegos == Decimal("100.000")
