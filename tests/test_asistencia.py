"""Tests de los routers de Empleados y Asistencia.

Lo que más se cuida acá es el upsert de la planilla: el operador guarda el mismo
día varias veces (carga la entrada a la mañana, la salida a la tarde, corrige un
horario), y cada guardado tiene que actualizar la fila, no agregar una nueva.
"""
from datetime import date, time
from decimal import Decimal

import pytest

import models
from conftest import crear_empleado, crear_registro_asistencia

HOY = date(2026, 7, 27)


def fila(empleado, entrada=None, salida=None, observaciones=None):
    """Una fila de la planilla tal como la manda el frontend."""
    return {
        "empleado_id": empleado.id,
        "hora_entrada": entrada,
        "hora_salida": salida,
        "observaciones": observaciones,
    }


def guardar(client, fecha, filas):
    return client.post("/api/asistencia/planilla", json={"fecha": str(fecha), "filas": filas})


# --- ABM de empleados -------------------------------------------------------

class TestEmpleados:

    def test_da_de_alta_un_empleado(self, client, db):
        r = client.post("/api/empleados/", json={"nombre": "Eduardo"})

        assert r.status_code == 200
        assert r.json()["nombre"] == "Eduardo"
        assert r.json()["activo"] is True
        assert db.query(models.Empleado).count() == 1

    def test_lista_solo_los_activos_por_defecto(self, client, db):
        crear_empleado(db, nombre="Eduardo")
        crear_empleado(db, nombre="Diego", activo=False)

        nombres = [e["nombre"] for e in client.get("/api/empleados/").json()]
        assert nombres == ["Eduardo"]

    def test_los_lista_por_nombre(self, client, db):
        for nombre in ("Lucio", "Diego", "Eduardo"):
            crear_empleado(db, nombre=nombre)

        nombres = [e["nombre"] for e in client.get("/api/empleados/").json()]
        assert nombres == ["Diego", "Eduardo", "Lucio"]

    def test_puede_pedir_tambien_los_inactivos(self, client, db):
        crear_empleado(db, nombre="Eduardo")
        crear_empleado(db, nombre="Diego", activo=False)

        r = client.get("/api/empleados/?incluir_inactivos=true")
        assert len(r.json()) == 2

    def test_da_de_baja_sin_borrar(self, client, db):
        empleado = crear_empleado(db, nombre="Diego")

        r = client.put(f"/api/empleados/{empleado.id}", json={"activo": False})

        assert r.status_code == 200
        assert r.json()["activo"] is False
        # Sigue existiendo: la baja es lógica.
        assert db.query(models.Empleado).count() == 1

    def test_un_empleado_que_no_existe_da_404(self, client):
        assert client.put("/api/empleados/nope", json={"nombre": "X"}).status_code == 404


class TestBorrarEmpleado:
    """Borrar existe para deshacer un alta equivocada, no para dar de baja."""

    def test_borra_uno_al_que_nunca_se_le_cargo_nada(self, client, db):
        empleado = crear_empleado(db, nombre="Alta equivocada")

        r = client.delete(f"/api/empleados/{empleado.id}")

        assert r.status_code == 200
        assert db.query(models.Empleado).count() == 0

    def test_no_borra_uno_con_asistencia_cargada(self, client, db):
        empleado = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(db, empleado, fecha=HOY)

        r = client.delete(f"/api/empleados/{empleado.id}")

        assert r.status_code == 400
        assert "dalo de baja" in r.json()["detail"].lower()
        # Ni el empleado ni su historial de horas se tocaron.
        assert db.query(models.Empleado).count() == 1
        assert db.query(models.RegistroAsistencia).count() == 1


# --- La planilla del día ----------------------------------------------------

