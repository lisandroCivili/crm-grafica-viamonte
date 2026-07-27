"""Helpers compartidos por los routers. No es una capa de servicios: es un lugar
para el pegamento que se repetía endpoint a endpoint.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session


def obtener_o_404(db: Session, modelo, id_, mensaje: str):
    """Trae una fila por su id o corta con un 404.

    Colapsa el patrón "query por id + if not + raise HTTPException(404)" que se
    repetía en casi todos los endpoints. El mensaje se pasa entero para conservar
    textual el que ya devolvía cada router ('Trabajo no encontrado', 'Cheque no
    encontrado'…): la API pública no cambia.
    """
    obj = db.query(modelo).filter(modelo.id == id_).first()
    if obj is None:
        raise HTTPException(status_code=404, detail=mensaje)
    return obj
