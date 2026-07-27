"""Tests de las validaciones de schemas.py.

Son las reglas que atajan datos inválidos ANTES de que lleguen a la base o a
calculos.py. Se prueban contra el schema directo (sin TestClient) porque lo que
importa acá es la validación, no el transporte HTTP: FastAPI convierte
cualquier ValidationError en un 422.
"""
from datetime import date, time
from decimal import Decimal

import pytest
from pydantic import ValidationError

import models
import schemas


def cheque_valido(**overrides):
    """Payload mínimo de un cheque, para sobrescribir sólo lo que se prueba."""
    datos = dict(
        banco="Galicia",
        numero="00012345",
        monto=Decimal("1000"),
        fecha_emision=date(2026, 7, 1),
        fecha_cobro=date(2026, 7, 30),
    )
    datos.update(overrides)
    return datos


# --- Caso 1: detalles_costos ------------------------------------------------

class TestDetallesCostosEnSchema:
    """El dict de costos sólo acepta números: antes un texto llegaba hasta
    sumar_detalles_costos y reventaba con un 500. Ahora los costos viven en cada
    ítem del presupuesto (ItemPresupuesto)."""

    def _item(self, **overrides):
        datos = dict(descripcion="Volantes", cantidad=100, precio_unitario=Decimal("10"))
        datos.update(overrides)
        return datos

    @pytest.mark.parametrize("valor", [1000, "250.50", 0.1])
    def test_acepta_valores_numericos_sin_convertirlos(self, valor):
        # El dict va a una columna JSON: si el validator convirtiera a Decimal,
        # json.dumps reventaría al persistir. Valida, no transforma.
        item = schemas.ItemPresupuestoCreate(**self._item(detalles_costos={"papel": valor}))
        assert item.detalles_costos["papel"] == valor
        assert type(item.detalles_costos["papel"]) is type(valor)

    @pytest.mark.parametrize("basura", ["", "abc", "1,50", [], {}])
    def test_rechaza_valores_no_numericos(self, basura):
        with pytest.raises(ValidationError):
            schemas.ItemPresupuestoCreate(**self._item(detalles_costos={"papel": basura}))

    def test_el_error_nombra_el_costo_culpable(self):
        with pytest.raises(ValidationError, match="tinta"):
            schemas.ItemPresupuestoCreate(**self._item(detalles_costos={"papel": 100, "tinta": "abc"}))

    def test_acepta_null_como_costo_no_cargado(self):
        # calculos.py ya trata None como "no cargado" y lo saltea: rechazarlo
        # rompería compatibilidad con lo que hoy funciona.
        item = schemas.ItemPresupuestoCreate(**self._item(detalles_costos={"papel": None}))
        assert item.detalles_costos == {"papel": None}

    def test_tambien_valida_al_crear_el_presupuesto(self):
        with pytest.raises(ValidationError):
            schemas.PresupuestoCreate(
                fecha_creacion=date(2026, 7, 1),
                items=[self._item(detalles_costos={"papel": ""})],
            )


# --- Caso 2: whitelist de estados -------------------------------------------

class TestEstadoCheque:

    @pytest.mark.parametrize("estado", models.ESTADOS_CHEQUE)
    def test_acepta_todos_los_estados_validos(self, estado):
        assert schemas.ChequeCreate(**cheque_valido(estado=estado)).estado == estado

    @pytest.mark.parametrize("estado", ["banana", "cobrado", "COBRADO", "", "Anulado"])
    def test_rechaza_un_estado_inexistente(self, estado):
        # Incluye las variantes de mayúsculas: 'cobrado' no es 'Cobrado', y si
        # entrara ningún cálculo lo reconocería después.
        with pytest.raises(ValidationError):
            schemas.ChequeCreate(**cheque_valido(estado=estado))

    def test_rechaza_estado_inexistente_tambien_al_editar(self):
        with pytest.raises(ValidationError):
            schemas.ChequeUpdate(estado="banana")

    def test_nace_en_cartera_por_defecto(self):
        assert schemas.ChequeCreate(**cheque_valido()).estado == models.ESTADO_CHEQUE_INICIAL


# --- Caso 3: fecha de endoso ------------------------------------------------

