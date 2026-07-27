"""Armado de los PDF del taller (orden de producción y presupuesto).

Reemplaza a los antiguos orden_pdf.py y presupuesto_pdf.py, que compartían
helpers duplicados (_texto idéntico, _ruta_logo/_ruta_asset gemelas). Ahora esos
helpers viven una vez en pdf/comun.py y cada comprobante en su módulo.

Se re-exportan las dos funciones públicas para que los routers sigan importando
`from pdf import construir_orden_pdf` sin saber en qué submódulo viven.
"""
from .orden import construir_orden_pdf
from .presupuesto import construir_presupuesto_pdf
