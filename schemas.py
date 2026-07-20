from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# --- ESQUEMAS PARA CLIENTES ---

class ClienteBase(BaseModel):
    nombre_completo: str
    nombre_empresa: Optional[str] = None
    dni_cuit: str
    telefono: str
    frecuencia_recompra_dias: Optional[int] = None

# Esquema para cuando recibimos los datos para CREAR un cliente
class ClienteCreate(ClienteBase):
    pass

# Esquema para cuando DEVOLVEMOS los datos del cliente hacia el front-end
class ClienteResponse(ClienteBase):
    id: str

    # Esto le dice a Pydantic que lea los datos directo desde los modelos de SQLAlchemy
    model_config = {"from_attributes": True}

# Esquema para EDITAR un cliente existente (todos los campos opcionales)
class ClienteUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    nombre_empresa: Optional[str] = None
    dni_cuit: Optional[str] = None
    telefono: Optional[str] = None
    frecuencia_recompra_dias: Optional[int] = None

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

class TrabajoResponse(TrabajoBase):
    id: str
    # Campos de solo lectura: los controla el backend al imprimir la orden o al
    # cancelarla, por eso no están en TrabajoBase (nadie los manda desde afuera).
    orden_impresa: bool = False
    numero_orden: Optional[str] = None
    fecha_orden_impresa: Optional[datetime] = None
    papel_devuelto: bool = False
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


# --- ESQUEMAS PARA PRESUPUESTOS ---
class PresupuestoBase(BaseModel):
    # Opcional: permite guardar un borrador sin cliente asignado todavía.
    cliente_id: Optional[str] = None
    trabajo_id: Optional[str] = None
    version_de: Optional[str] = None
    numero_secuencia: Optional[str] = None
    descripcion: str
    cantidad: int
    material: Optional[str] = None   # tipo de papel
    gramaje: Optional[str] = None    # g/m²
    costo_materiales: Decimal
    detalles_costos: Optional[dict] = None
    margen_ganancia: Decimal
    precio_final: Decimal
    estado: Optional[str] = "Borrador"
    convertido_a_trabajo: Optional[bool] = False
    fecha_creacion: date

class PresupuestoCreate(PresupuestoBase):
    # El backend recalcula costo_materiales y precio_final a partir de
    # detalles_costos y margen_ganancia, así que estos pueden venir en 0.
    # trabajo_id (heredado de PresupuestoBase) es opcional: si viene, asocia el
    # presupuesto a un trabajo ya creado que todavía no tenía presupuesto.
    costo_materiales: Decimal = Decimal("0")
    precio_final: Decimal = Decimal("0")

class PresupuestoResponse(PresupuestoBase):
    id: str
    model_config = {"from_attributes": True}

# Fila del "Informe general de trabajos a clientes". Se arma a partir de los
# presupuestos, cruzando el trabajo asociado (si ya se convirtió). Los campos
# vienen listos para renderizar en la tabla del PDF; "Pendiente"/"-"/"" según
# corresponda para los presupuestos que todavía no son trabajo.
class InformeTrabajoRow(BaseModel):
    nro_trabajo: str
    fecha_entrada: str
    cliente: str
    descripcion_material: str
    gramaje: str
    colores: str
    cantidad: int
    fecha_entrega: str
    dias_produccion: str
    estado: str
    cobrado: bool
    observaciones: str


# Esquema para EDITAR un presupuesto existente (no se permite tocar convertido_a_trabajo/trabajo_id acá)
class PresupuestoUpdate(BaseModel):
    cliente_id: Optional[str] = None
    descripcion: Optional[str] = None
    cantidad: Optional[int] = None
    material: Optional[str] = None
    gramaje: Optional[str] = None
    detalles_costos: Optional[dict] = None
    margen_ganancia: Optional[Decimal] = None
    estado: Optional[str] = None


