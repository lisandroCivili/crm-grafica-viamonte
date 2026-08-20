"""Persistencia en disco de los archivos adjuntos a un Trabajo (arte, fotos,
PDFs). Vive en la raíz, al lado de papel.py y trabajos_comun.py.

Los archivos NO van a la base (sqlite crecería sin control y el backup de
main.py sólo copia viamonte.db) ni a _DIR_RECURSOS de rutas.py (esa carpeta es
de sólo lectura y no persiste empaquetada): van a DIR_DATOS/uploads/trabajos,
la misma carpeta escribible donde vive viamonte.db.
"""
import os
import uuid

from fastapi import HTTPException

from rutas import DIR_DATOS

# extensión -> content-types aceptados. Se valida por los DOS lados porque
# cada uno se puede falsear por separado: un .exe renombrado a .pdf pasa la
# validación de extensión sola, y un navegador puede mandar un content-type
# genérico para un archivo que sí es válido.
EXTENSIONES_A_CONTENT_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
    ".pdf": {"application/pdf"},
}

# 15 MB: cubre una foto de celular en alta resolución o un PDF de arte con
# imágenes incrustadas, sin dejar que un archivo enorme (por error o no) se
# coma el volumen de Railway.
TAMANO_MAXIMO_BYTES = 15 * 1024 * 1024

def _carpeta_uploads() -> str:
    # DIR_DATOS se lee del módulo (no de una constante precalculada al
    # importar) para que los tests puedan aislarlo con
    # monkeypatch.setattr(archivos, "DIR_DATOS", tmp_path), mismo criterio que
    # db_factory en tests/conftest.py aísla la base en un archivo temporal.
    carpeta = os.path.join(DIR_DATOS, "uploads", "trabajos")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def validar_tipo_archivo(nombre_original: str, content_type: str) -> str:
    """Extensión + content-type contra la whitelist. Devuelve la extensión (con
    punto, en minúsculas) si es válida; corta con 400 si no."""
    _, extension = os.path.splitext(nombre_original or "")
    extension = extension.lower()
    tipos_validos = EXTENSIONES_A_CONTENT_TYPES.get(extension)
    if not tipos_validos:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{nombre_original or 'archivo'}': tipo no permitido. "
                "Sólo se aceptan imágenes (jpg, jpeg, png, webp, gif) o PDF."
            ),
        )
    if content_type not in tipos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"'{nombre_original}': el contenido no coincide con un {extension}.",
        )
    return extension


def guardar_archivo_en_disco(contenido: bytes, extension: str, nombre_original: str) -> str:
    """Escribe el contenido con un nombre único (uuid4 + extensión, nunca el
    nombre original: riesgo de path traversal). Devuelve el nombre en disco."""
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"'{nombre_original}' pesa más de {TAMANO_MAXIMO_BYTES // (1024*1024)} MB.",
        )
    nombre_en_disco = f"{uuid.uuid4()}{extension}"
    with open(os.path.join(_carpeta_uploads(), nombre_en_disco), "wb") as f:
        f.write(contenido)
    return nombre_en_disco


def archivo_en_disco(nombre_archivo: str) -> str | None:
    """Ruta completa si el archivo existe en disco, None si no (para servirlo)."""
    ruta = os.path.join(_carpeta_uploads(), nombre_archivo)
    return ruta if os.path.exists(ruta) else None


def borrar_archivo_fisico(nombre_archivo: str) -> None:
    """Borra el archivo del disco. No rompe si ya no está: la base es la
    fuente de verdad de lo que existe, no el filesystem."""
    try:
        os.remove(os.path.join(_carpeta_uploads(), nombre_archivo))
    except FileNotFoundError:
        pass