class TestVerPlanilla:

    def test_trae_una_fila_por_empleado_aunque_no_tenga_nada_cargado(self, client, db):
        crear_empleado(db, nombre="Eduardo")
        crear_empleado(db, nombre="Lucio")

        r = client.get(f"/api/asistencia/planilla?fecha={HOY}")

        assert r.status_code == 200
        filas = r.json()["filas"]
        assert [f["nombre"] for f in filas] == ["Eduardo", "Lucio"]
        # Sin registro, las horas vienen en null y no en 0.
        assert all(f["horas"] is None for f in filas)

    def test_devuelve_las_horas_calculadas_por_el_backend(self, client, db):
        empleado = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(
            db, empleado, fecha=HOY, hora_entrada=time(8, 0), hora_salida=time(16, 30)
        )

        fila_eduardo = client.get(f"/api/asistencia/planilla?fecha={HOY}").json()["filas"][0]
        assert Decimal(str(fila_eduardo["horas"])) == Decimal("8.50")

    def test_sin_fecha_devuelve_la_de_hoy(self, client, db):
        crear_empleado(db, nombre="Eduardo")

        assert client.get("/api/asistencia/planilla").json()["fecha"] == str(date.today())

    def test_un_empleado_inactivo_no_aparece(self, client, db):
        crear_empleado(db, nombre="Eduardo")
        crear_empleado(db, nombre="Diego", activo=False)

        filas = client.get(f"/api/asistencia/planilla?fecha={HOY}").json()["filas"]
        assert [f["nombre"] for f in filas] == ["Eduardo"]

    def test_pero_si_tiene_algo_cargado_ese_dia_si_aparece(self, client, db):
        # Se dio de baja en marzo: su día de febrero tiene que seguir viéndose.
        diego = crear_empleado(db, nombre="Diego", activo=False)
        crear_registro_asistencia(db, diego, fecha=HOY)

        filas = client.get(f"/api/asistencia/planilla?fecha={HOY}").json()["filas"]
        assert [f["nombre"] for f in filas] == ["Diego"]


