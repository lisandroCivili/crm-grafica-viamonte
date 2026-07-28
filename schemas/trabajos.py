from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from .comun import _validar_monto_no_negativo

# --- ESQUEMAS PARA TRABAJOS ---
class TrabajoBase(BaseModel):
    cliente_id: str
    # El alta de trabajo ya no exige descripción, cantidad de unidades, costo de
    # materiales ni forma de pago desde el formulario: el trabajo se cuenta por
    # pliegos y esos datos pasaron a ser opcionales. Se mantienen las columnas
    # (NOT NULL en el modelo) con defaults para no romper filas ni la creación
    # desde otros orígenes (p. ej. conversión de presupuesto, que sí los manda).
    descripcion_producto: str = ""
    cantidad: int = 1
    estado: Optional[str] = "Aprobado"
    fecha_creacion: date
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None
    precio_venta: Decimal
    costo_total_materiales: Decimal = Decimal("0")
    forma_pago_heredada: Optional[str] = None
    # La columna existía en el modelo pero no en el schema, así que lo que
    # mandaba el drawer de alta lo descartaba Pydantic en silencio.
    notas_iniciales: Optional[str] = None

    # Datos de la boleta física. Todos opcionales: un trabajo se puede dar de
    # alta sin la parte productiva y completarla después.
    medida_terminado: Optional[str] = None
    medida_pliego: Optional[str] = None
    corte_pliego: Optional[str] = None
    tintas: Optional[str] = None
    troquelado: Optional[str] = None
    barniz: Optional[str] = None
    otros: Optional[str] = None
    papel_tipo: Optional[str] = None
    papel_id: Optional[str] = None
    cantidad_pliegos: Optional[Decimal] = None

    _montos_validos = field_validator("precio_venta", "costo_total_materiales")(
        _validar_monto_no_negativo
    )

class TrabajoCreate(TrabajoBase):
    pass

class TrabajoUpdate(BaseModel):
    estado: Optional[str] = None
    fecha_comienzo: Optional[date] = None
    fecha_entrega: Optional[date] = None
    descripcion_producto: Optional[str] = None
    cantidad: Optional[int] = None
    precio_venta: Optional[Decimal] = None
    medida_terminado: Optional[str] = None
    medida_pliego: Optional[str] = None
    corte_pliego: Optional[str] = None
    tintas: Optional[str] = None
    troquelado: Optional[str] = None
    barniz: Optional[str] = None
    otros: Optional[str] = None
    papel_tipo: Optional[str] = None
    papel_id: Optional[str] = None
    cantidad_pliegos: Optional[Decimal] = None
    notas_iniciales: Optional[str] = None

    _monto_valido = field_validator("precio_venta")(_validar_monto_no_negativo)

class TrabajoResponse(TrabajoBase):
    id: str
    # Campos de solo lectura: los controla el backend al imprimir la orden o al
    # cancelarla, por eso no están en TrabajoBase (nadie los manda desde afuera).
    orden_impresa: bool = False
    numero_orden: Optional[str] = None
    fecha_orden_impresa: Optional[datetime] = None
    papel_devuelto: bool = False
    remito_impreso: bool = False
    numero_remito: Optional[str] = None
    fecha_remito_impreso: Optional[datetime] = None
    model_config = {"from_attributes": True}

# Datos que se piden al pasar un trabajo de Aprobado a En Diseño.
class IniciarDisenoRequest(BaseModel):
    monto: Decimal
    metodo: Optional[str] = None
    motivo: Optional[str] = None
    # Sólo cuando la seña se abona con cheque: se crea un Cheque recibido en vez
    # de un Movimiento (no cuenta como ingreso hasta cobrarse).
    banco: Optional[str] = None
    numero: Optional[str] = None
    fecha_cobro: Optional[date] = None

    @model_validator(mode="after")
    def validar_monto_y_motivo(self):
        if self.monto < Decimal("0"):
            raise ValueError("El monto abonado no puede ser negativo.")
        # Se puede arrancar el diseño sin seña, pero hay que justificar por qué.
        if self.monto == Decimal("0") and not (self.motivo or "").strip():
            raise ValueError("Si no hay monto abonado, el motivo es obligatorio.")
        # Si la seña es con cheque, necesitamos los datos mínimos del cheque.
        if self.monto > Decimal("0") and (self.metodo or "") == "Cheque":
            faltan = [c for c in ("banco", "numero", "fecha_cobro") if not getattr(self, c)]
            if faltan:
                raise ValueError(f"Para una seña con cheque faltan datos: {', '.join(faltan)}.")
        return self


# Resultado de aplicar el saldo a favor del cliente a un trabajo. No lleva request:
# el monto lo determina el backend (mínimo entre lo que falta del trabajo y el
# crédito disponible del cliente). Ver routers/trabajos.py._aplicar_saldo_favor.
class AplicarSaldoFavorResponse(BaseModel):
    monto_aplicado: Decimal
    saldo_pendiente_restante: Decimal