# --- ESQUEMAS PARA MOVIMIENTOS ---
class MovimientoCreate(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    monto: Decimal
    tipo: str
    metodo: Optional[str] = None
    descripcion: str

class MovimientoResponse(MovimientoCreate):
    id: str
    fecha: datetime
    model_config = {"from_attributes": True}

# Esquema para EDITAR un movimiento existente (corrección de pagos mal cargados)
class MovimientoUpdate(BaseModel):
    trabajo_id: Optional[str] = None
    monto: Optional[Decimal] = None
    tipo: Optional[str] = None
    metodo: Optional[str] = None
    descripcion: Optional[str] = None


# --- ESQUEMAS PARA NOTAS ---
class NotaCreate(BaseModel):
    cliente_id: str
    trabajo_id: Optional[str] = None
    texto: str

class NotaResponse(NotaCreate):
    id: str
    fecha_creacion: datetime
    model_config = {"from_attributes": True}

# Esquema para EDITAR una nota existente
class NotaUpdate(BaseModel):
    texto: str


# --- ESQUEMAS PARA GASTOS ---
class GastoBase(BaseModel):
    categoria: str
    concepto: str
    monto: Decimal
    fecha: date
    metodo_pago: str = "Efectivo"
    comprobante: str = "Sin comprobante"
    responsable: str = "General"
    trabajo_id: Optional[str] = None

class GastoCreate(GastoBase):
    pass

class GastoResponse(GastoBase):
    id: str
    model_config = {"from_attributes": True}

# Esquema para EDITAR un gasto existente
class GastoUpdate(BaseModel):
    categoria: Optional[str] = None
    concepto: Optional[str] = None
    monto: Optional[Decimal] = None
    fecha: Optional[date] = None
    metodo_pago: Optional[str] = None
    comprobante: Optional[str] = None
    responsable: Optional[str] = None
    trabajo_id: Optional[str] = None


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


# --- ESQUEMAS PARA CHEQUES ---
class ChequeBase(BaseModel):
    cliente_id: Optional[str] = None
    clasificacion: str = "Recibido"   # 'Recibido' (de cliente) o 'Emitido' (a proveedor)
    trabajo_id: Optional[str] = None
    banco: str
    numero: str
    monto: Decimal
    fecha_emision: date
    fecha_cobro: date
    estado: str = "En Cartera"
    destinatario_endoso: Optional[str] = None
    fecha_endoso: Optional[date] = None

class ChequeCreate(ChequeBase):
    pass

class ChequeUpdate(BaseModel):
    cliente_id: Optional[str] = None
    clasificacion: Optional[str] = None
    trabajo_id: Optional[str] = None
    banco: Optional[str] = None
    numero: Optional[str] = None
    monto: Optional[Decimal] = None
    fecha_emision: Optional[date] = None
    fecha_cobro: Optional[date] = None
    estado: Optional[str] = None
    destinatario_endoso: Optional[str] = None
    fecha_endoso: Optional[date] = None
    # No es una columna del cheque: justifica revertir un estado final
    # (Cobrado / Endosado / Rechazado) y queda asentado en el historial.
    motivo: Optional[str] = None

class ChequeResponse(ChequeBase):
    id: str
    model_config = {"from_attributes": True}

class HistorialChequeResponse(BaseModel):
    id: str
    cheque_id: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    detalle: str
    fecha: datetime
    model_config = {"from_attributes": True}


# --- ESQUEMA PARA SALDO DE CLIENTE (calculado por el backend) ---
class SaldoResponse(BaseModel):
    cliente_id: str
    total_facturado: Decimal
    total_pagado: Decimal
    saldo: Decimal


# --- ESQUEMA PARA EL DASHBOARD (KPIs financieros calculados por el backend) ---
class MorosoResponse(BaseModel):
    trabajo_id: str
    descripcion_producto: str
    saldo_pendiente: Decimal


class DashboardResponse(BaseModel):
    # Plata realmente cobrada en el período (pagos no-cheque + cheques cobrados).
    ingresos: Decimal
    # Gastos del período: toda la plata que salió de la caja.
    egresos: Decimal
    # Parte de los egresos que NO resta de la ganancia porque su costo ya estaba
    # contemplado en el margen de un presupuesto. Se expone para poder explicar
    # en el dashboard por qué la ganancia no es ingresos - egresos.
    costos_presupuestados: Decimal = Decimal("0")
    # Suma de la ganancia proporcional a lo cobrado de cada trabajo con
    # presupuesto, menos los gastos del período que sí restan.
    ganancia_neta: Decimal
    # Conteos actuales (snapshot, no dependen del período).
    trabajos_pendientes: int
    trabajos_sin_presupuesto: int
    # Trabajos entregados del período con saldo sin cobrar (incluye cheques
    # recibidos no rechazados como pago, igual que el saldo de la ficha).
    plata_en_la_calle: Decimal = Decimal("0")
    morosos: list[MorosoResponse] = []
