from pydantic import BaseModel, computed_field, field_validator, model_validator
from typing import Optional
from datetime import date
from decimal import Decimal

from money import Q2
from .comun import _validar_detalles_costos, _validar_margen, _validar_monto_no_negativo

# --- ESQUEMAS PARA PRESUPUESTOS ---
# Un presupuesto tiene UNO O VARIOS ítems (productos). Cada ítem lleva su precio
# unitario, que es lo que ve el cliente; los costos y el margen son opcionales y
# sólo alimentan la hoja de costos interna y el cálculo de ganancia.
class ItemPresupuestoBase(BaseModel):
    descripcion: str
    cantidad: int
    precio_unitario: Decimal
    # Costos internos opcionales. costo_materiales lo deriva el backend de
    # detalles_costos; el margen queda a título informativo.
    detalles_costos: Optional[dict] = None
    margen_ganancia: Optional[Decimal] = None
    # Papel del ítem: material/gramaje es el texto del presupuesto; papel_id +
    # cantidad_pliegos son para descontar del stock. El trabajo lo hereda.
    material: Optional[str] = None
    gramaje: Optional[str] = None
    papel_id: Optional[str] = None
    cantidad_pliegos: Optional[Decimal] = None
    orden: int = 0

    _costos_validos = field_validator("detalles_costos")(_validar_detalles_costos)
    _margen_valido = field_validator("margen_ganancia")(_validar_margen)
    _precio_valido = field_validator("precio_unitario")(_validar_monto_no_negativo)


class ItemPresupuestoCreate(ItemPresupuestoBase):
    pass


class ItemPresupuestoResponse(ItemPresupuestoBase):
    id: str
    costo_materiales: Optional[Decimal] = None
    trabajo_id: Optional[str] = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def total(self) -> Decimal:
        """Total del ítem = cantidad * precio_unitario (no se persiste)."""
        return Q2(self.cantidad * self.precio_unitario)


class PresupuestoBase(BaseModel):
    # Opcional: permite guardar un borrador sin cliente asignado todavía.
    cliente_id: Optional[str] = None
    # Si viene, asocia el presupuesto (de UN solo ítem) a un trabajo ya creado
    # que todavía no tenía presupuesto. Reemplaza al viejo trabajo_id de cabecera.
    trabajo_asociado_id: Optional[str] = None
    version_de: Optional[str] = None
    numero_secuencia: Optional[str] = None
    estado: Optional[str] = "Borrador"
    convertido_a_trabajo: Optional[bool] = False
    fecha_creacion: date


class PresupuestoCreate(PresupuestoBase):
    items: list[ItemPresupuestoCreate]

    @model_validator(mode="after")
    def _al_menos_un_item(self):
        if not self.items:
            raise ValueError("El presupuesto tiene que tener al menos un ítem.")
        return self


class PresupuestoResponse(PresupuestoBase):
    id: str
    items: list[ItemPresupuestoResponse]
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def total(self) -> Decimal:
        """Total del presupuesto = suma de los totales de sus ítems."""
        return Q2(sum((i.total for i in self.items), Decimal("0")))


# Esquema para EDITAR un presupuesto existente (no se permite tocar
# convertido_a_trabajo acá). Si viene 'items', reemplaza toda la lista.
class PresupuestoUpdate(BaseModel):
    cliente_id: Optional[str] = None
    estado: Optional[str] = None
    items: Optional[list[ItemPresupuestoCreate]] = None
