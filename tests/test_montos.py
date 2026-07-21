"""Caso 9: montos negativos.

Un importe negativo no representa nada en el taller y además invierte el signo
de los cálculos sin avisar: un gasto negativo infla la ganancia, un pago
negativo agranda la deuda del cliente y un precio negativo hace que un trabajo
entregado figure como plata a favor.

calculos.py opera bien con lo que le dan; el problema es que estos valores
llegan a la base. La validación va en el schema, que es donde ya viven las
demás reglas de entrada.

El cero NO se rechaza: un trabajo de cortesía (una reimpresión por error
propio) se factura en 0 y es legítimo. Lo que no existe es el negativo.
"""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import schemas
from conftest import crear_cliente, crear_trabajo


class TestPrecioDeTrabajo:

    def test_rechaza_un_precio_negativo(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id,
            "fecha_creacion": str(date.today()),
            "precio_venta": -50000,
        })
        assert r.status_code == 422

    def test_acepta_un_trabajo_de_cortesia_en_cero(self, client, db):
        # Reimpresión por error del taller: se hace, no se cobra.
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id,
            "fecha_creacion": str(date.today()),
            "precio_venta": 0,
        })
        assert r.status_code == 200

    def test_rechaza_un_precio_negativo_al_editar(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        r = client.put(f"/api/trabajos/{trabajo.id}", json={"precio_venta": -1})
        assert r.status_code == 422

    def test_el_trabajo_conserva_su_precio_tras_el_rechazo(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, precio_venta=Decimal("50000"))

        client.put(f"/api/trabajos/{trabajo.id}", json={"precio_venta": -1})

        db.refresh(trabajo)
        assert trabajo.precio_venta == Decimal("50000.00")

    def test_rechaza_un_costo_de_materiales_negativo(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id,
            "fecha_creacion": str(date.today()),
            "precio_venta": 1000,
            "costo_total_materiales": -500,
        })
        assert r.status_code == 422


class TestMontoDeMovimiento:

    def test_rechaza_un_pago_negativo(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/movimientos/", json={
            "cliente_id": cliente.id, "monto": -1000,
            "tipo": "Pago", "metodo": "Efectivo", "descripcion": "Pago",
        })
        assert r.status_code == 422

    def test_rechaza_un_monto_negativo_al_corregir(self):
        with pytest.raises(ValidationError):
            schemas.MovimientoUpdate(monto=Decimal("-1"))


class TestMontoDeGasto:

    def test_rechaza_un_gasto_negativo(self, client, db):
        # Un gasto negativo se resta al revés y aparece como ganancia.
        r = client.post("/api/gastos/", json={
            "categoria": "Insumos", "concepto": "Tinta",
            "monto": -5000, "fecha": str(date.today()),
        })
        assert r.status_code == 422

    def test_rechaza_un_gasto_negativo_al_editar(self):
        with pytest.raises(ValidationError):
            schemas.GastoUpdate(monto=Decimal("-1"))


class TestMontoDeCheque:

    def test_rechaza_un_cheque_negativo(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/cheques/", json={
            "cliente_id": cliente.id, "banco": "Galicia", "numero": "123",
            "monto": -1000, "fecha_emision": str(date.today()),
            "fecha_cobro": str(date.today()),
        })
        assert r.status_code == 422

    def test_rechaza_un_cheque_negativo_al_editar(self):
        with pytest.raises(ValidationError):
            schemas.ChequeUpdate(monto=Decimal("-1"))


class TestPresupuesto:

    def test_rechaza_un_costo_negativo_en_el_detalle(self, client, db):
        # Complementa el Caso 1: ahí se validó que fueran números, acá que no
        # sean números al revés.
        r = client.post("/api/presupuestos/", json={
            "descripcion": "Volantes", "cantidad": 1000,
            "margen_ganancia": 50, "fecha_creacion": str(date.today()),
            "detalles_costos": {"papel": -1000},
        })
        assert r.status_code == 422

    def test_acepta_un_margen_negativo(self, client, db):
        # Vender bajo costo es una decisión comercial válida (liquidar un saldo
        # de papel, no perder un cliente). No es un dato mal cargado.
        r = client.post("/api/presupuestos/", json={
            "descripcion": "Volantes", "cantidad": 1000,
            "margen_ganancia": -10, "fecha_creacion": str(date.today()),
            "detalles_costos": {"papel": 1000},
        })
        assert r.status_code == 200

    def test_acepta_un_margen_de_menos_cien(self, client, db):
        # -100% es regalarlo: precio final 0, el mismo caso de cortesía.
        r = client.post("/api/presupuestos/", json={
            "descripcion": "Volantes", "cantidad": 1000,
            "margen_ganancia": -100, "fecha_creacion": str(date.today()),
            "detalles_costos": {"papel": 1000},
        })
        assert r.status_code == 200
        assert Decimal(str(r.json()["precio_final"])) == Decimal("0")

    def test_rechaza_un_margen_que_da_precio_negativo(self, client, db):
        # Menos de -100% significa pagarle al cliente por llevarse el trabajo.
        r = client.post("/api/presupuestos/", json={
            "descripcion": "Volantes", "cantidad": 1000,
            "margen_ganancia": -200, "fecha_creacion": str(date.today()),
            "detalles_costos": {"papel": 1000},
        })
        assert r.status_code == 422


class TestPrecioNegativoPorLaPuertaDeAtras:
    """convertir_presupuesto crea el Trabajo por ORM, salteando TrabajoCreate.

    Sin cortar el margen, un presupuesto con margen < -100% produce un
    precio_final negativo que entra a trabajos sin pasar por ninguna
    validación. Y como TrabajoResponse hereda el validador, el trabajo
    resultante ni siquiera se puede volver a leer: reventaría al serializar.
    """

    def test_un_presupuesto_no_puede_producir_un_trabajo_negativo(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/presupuestos/", json={
            "cliente_id": cliente.id,
            "descripcion": "Volantes", "cantidad": 1000,
            "margen_ganancia": -200, "fecha_creacion": str(date.today()),
            "detalles_costos": {"papel": 1000},
        })
        assert r.status_code == 422, "El presupuesto con precio negativo no debería crearse"

    def test_el_listado_de_trabajos_se_puede_leer_siempre(self, client, db):
        # La contracara del validador en el Response: si un importe negativo
        # llegara igual a la base, la pantalla de trabajos dejaría de abrir.
        # Este test es el canario de que ningún camino los deja entrar.
        cliente = crear_cliente(db)
        crear_trabajo(db, cliente)
        assert client.get("/api/trabajos/").status_code == 200


class TestMensajeDeError:

    def test_el_error_dice_de_que_campo_se_trata(self, client, db):
        cliente = crear_cliente(db)
        r = client.post("/api/trabajos/", json={
            "cliente_id": cliente.id,
            "fecha_creacion": str(date.today()),
            "precio_venta": -50000,
        })
        assert r.status_code == 422
        assert "precio_venta" in str(r.json())
