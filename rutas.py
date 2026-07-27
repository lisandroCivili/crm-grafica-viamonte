"""Resolución de rutas del proyecto, en un solo lugar.

Empaquetado con PyInstaller (--onefile) conviven DOS carpetas distintas, y
confundirlas es un bug silencioso:

- El .exe corre desde sys.executable, y al lado de él persiste viamonte.db: es la
  única carpeta escribible entre ejecuciones. La expone DIR_DATOS.
- Los archivos agregados con datas=[('frontend','frontend')] se extraen a una
  carpeta temporal (sys._MEIPASS) que se borra al cerrar el programa: son de sólo
  lectura (el frontend servido, el logo y la firma de los PDF) y se resuelven con
  ruta_recurso().

En desarrollo (`python main.py`) las dos son la carpeta del proyecto.

Antes este mismo bloque estaba duplicado en database.py, main.py, orden_pdf.py y
presupuesto_pdf.py, con dos nombres para el mismo concepto. Acá vive una vez.
"""
import os
import sys

if getattr(sys, "frozen", False):
    # Empaquetado: la base persiste junto al .exe; los assets salen del bundle.
    DIR_DATOS = os.path.dirname(sys.executable)
    _DIR_RECURSOS = sys._MEIPASS
else:
    # Desarrollo: ambos son la carpeta del proyecto (donde vive este archivo).
    DIR_DATOS = os.path.dirname(os.path.abspath(__file__))
    _DIR_RECURSOS = DIR_DATOS


def ruta_recurso(*partes: str) -> str:
    """Ruta de un recurso empaquetado (sólo lectura): el frontend, los assets…"""
    return os.path.join(_DIR_RECURSOS, *partes)
