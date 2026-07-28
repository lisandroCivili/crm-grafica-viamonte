"""Resolución de rutas del proyecto, en un solo lugar.

Conviven DOS carpetas distintas, y confundirlas es un bug silencioso:

- DIR_DATOS es la carpeta ESCRIBIBLE, donde persiste viamonte.db entre
  ejecuciones. Dónde queda depende de cómo esté corriendo el sistema (ver abajo).
- _DIR_RECURSOS es de SÓLO LECTURA: el frontend servido, el logo y la firma de
  los PDF, el manual. Se resuelve con ruta_recurso().

Los tres escenarios:

1. Servidor (Railway y cualquier hosting): el disco del contenedor se rehace en
   cada deploy, así que la base TIENE que escribirse en un volumen montado
   aparte o se pierde todo lo cargado.
2. Empaquetado con PyInstaller (--onefile): el .exe corre desde sys.executable y
   al lado de él persiste la base. Los archivos agregados con
   datas=[('frontend','frontend')] se extraen a una carpeta temporal
   (sys._MEIPASS) que se borra al cerrar el programa.
3. Desarrollo (`python main.py`): las dos son la carpeta del proyecto.

Antes este mismo bloque estaba duplicado en database.py, main.py, orden_pdf.py y
presupuesto_pdf.py, con dos nombres para el mismo concepto. Acá vive una vez.
"""
import os
import sys

# Railway inyecta RAILWAY_VOLUME_MOUNT_PATH solo cuando hay un volumen montado,
# así que en el servidor esto funciona sin configurar nada a mano. DIR_DATOS
# queda como override manual para cualquier otro hosting. En la compu del taller
# ninguna de las dos existe y todo sigue como siempre.
_DIR_MONTADO = os.getenv("DIR_DATOS") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

if _DIR_MONTADO:
    # Servidor: la base va al volumen; los recursos, a la copia del repo.
    DIR_DATOS = _DIR_MONTADO
    _DIR_RECURSOS = os.path.dirname(os.path.abspath(__file__))
elif getattr(sys, "frozen", False):
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
