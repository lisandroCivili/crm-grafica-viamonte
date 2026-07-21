"""Tests de calculos.py — la matemática financiera del CRM.

calculos.py es código puro: no toca la base ni la sesión, sólo lee atributos de
los objetos que recibe. Por eso los tests usan stubs livianos (SimpleNamespace)
en vez de modelos SQLAlchemy: no hace falta engine ni fixtures de DB.

Los tests marcados con BUG documentan comportamiento actual que quedó señalado
en la auditoría. No se corrigen acá: primero hay que decidir la regla de negocio.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

import pytest

from calculos import (
    CATEGORIA_COSTO_PRESUPUESTADO,
    calcular_precio_presupuesto,
    calcular_saldo_cliente,
    calcular_saldo_trabajo,
    fraccion_ganancia,
    fraccion_ganancia_efectiva,
    ganancia_bruta_realizada,
    ingresos_reales,
    ingresos_sin_imputar,
    sumar_detalles_costos,
    total_gastos,
    total_gastos_operativos,
)

# --- Constructores de stubs -------------------------------------------------
# Cada uno arma el mínimo objeto que la función bajo prueba necesita leer.

JULIO = date(2026, 7, 15)
AGOSTO = date(2026, 8, 15)


def en_julio(f) -> bool:
    """Predicado de período equivalente al de reportes.py, acotado a julio 2026."""
    return bool(f) and f.month == 7 and f.year == 2026


def siempre(f) -> bool:
    """Predicado 'histórico': todo entra."""
    return True


def mov(monto, tipo="Pago", metodo="Efectivo", fecha=JULIO, trabajo_id="T1"):
    return SimpleNamespace(
        monto=Decimal(monto), tipo=tipo, metodo=metodo,
        fecha=fecha, trabajo_id=trabajo_id,
    )


def cheque(monto, estado="En Cartera", clasificacion="Recibido",
           fecha_cobro=JULIO, fecha_endoso=None, trabajo_id="T1"):
    return SimpleNamespace(
        monto=Decimal(monto), estado=estado, clasificacion=clasificacion,
        fecha_cobro=fecha_cobro, fecha_endoso=fecha_endoso, trabajo_id=trabajo_id,
    )


def trabajo(precio, estado="Entregado", id="T1"):
    return SimpleNamespace(id=id, precio_venta=Decimal(precio), estado=estado)


def presupuesto(trabajo_id="T1", margen="50", costo="100"):
    return SimpleNamespace(
        trabajo_id=trabajo_id,
        margen_ganancia=Decimal(margen),
        costo_materiales=Decimal(costo),
    )


def gasto(monto, categoria="Alquiler", trabajo_id=None, fecha=JULIO):
    return SimpleNamespace(
        monto=Decimal(monto), categoria=categoria,
        trabajo_id=trabajo_id, fecha=fecha,
    )


# --- sumar_detalles_costos --------------------------------------------------

class TestSumarDetallesCostos:

    def test_sin_detalles_devuelve_cero(self):
        assert sumar_detalles_costos(None) == Decimal("0.00")
        assert sumar_detalles_costos({}) == Decimal("0.00")

    def test_suma_los_valores(self):
        detalles = {"papel": 1000, "tinta": "250.50", "troquel": Decimal("99.49")}
        assert sumar_detalles_costos(detalles) == Decimal("1349.99")

    def test_ignora_valores_nulos(self):
        assert sumar_detalles_costos({"papel": 100, "tinta": None}) == Decimal("100.00")

    def test_no_arrastra_error_de_float(self):
        # El clásico 0.1 + 0.2 == 0.30000000000000004 no debe aparecer.
        assert sumar_detalles_costos({"a": 0.1, "b": 0.2}) == Decimal("0.30")

    @pytest.mark.parametrize("basura", ["", "abc", "1,50"])
    def test_falla_ruidosamente_ante_un_valor_no_numerico(self, basura):
        # Decisión (auditoría #1): la validación vive en el schema, que rechaza
        # esto con un 422 antes de llegar acá (ver TestDetallesCostosEnSchema).
        # Si igual llegara, tiene que reventar y no devolver un número: silenciar
        # un costo daría un presupuesto mal calculado sin que nadie se entere.
        with pytest.raises(InvalidOperation):
            sumar_detalles_costos({"papel": basura})


# --- calcular_precio_presupuesto --------------------------------------------

class TestCalcularPrecioPresupuesto:

    def test_margen_cero_deja_el_precio_igual_al_costo(self):
        subtotal, ganancia, precio = calcular_precio_presupuesto(
            Decimal("1000"), Decimal("0")
        )
        assert (subtotal, ganancia, precio) == (
            Decimal("1000.00"), Decimal("0.00"), Decimal("1000.00"),
        )

    def test_margen_cincuenta_por_ciento(self):
        _, ganancia, precio = calcular_precio_presupuesto(
            Decimal("1000"), Decimal("50")
        )
        assert ganancia == Decimal("500.00")
        assert precio == Decimal("1500.00")

    def test_redondea_half_up_y_no_bankers(self):
        # 1 * 12.5 / 100 = 0.125 → HALF_UP da 0.13 (banker's rounding daría 0.12).
        _, ganancia, precio = calcular_precio_presupuesto(
            Decimal("1"), Decimal("12.5")
        )
        assert ganancia == Decimal("0.13")
        assert precio == Decimal("1.13")

    def test_margen_negativo_vende_bajo_el_costo(self):
        _, ganancia, precio = calcular_precio_presupuesto(
            Decimal("1000"), Decimal("-20")
        )
        assert ganancia == Decimal("-200.00")
        assert precio == Decimal("800.00")


# --- fraccion_ganancia / fraccion_ganancia_efectiva -------------------------

class TestFraccionGanancia:

    def test_margen_cero_no_deja_ganancia(self):
        assert fraccion_ganancia(Decimal("0")) == Decimal("0")

    def test_margen_cien_deja_la_mitad_de_cada_peso(self):
        assert fraccion_ganancia(Decimal("100")) == Decimal("0.5")

    def test_margen_menos_cien_no_divide_por_cero(self):
        # denom = 100 + (-100) = 0: la guardia devuelve 0 en vez de reventar.
        assert fraccion_ganancia(Decimal("-100")) == Decimal("0")


class TestFraccionGananciaEfectiva:

    def test_sin_costo_congelado_cae_al_margen(self):
        assert fraccion_ganancia_efectiva(
            Decimal("150"), None, Decimal("50")
        ) == fraccion_ganancia(Decimal("50"))

    def test_costo_cero_cae_al_margen(self):
        assert fraccion_ganancia_efectiva(
            Decimal("150"), Decimal("0"), Decimal("50")
        ) == fraccion_ganancia(Decimal("50"))

    def test_precio_sin_editar_coincide_con_el_margen_original(self):
        # precio = costo * (1 + margen/100) = 100 * 1.5 = 150
        assert fraccion_ganancia_efectiva(
            Decimal("150"), Decimal("100"), Decimal("50")
        ) == fraccion_ganancia(Decimal("50"))

    def test_descuento_al_cliente_baja_la_ganancia_real(self):
        # Se vendió a 120 lo que costó 100: la ganancia real es 20/120, no 50/150.
        efectiva = fraccion_ganancia_efectiva(
            Decimal("120"), Decimal("100"), Decimal("50")
        )
        assert efectiva == Decimal("20") / Decimal("120")
        assert efectiva < fraccion_ganancia(Decimal("50"))

    def test_venta_bajo_el_costo_da_fraccion_negativa(self):
        # Vendido a 50 lo que costó 100: pérdida del 100% de lo cobrado.
        assert fraccion_ganancia_efectiva(
            Decimal("50"), Decimal("100"), Decimal("50")
        ) == Decimal("-1")

    @pytest.mark.parametrize("precio", [Decimal("0"), Decimal("-100"), None])
    def test_precio_no_positivo_no_rompe(self, precio):
        # Auditoría #9: TrabajoUpdate.precio_venta no valida signo. Acá está
        # contenido (devuelve 0), pero el precio inválido igual se persiste.
        assert fraccion_ganancia_efectiva(
            precio, Decimal("100"), Decimal("50")
        ) == Decimal("0")


# --- calcular_saldo_trabajo -------------------------------------------------

class TestCalcularSaldoTrabajo:

    def test_sin_pagos_debe_todo(self):
        assert calcular_saldo_trabajo(Decimal("1000"), []) == Decimal("1000.00")

    def test_pago_parcial(self):
        assert calcular_saldo_trabajo(
            Decimal("1000"), [mov("300")]
        ) == Decimal("700.00")

    def test_solo_cuentan_los_movimientos_de_tipo_pago(self):
        # Una 'Edición' o un 'Ajuste' no cancelan deuda.
        movimientos = [mov("300"), mov("999", tipo="Edición"), mov("50", tipo="Ajuste")]
        assert calcular_saldo_trabajo(Decimal("1000"), movimientos) == Decimal("700.00")

    def test_el_cheque_entregado_cancela_deuda(self):
        assert calcular_saldo_trabajo(
            Decimal("1000"), [], [cheque("1000")]
        ) == Decimal("0.00")

    def test_el_cheque_rechazado_reabre_la_deuda(self):
        assert calcular_saldo_trabajo(
            Decimal("1000"), [], [cheque("1000", estado="Rechazado")]
        ) == Decimal("1000.00")

    def test_el_cheque_emitido_no_es_un_pago_del_cliente(self):
        # Un cheque propio a un proveedor no cancela lo que nos deben.
        assert calcular_saldo_trabajo(
            Decimal("1000"), [], [cheque("1000", clasificacion="Emitido")]
        ) == Decimal("1000.00")

    def test_sobrepago_deja_saldo_negativo(self):
        assert calcular_saldo_trabajo(
            Decimal("1000"), [mov("1200")]
        ) == Decimal("-200.00")

    def test_pago_y_cheque_se_suman(self):
        assert calcular_saldo_trabajo(
            Decimal("1000"), [mov("400")], [cheque("600")]
        ) == Decimal("0.00")


# --- calcular_saldo_cliente -------------------------------------------------

class TestCalcularSaldoCliente:

    def test_facturado_pagado_y_saldo(self):
        facturado, pagado, saldo = calcular_saldo_cliente(
            [trabajo("1000"), trabajo("500", id="T2")],
            [mov("300")],
            [cheque("200")],
        )
        assert facturado == Decimal("1500.00")
        assert pagado == Decimal("500.00")
        assert saldo == Decimal("1000.00")

    def test_el_trabajo_cancelado_no_factura(self):
        facturado, _, saldo = calcular_saldo_cliente(
            [trabajo("1000"), trabajo("500", estado="Cancelado", id="T2")], [], []
        )
        assert facturado == Decimal("1000.00")
        assert saldo == Decimal("1000.00")

    def test_trabajo_cancelado_con_sena_deja_saldo_a_favor(self):
        # REGLA DECIDIDA (auditoría #4): la seña de un trabajo cancelado no se
        # devuelve ni se pierde, queda a cuenta del próximo trabajo. El saldo
        # negativo es el comportamiento correcto y este test lo protege.
        # Pendiente en el frontend: mostrarlo como "Saldo a favor" en verde.
        facturado, pagado, saldo = calcular_saldo_cliente(
            [trabajo("1000", estado="Cancelado")], [mov("300")], []
        )
        assert facturado == Decimal("0.00")
        assert pagado == Decimal("300.00")
        assert saldo == Decimal("-300.00")


# --- ingresos_reales --------------------------------------------------------

class TestIngresosReales:

    def test_suma_los_pagos_del_periodo(self):
        assert ingresos_reales([mov("500")], [], en_julio) == Decimal("500.00")

    def test_ignora_los_pagos_fuera_del_periodo(self):
        assert ingresos_reales([mov("500", fecha=AGOSTO)], [], en_julio) == Decimal("0.00")

    def test_acepta_datetime_ademas_de_date(self):
        # Movimiento.fecha es DateTime; _a_fecha lo normaliza antes de comparar.
        pago = mov("500", fecha=datetime(2026, 7, 15, 22, 30))
        assert ingresos_reales([pago], [], en_julio) == Decimal("500.00")

    def test_el_pago_con_metodo_cheque_no_es_ingreso(self):
        # No es plata realizada: se sigue por el módulo Cheques.
        assert ingresos_reales([mov("500", metodo="Cheque")], [], en_julio) == Decimal("0.00")

    @pytest.mark.parametrize("metodo", ["cheque", "CHEQUE", " Cheque "])
    def test_el_metodo_cheque_se_detecta_sin_importar_formato(self, metodo):
        assert ingresos_reales([mov("500", metodo=metodo)], [], en_julio) == Decimal("0.00")

    def test_el_cheque_cobrado_es_ingreso_por_su_fecha_de_cobro(self):
        assert ingresos_reales(
            [], [cheque("800", estado="Cobrado")], en_julio
        ) == Decimal("800.00")

    def test_el_cheque_endosado_es_ingreso_por_su_fecha_de_endoso(self):
        # Endosar realiza la ganancia igual que cobrar (la pata de egreso es el Gasto).
        ch = cheque("800", estado="Endosado", fecha_cobro=AGOSTO, fecha_endoso=JULIO)
        assert ingresos_reales([], [ch], en_julio) == Decimal("800.00")

    def test_el_cheque_en_cartera_todavia_no_es_ingreso(self):
        assert ingresos_reales([], [cheque("800")], en_julio) == Decimal("0.00")

    def test_el_cheque_emitido_nunca_es_ingreso(self):
        ch = cheque("800", estado="Cobrado", clasificacion="Emitido")
        assert ingresos_reales([], [ch], en_julio) == Decimal("0.00")

    def test_cheque_endosado_sin_fecha_de_endoso_no_cuenta(self):
        # BUG (auditoría #3): calculos.py hace lo correcto con el dato que tiene,
        # pero POST /api/cheques permite crear un cheque ya 'Endosado' sin
        # fecha_endoso (el autocompletado vive sólo en el PATCH). Ese cheque
        # queda invisible para los ingresos para siempre.
        ch = cheque("800", estado="Endosado", fecha_endoso=None)
        assert ingresos_reales([], [ch], en_julio) == Decimal("0.00")


# --- ganancia_bruta_realizada -----------------------------------------------

class TestGananciaBrutaRealizada:

    def test_ganancia_proporcional_a_lo_cobrado(self):
        # Costo 100, margen 50 → precio 150. Se cobran 150 → ganancia 50.
        ganancia = ganancia_bruta_realizada(
            [presupuesto()], [trabajo("150")], [mov("150")], [], en_julio
        )
        assert ganancia == Decimal("50.00")

    def test_cobro_parcial_realiza_ganancia_parcial(self):
        # Se cobra la mitad (75 de 150) → se realiza la mitad de la ganancia.
        ganancia = ganancia_bruta_realizada(
            [presupuesto()], [trabajo("150")], [mov("75")], [], en_julio
        )
        assert ganancia == Decimal("25.00")

    def test_trabajo_sin_presupuesto_no_aporta_ganancia(self):
        # El cobro sí es ingreso, pero sin presupuesto no hay costo con qué
        # calcular la ganancia (si no, daría 100%).
        ganancia = ganancia_bruta_realizada(
            [], [trabajo("150")], [mov("150")], [], en_julio
        )
        assert ganancia == Decimal("0.00")

    def test_el_descuento_al_cliente_reduce_la_ganancia_realizada(self):
        # Presupuestado a 150 (costo 100) pero se editó el precio a 120.
        # El costo está hundido: la ganancia real es 20, no 40.
        ganancia = ganancia_bruta_realizada(
            [presupuesto()], [trabajo("120")], [mov("120")], [], en_julio
        )
        assert ganancia == Decimal("20.00")

    def test_el_cheque_cobrado_realiza_ganancia(self):
        ganancia = ganancia_bruta_realizada(
            [presupuesto()], [trabajo("150")],
            [], [cheque("150", estado="Cobrado")], en_julio,
        )
        assert ganancia == Decimal("50.00")

    def test_cheque_sin_trabajo_imputado_es_ingreso_pero_no_ganancia(self):
        # REGLA DECIDIDA (auditoría #5): un cobro puede no estar imputado a un
        # trabajo (pago a cuenta). Es ingreso real, pero sin presupuesto no hay
        # costo con qué calcular ganancia. Para que esa plata no quede invisible
        # se informa aparte en ingresos_sin_imputar.
        ch = cheque("150", estado="Cobrado", trabajo_id=None)
        assert ingresos_reales([], [ch], en_julio) == Decimal("150.00")
        assert ingresos_sin_imputar([], [ch], en_julio) == Decimal("150.00")
        assert ganancia_bruta_realizada(
            [presupuesto()], [trabajo("150")], [], [ch], en_julio
        ) == Decimal("0.00")


# --- ingresos_sin_imputar ---------------------------------------------------

class TestIngresosSinImputar:

    def test_todo_imputado_no_deja_nada_suelto(self):
        assert ingresos_sin_imputar(
            [mov("500")], [cheque("300", estado="Cobrado")], en_julio
        ) == Decimal("0.00")

    def test_cuenta_el_pago_a_cuenta_sin_trabajo(self):
        assert ingresos_sin_imputar(
            [mov("500", trabajo_id=None)], [], en_julio
        ) == Decimal("500.00")

    def test_suma_pagos_y_cheques_sin_imputar(self):
        movimientos = [mov("500", trabajo_id=None), mov("200")]
        cheques = [cheque("300", estado="Cobrado", trabajo_id=None)]
        assert ingresos_sin_imputar(movimientos, cheques, en_julio) == Decimal("800.00")

    def test_nunca_supera_a_los_ingresos_totales(self):
        # Invariante: es un subconjunto de ingresos_reales, misma regla de cobro.
        movimientos = [mov("500", trabajo_id=None), mov("200")]
        cheques = [cheque("300", estado="Cobrado", trabajo_id=None),
                   cheque("100", estado="En Cartera", trabajo_id=None)]
        sin_imputar = ingresos_sin_imputar(movimientos, cheques, en_julio)
        assert sin_imputar <= ingresos_reales(movimientos, cheques, en_julio)
        # El cheque En Cartera no entra: todavía no es plata realizada.
        assert sin_imputar == Decimal("800.00")

    def test_lo_que_no_es_ingreso_tampoco_esta_sin_imputar(self):
        # Un pago con método Cheque no es plata realizada por sí mismo.
        assert ingresos_sin_imputar(
            [mov("500", metodo="Cheque", trabajo_id=None)], [], en_julio
        ) == Decimal("0.00")

    def test_ignora_lo_de_otro_periodo(self):
        assert ingresos_sin_imputar(
            [mov("500", trabajo_id=None, fecha=AGOSTO)], [], en_julio
        ) == Decimal("0.00")


# --- total_gastos / total_gastos_operativos ---------------------------------

class TestTotalGastos:

    def test_suma_los_gastos_del_periodo(self):
        gastos = [gasto("500"), gasto("300"), gasto("999", fecha=AGOSTO)]
        assert total_gastos(gastos, en_julio) == Decimal("800.00")

    def test_los_egresos_incluyen_los_costos_presupuestados(self):
        # Plata que salió de la caja, sin importar de dónde se descuenta.
        gastos = [gasto("500", categoria=CATEGORIA_COSTO_PRESUPUESTADO, trabajo_id="T1")]
        assert total_gastos(gastos, en_julio) == Decimal("500.00")


class TestTotalGastosOperativos:

    def test_el_gasto_comun_resta_de_la_ganancia(self):
        assert total_gastos_operativos(
            [gasto("500")], en_julio, set()
        ) == Decimal("500.00")

    def test_el_costo_presupuestado_no_resta_dos_veces(self):
        # Su costo ya está descontado dentro del margen del presupuesto.
        gastos = [gasto("500", categoria=CATEGORIA_COSTO_PRESUPUESTADO, trabajo_id="T1")]
        assert total_gastos_operativos(gastos, en_julio, {"T1"}) == Decimal("0.00")

    def test_costo_presupuestado_de_un_trabajo_sin_presupuesto_si_resta(self):
        # Red de seguridad: ese costo nunca estuvo dentro de ningún margen, así
        # que si no restara acá desaparecería e inflaría la ganancia.
        gastos = [gasto("500", categoria=CATEGORIA_COSTO_PRESUPUESTADO, trabajo_id="T9")]
        assert total_gastos_operativos(gastos, en_julio, {"T1"}) == Decimal("500.00")

    def test_la_diferencia_con_los_egresos_son_los_costos_presupuestados(self):
        # Es la resta que reportes.py expone como costos_presupuestados.
        gastos = [
            gasto("500", categoria=CATEGORIA_COSTO_PRESUPUESTADO, trabajo_id="T1"),
            gasto("300", categoria="Alquiler"),
        ]
        egresos = total_gastos(gastos, en_julio)
        operativos = total_gastos_operativos(gastos, en_julio, {"T1"})
        assert egresos == Decimal("800.00")
        assert operativos == Decimal("300.00")
        assert egresos - operativos == Decimal("500.00")
