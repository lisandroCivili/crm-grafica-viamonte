"""Helpers compartidos por los dos PDF del taller (orden y presupuesto).

Antes cada módulo tenía su propia copia de _texto() (idéntica) y su propia
función de ruta de assets con distinto nombre (_ruta_logo / _ruta_asset). Acá
viven una sola vez.
"""
import os
from decimal import Decimal

from rutas import ruta_recurso


def texto(valor):
    """Normaliza un valor para imprimirlo: None y vacío se muestran como '-'."""
    if valor is None:
        return "-"
    t = str(valor).strip()
    return t if t else "-"


def ruta_asset(nombre):
    """Ruta de un asset de frontend/assets/, o None si no existe.

    Empaquetado con PyInstaller los assets se extraen a una carpeta temporal; en
    desarrollo se usa la carpeta del proyecto. Todo eso lo resuelve rutas.py.
    """
    ruta = ruta_recurso("frontend", "assets", nombre)
    return ruta if os.path.exists(ruta) else None


def pesos(valor):
    """Formatea un monto al estilo argentino: 1.890.000 o 1.890.500,50.

    Igual criterio que fmtMoney del frontend, pero omite los decimales cuando
    son cero, que es como se ve el PDF de referencia (precios enteros). Sin
    símbolo $: cada lugar decide si lo antepone.
    """
    numero = Decimal(valor or 0)
    entero = int(numero)
    centavos = int((abs(numero) - abs(entero)) * 100)
    miles = f"{entero:,}".replace(",", ".")
    return miles if centavos == 0 else f"{miles},{centavos:02d}"