class TestFechaEndoso:
    """Endosar equivale a cobrar y calculos.py usa fecha_endoso para saber
    cuándo se realizó esa plata: sin ella el cheque no cuenta como ingreso."""

    def test_se_completa_al_crear_un_cheque_ya_endosado(self):
        c = schemas.ChequeCreate(**cheque_valido(estado="Endosado"))
        assert c.fecha_endoso == date.today()

    def test_se_completa_al_pasar_a_endosado_por_patch(self):
        u = schemas.ChequeUpdate(estado="Endosado")
        assert u.fecha_endoso == date.today()

    def test_sobrevive_al_exclude_unset_del_patch(self):
        # El router aplica model_dump(exclude_unset=True): si la fecha que puso
        # el validator no quedara marcada como set, se perdería en el camino.
        u = schemas.ChequeUpdate(estado="Endosado")
        assert "fecha_endoso" in u.model_dump(exclude_unset=True)

    def test_respeta_la_fecha_indicada_a_mano(self):
        # Un endoso que se carga tarde conserva su fecha real.
        ayer = date(2026, 1, 5)
        u = schemas.ChequeUpdate(estado="Endosado", fecha_endoso=ayer)
        assert u.fecha_endoso == ayer

    def test_un_cambio_que_no_toca_el_estado_no_inventa_fecha(self):
        u = schemas.ChequeUpdate(banco="Nación")
        assert u.model_dump(exclude_unset=True) == {"banco": "Nación"}

    @pytest.mark.parametrize("estado", ["En Cartera", "Depositado", "Cobrado", "Rechazado"])
    def test_los_demas_estados_no_llevan_fecha_de_endoso(self, estado):
        assert schemas.ChequeCreate(**cheque_valido(estado=estado)).fecha_endoso is None


# --- Caso 5: el trabajo es opcional en un pago ------------------------------

class TestPagoSinTrabajo:

    def test_el_movimiento_acepta_un_pago_sin_trabajo(self):
        # Pago a cuenta: misma política que los cheques recibidos.
        m = schemas.MovimientoCreate(
            cliente_id="C1", monto=Decimal("500"), tipo="Pago",
            metodo="Efectivo", descripcion="Pago a cuenta",
        )
        assert m.trabajo_id is None


# --- Caso 6: los horarios de una fila de asistencia -------------------------

class TestHorariosDeAsistencia:
    """La salida tiene que ser posterior a la entrada.

    No se contempla el turno que cruza la medianoche porque en el taller no
    existe: una salida anterior a la entrada es un error de tipeo, y dejarlo
    pasar mete un día raro en el total de horas del mes.
    """

    def test_una_jornada_normal_pasa(self):
        fila = schemas.FilaPlanillaGuardar(
            empleado_id="E1", hora_entrada=time(8, 0), hora_salida=time(17, 0),
        )
        assert fila.hora_salida == time(17, 0)

    def test_una_salida_anterior_a_la_entrada_se_rechaza(self):
        with pytest.raises(ValidationError, match="posterior"):
            schemas.FilaPlanillaGuardar(
                empleado_id="E1", hora_entrada=time(17, 0), hora_salida=time(8, 0),
            )

    def test_entrar_y_salir_a_la_misma_hora_se_rechaza(self):
        with pytest.raises(ValidationError, match="posterior"):
            schemas.FilaPlanillaGuardar(
                empleado_id="E1", hora_entrada=time(8, 0), hora_salida=time(8, 0),
            )

    def test_una_entrada_sin_salida_pasa(self):
        # El empleado entró y todavía no salió: la planilla se guarda igual.
        fila = schemas.FilaPlanillaGuardar(empleado_id="E1", hora_entrada=time(8, 0))
        assert fila.hora_salida is None

    def test_una_fila_vacia_pasa(self):
        # Es la fila de alguien que no vino. El router la usa para borrar un
        # registro anterior cargado por error.
        fila = schemas.FilaPlanillaGuardar(empleado_id="E1")
        assert fila.hora_entrada is None and fila.hora_salida is None

    def test_una_fila_solo_con_observaciones_pasa(self):
        fila = schemas.FilaPlanillaGuardar(empleado_id="E1", observaciones="Franco")
        assert fila.observaciones == "Franco"

    def test_la_fila_expone_las_horas_calculadas(self):
        fila = schemas.FilaPlanillaResponse(
            empleado_id="E1", nombre="Eduardo",
            hora_entrada=time(8, 0), hora_salida=time(16, 30),
        )
        assert fila.horas == Decimal("8.50")

    def test_las_horas_no_se_reciben_desde_afuera(self):
        # Son campo calculado: mandarlas no las pisa. Es lo que evita que un
        # total quede desfasado del horario que lo produjo.
        fila = schemas.FilaPlanillaResponse(
            empleado_id="E1", nombre="Eduardo",
            hora_entrada=time(8, 0), hora_salida=time(17, 0), horas=Decimal("99"),
        )
        assert fila.horas == Decimal("9.00")
