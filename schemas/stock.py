from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# --- ESQUEMAS PARA STOCK ---
class StockBase(BaseModel):
    nombre: str
    categoria: Optional[str] = "General"
    proveedor: Optional[str] = None
    cantidad: Decimal
    unidad: str
    stock_minimo: Decimal
    costo_unitario: Decimal
    ultima_actualizacion: date
    largo_cm: Optional[Decimal] = None
    ancho_cm: Optional[Decimal] = None
    gramaje_grs: Optional[Decimal] = None

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    proveedor: Optional[str] = None
    unidad: Optional[str] = None
    stock_minimo: Optional[Decimal] = None
    cantidad: Optional[Decimal] = None
    costo_unitario: Optional[Decimal] = None
    ultima_actualizacion: Optional[date] = None
    largo_cm: Optional[Decimal] = None
    ancho_cm: Optional[Decimal] = None
    gramaje_grs: Optional[Decimal] = None
    motivo: Optional[str] = "Ajuste rápido"

class CompraStockItem(BaseModel):
    """Ítem del carrito de compras de stock.

    Con articulo_id es una recompra (suma cantidad al artículo existente);
    sin articulo_id es un alta nueva. Si unidad == 'Kg' el backend convierte
    el peso a pliegos usando largo/ancho/gramaje (ver routers/stock.py).
    """
    articulo_id: Optional[str] = None
    nombre: Optional[str] = None
    categoria: Optional[str] = "General"
    proveedor: Optional[str] = None
    unidad: Optional[str] = None
    cantidad: Optional[Decimal] = None
    stock_minimo: Optional[Decimal] = None
    costo_unitario: Optional[Decimal] = None
    costo_total: Optional[Decimal] = None
    largo_cm: Optional[Decimal] = None
    ancho_cm: Optional[Decimal] = None
    gramaje_grs: Optional[Decimal] = None
    peso_total_kg: Optional[Decimal] = None

class StockResponse(StockBase):
    id: str
    model_config = {"from_attributes": True}

class HistorialStockResponse(BaseModel):
    id: str
    articulo_id: str
    diferencia: Decimal
    motivo: str
    fecha: datetime
    model_config = {"from_attributes": True}
