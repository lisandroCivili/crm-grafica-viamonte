"""Tests de los endpoints de archivos adjuntos (routers/trabajos.py:
subir_archivos, ver_archivo, borrar_archivo) y de su limpieza en disco al
borrar un trabajo.
"""
import pytest

import archivos as archivos_modulo
import models
from conftest import crear_cliente, crear_trabajo


@pytest.fixture(autouse=True)
def _uploads_en_carpeta_temporal(tmp_path, monkeypatch):
    """Aísla los archivos subidos en una carpeta temporal por test: sin esto,
    los tests escribirían de verdad en DIR_DATOS/uploads/trabajos del
    proyecto (mismo motivo por el que db_factory, en conftest.py, usa un
    sqlite en tmp_path en vez de viamonte.db).
    """
    monkeypatch.setattr(archivos_modulo, "DIR_DATOS", str(tmp_path))


def _jpg(nombre="foto.jpg", contenido=b"contenido-de-prueba"):
    return ("archivos", (nombre, contenido, "image/jpeg"))


def _pdf(nombre="arte.pdf", contenido=b"%PDF-1.4 contenido de prueba"):
    return ("archivos", (nombre, contenido, "application/pdf"))


def _carpeta_uploads(tmp_path):
    return tmp_path / "uploads" / "trabajos"


class TestSubirArchivos:
    def test_sube_una_imagen(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])

        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 1
        assert body[0]["nombre_original"] == "foto.jpg"
        assert body[0]["content_type"] == "image/jpeg"
        assert (
            db.query(models.ArchivoTrabajo)
            .filter(models.ArchivoTrabajo.trabajo_id == trabajo.id)
            .count() == 1
        )

    def test_sube_varios_de_una_misma_tanda(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg(), _pdf()])

        assert r.status_code == 200
        assert len(r.json()) == 2
        assert (
            db.query(models.ArchivoTrabajo)
            .filter(models.ArchivoTrabajo.trabajo_id == trabajo.id)
            .count() == 2
        )

    def test_rechaza_un_tipo_no_permitido(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(
            f"/api/trabajos/{trabajo.id}/archivos",
            files=[("archivos", ("virus.exe", b"MZ...", "application/octet-stream"))],
        )

        assert r.status_code == 400
        assert "no permitido" in r.json()["detail"].lower()
        assert db.query(models.ArchivoTrabajo).count() == 0

    def test_rechaza_content_type_que_no_coincide_con_la_extension(self, client, db):
        # Un .exe renombrado a .pdf pasaría la validación de extensión sola;
        # el content-type que manda el navegador es lo que lo delata.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(
            f"/api/trabajos/{trabajo.id}/archivos",
            files=[("archivos", ("falso.pdf", b"MZ...", "application/octet-stream"))],
        )

        assert r.status_code == 400
        assert db.query(models.ArchivoTrabajo).count() == 0

    def test_rechaza_archivo_mas_grande_que_el_limite(self, client, db, monkeypatch):
        # Se baja el límite en vez de generar 15MB reales: lo que se prueba es
        # la regla, no el valor exacto configurado.
        monkeypatch.setattr(archivos_modulo, "TAMANO_MAXIMO_BYTES", 10)
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg(contenido=b"x" * 100)])

        assert r.status_code == 400
        assert "MB" in r.json()["detail"]

    def test_si_un_archivo_de_la_tanda_es_invalido_no_se_guarda_ninguno(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.post(
            f"/api/trabajos/{trabajo.id}/archivos",
            files=[_jpg(), ("archivos", ("virus.exe", b"MZ", "application/octet-stream"))],
        )

        assert r.status_code == 400
        assert db.query(models.ArchivoTrabajo).count() == 0

    def test_trabajo_inexistente_da_404(self, client, db):
        r = client.post("/api/trabajos/no-existe/archivos", files=[_jpg()])
        assert r.status_code == 404

    def test_el_archivo_queda_en_disco(self, client, db, tmp_path):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])

        assert len(list(_carpeta_uploads(tmp_path).iterdir())) == 1


class TestVerArchivo:
    def test_devuelve_el_contenido_subido(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg(contenido=b"bytes-originales")])
        archivo = db.query(models.ArchivoTrabajo).filter(models.ArchivoTrabajo.trabajo_id == trabajo.id).first()

        r = client.get(f"/api/trabajos/{trabajo.id}/archivos/{archivo.id}")

        assert r.status_code == 200
        assert r.content == b"bytes-originales"
        assert r.headers["content-type"].startswith("image/jpeg")

    def test_archivo_inexistente_da_404(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)

        r = client.get(f"/api/trabajos/{trabajo.id}/archivos/no-existe")

        assert r.status_code == 404

    def test_archivo_de_otro_trabajo_da_404(self, client, db):
        # El archivo existe, pero no bajo ESTE trabajo_id: no se puede
        # servir cruzando la URL de un trabajo con el id de un archivo ajeno.
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        otro = crear_trabajo(db, cliente, descripcion_producto="Otro")
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])
        archivo = db.query(models.ArchivoTrabajo).filter(models.ArchivoTrabajo.trabajo_id == trabajo.id).first()

        r = client.get(f"/api/trabajos/{otro.id}/archivos/{archivo.id}")

        assert r.status_code == 404


class TestBorrarArchivo:
    def test_borra_la_fila_y_el_archivo_fisico(self, client, db, tmp_path):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])
        archivo = db.query(models.ArchivoTrabajo).filter(models.ArchivoTrabajo.trabajo_id == trabajo.id).first()

        r = client.delete(f"/api/trabajos/{trabajo.id}/archivos/{archivo.id}")

        assert r.status_code == 200
        assert db.query(models.ArchivoTrabajo).filter(models.ArchivoTrabajo.id == archivo.id).first() is None
        assert list(_carpeta_uploads(tmp_path).iterdir()) == []

    def test_borrar_de_nuevo_da_404(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])
        archivo = db.query(models.ArchivoTrabajo).filter(models.ArchivoTrabajo.trabajo_id == trabajo.id).first()
        client.delete(f"/api/trabajos/{trabajo.id}/archivos/{archivo.id}")

        r = client.delete(f"/api/trabajos/{trabajo.id}/archivos/{archivo.id}")

        assert r.status_code == 404


class TestEliminarTrabajoConArchivos:
    def test_borra_tambien_los_archivos_fisicos(self, client, db, tmp_path):
        # cascade="all, delete-orphan" en Trabajo.archivos borra las FILAS
        # solas; lo que se prueba acá es que el DELETE del trabajo también
        # limpia el disco (ver el loop agregado en eliminar_trabajo).
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg(), _pdf()])

        r = client.delete(f"/api/trabajos/{trabajo.id}")

        assert r.status_code == 200
        assert list(_carpeta_uploads(tmp_path).iterdir()) == []
        assert (
            db.query(models.ArchivoTrabajo)
            .filter(models.ArchivoTrabajo.trabajo_id == trabajo.id)
            .count() == 0
        )


class TestListarTrabajosIncluyeArchivos:
    def test_get_trabajos_trae_la_lista_de_archivos(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente)
        client.post(f"/api/trabajos/{trabajo.id}/archivos", files=[_jpg()])

        r = client.get("/api/trabajos/")

        assert r.status_code == 200
        encontrado = next(t for t in r.json() if t["id"] == trabajo.id)
        assert len(encontrado["archivos"]) == 1
        assert encontrado["archivos"][0]["nombre_original"] == "foto.jpg"