class TestGuardarPlanilla:

    def test_guarda_el_dia_completo(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")
        lucio = crear_empleado(db, nombre="Lucio")

        r = guardar(client, HOY, [
            fila(eduardo, "08:00", "17:00"),
            fila(lucio, "08:30", "17:00"),
        ])

        assert r.status_code == 200
        assert db.query(models.RegistroAsistencia).count() == 2

    def test_devuelve_la_planilla_ya_guardada_con_las_horas(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        filas = guardar(client, HOY, [fila(eduardo, "08:00", "17:00")]).json()["filas"]

        assert Decimal(str(filas[0]["horas"])) == Decimal("9.00")

    def test_guardar_dos_veces_actualiza_y_no_duplica(self, client, db):
        # El caso real: se carga la entrada a la mañana y la salida a la tarde.
        eduardo = crear_empleado(db, nombre="Eduardo")

        guardar(client, HOY, [fila(eduardo, "08:00")])
        guardar(client, HOY, [fila(eduardo, "08:00", "17:00")])

        assert db.query(models.RegistroAsistencia).count() == 1
        registro = db.query(models.RegistroAsistencia).first()
        assert registro.hora_salida == time(17, 0)

    def test_corregir_un_horario_pisa_el_anterior(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")
        guardar(client, HOY, [fila(eduardo, "08:00", "17:00")])

        guardar(client, HOY, [fila(eduardo, "09:00", "17:00")])

        assert db.query(models.RegistroAsistencia).count() == 1
        assert db.query(models.RegistroAsistencia).first().hora_entrada == time(9, 0)

    def test_dias_distintos_son_registros_distintos(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        guardar(client, HOY, [fila(eduardo, "08:00", "17:00")])
        guardar(client, date(2026, 7, 28), [fila(eduardo, "08:00", "17:00")])

        assert db.query(models.RegistroAsistencia).count() == 2

    def test_una_fila_vacia_borra_lo_que_habia(self, client, db):
        # Es la forma de deshacer una carga equivocada desde la misma planilla.
        eduardo = crear_empleado(db, nombre="Eduardo")
        guardar(client, HOY, [fila(eduardo, "08:00", "17:00")])

        guardar(client, HOY, [fila(eduardo)])

        assert db.query(models.RegistroAsistencia).count() == 0

    def test_una_fila_vacia_sin_registro_previo_no_crea_nada(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        r = guardar(client, HOY, [fila(eduardo)])

        assert r.status_code == 200
        assert db.query(models.RegistroAsistencia).count() == 0

    def test_guarda_una_fila_que_solo_tiene_observaciones(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        guardar(client, HOY, [fila(eduardo, observaciones="Franco")])

        registro = db.query(models.RegistroAsistencia).first()
        assert registro.observaciones == "Franco"
        assert registro.hora_entrada is None

    def test_una_observacion_en_blanco_cuenta_como_vacia(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        guardar(client, HOY, [fila(eduardo, observaciones="   ")])

        assert db.query(models.RegistroAsistencia).count() == 0


class TestGuardarPlanillaInvalida:

    def test_rechaza_una_salida_anterior_a_la_entrada(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")

        r = guardar(client, HOY, [fila(eduardo, "17:00", "08:00")])

        assert r.status_code == 422
        assert db.query(models.RegistroAsistencia).count() == 0

    def test_rechaza_dos_filas_del_mismo_empleado(self, client, db):
        # La segunda pisaría a la primera sin que nadie se entere.
        eduardo = crear_empleado(db, nombre="Eduardo")

        r = guardar(client, HOY, [fila(eduardo, "08:00", "12:00"), fila(eduardo, "13:00", "17:00")])

        assert r.status_code == 400
        assert db.query(models.RegistroAsistencia).count() == 0

    def test_rechaza_un_empleado_que_no_existe(self, client, db):
        r = guardar(client, HOY, [{"empleado_id": "nope", "hora_entrada": "08:00"}])

        assert r.status_code == 404

    def test_una_fila_invalida_no_guarda_ninguna(self, client, db):
        # Un solo commit al final: media planilla cargada es peor que ninguna.
        eduardo = crear_empleado(db, nombre="Eduardo")
        lucio = crear_empleado(db, nombre="Lucio")

        guardar(client, HOY, [fila(eduardo, "08:00", "17:00"), fila(lucio, "17:00", "08:00")])

        assert db.query(models.RegistroAsistencia).count() == 0


# --- El resumen del período -------------------------------------------------

class TestResumen:

    def test_suma_las_horas_de_cada_empleado(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(
            db, eduardo, fecha=date(2026, 7, 1), hora_entrada=time(8, 0), hora_salida=time(17, 0)
        )
        crear_registro_asistencia(
            db, eduardo, fecha=date(2026, 7, 2), hora_entrada=time(8, 0), hora_salida=time(16, 30)
        )

        r = client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31")

        assert r.status_code == 200
        resumen = r.json()[0]
        assert resumen["dias_trabajados"] == 2
        assert Decimal(str(resumen["total_horas"])) == Decimal("17.50")

    def test_solo_cuenta_los_dias_del_rango(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(db, eduardo, fecha=date(2026, 7, 15))
        crear_registro_asistencia(db, eduardo, fecha=date(2026, 8, 15))

        r = client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31")

        assert r.json()[0]["dias_trabajados"] == 1

    def test_los_bordes_del_rango_entran(self, client, db):
        eduardo = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(db, eduardo, fecha=date(2026, 7, 1))
        crear_registro_asistencia(db, eduardo, fecha=date(2026, 7, 31))

        r = client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31")

        assert r.json()[0]["dias_trabajados"] == 2

    def test_un_dia_a_medio_cargar_no_suma(self, client, db):
        # Entró y todavía no se anotó la salida: no aporta horas, así que
        # tampoco cuenta como día trabajado.
        eduardo = crear_empleado(db, nombre="Eduardo")
        crear_registro_asistencia(
            db, eduardo, fecha=date(2026, 7, 1), hora_entrada=time(8, 0), hora_salida=None
        )

        assert client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31").json() == []

    def test_un_empleado_dado_de_baja_sigue_apareciendo(self, client, db):
        # Se fue en agosto, pero las horas que hizo en julio son suyas.
        diego = crear_empleado(db, nombre="Diego", activo=False)
        crear_registro_asistencia(db, diego, fecha=date(2026, 7, 10))

        r = client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31")

        assert r.json()[0]["nombre"] == "Diego"

    def test_un_periodo_sin_nada_devuelve_lista_vacia(self, client, db):
        crear_empleado(db, nombre="Eduardo")

        assert client.get("/api/asistencia/resumen?desde=2026-07-01&hasta=2026-07-31").json() == []

    def test_rechaza_un_rango_al_reves(self, client, db):
        r = client.get("/api/asistencia/resumen?desde=2026-07-31&hasta=2026-07-01")

        assert r.status_code == 400
