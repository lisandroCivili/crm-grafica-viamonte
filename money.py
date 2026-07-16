"""
Tipo de dato y helpers para manejar dinero con exactitud.

Todo el dinero del CRM se representa como Decimal (nunca float) para evitar
errores de redondeo del punto flotante IEEE-754 (ej: 0.1 + 0.2 == 0.30000000000000004).

SQLite no tiene un tipo DECIMAL nativo (guarda REAL/float), así que usamos un
TypeDecorator que persiste el valor como TEXT y lo devuelve como Decimal ya
cuantizado a 2 decimales. De esta forma el error de float nunca se guarda en disco.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

# Cantidad de dinero: siempre 2 decimales.
DOS_DECIMALES = Decimal("0.01")

# Cantidades de stock: permitimos más precisión (ej: 1.5 resmas, 0.250 kg).
TRES_DECIMALES = Decimal("0.001")


def Q2(valor: Union[Decimal, int, float, str, None]) -> Optional[Decimal]:
    """Redondea un valor a 2 decimales (dinero) usando ROUND_HALF_UP.

    Acepta str/int/Decimal directamente. Si recibe un float lo pasa por str()
    primero para no arrastrar la basura binaria del float. Devuelve None si
    el valor es None.
    """
    if valor is None:
        return None
    if isinstance(valor, float):
        valor = str(valor)
    return Decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def Q3(valor: Union[Decimal, int, float, str, None]) -> Optional[Decimal]:
    """Redondea un valor a 3 decimales (cantidades de stock)."""
    if valor is None:
        return None
    if isinstance(valor, float):
        valor = str(valor)
    return Decimal(valor).quantize(TRES_DECIMALES, rounding=ROUND_HALF_UP)


class Money(TypeDecorator):
    """Columna de dinero: Decimal <-> TEXT en SQLite, cuantizado a 2 decimales."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # Python -> DB
        if value is None:
            return None
        return str(Q2(value))

    def process_result_value(self, value, dialect):
        # DB -> Python
        if value is None:
            return None
        return Q2(value)


class Cantidad(TypeDecorator):
    """Columna de cantidad de stock: Decimal <-> TEXT, cuantizado a 3 decimales."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(Q3(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Q3(value)
