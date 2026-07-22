import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from money import Money, Cantidad

# Estados por los que puede pasar un Trabajo. Única fuente de verdad: el router
# valida contra esta lista y el frontend arma el Kanban con estos mismos nombres.
ESTADOS_TRABAJO = ["Aprobado", "En Diseño", "En Producción", "Entregado", "Cancelado"]

# Estados por los que puede pasar un Cheque. Mismo criterio que ESTADOS_TRABAJO:
# única fuente de verdad, validada desde el schema para que un estado inventado
# no llegue nunca a la base. Las transiciones válidas entre ellos las define
# routers/cheques.py; esto sólo acota el universo de valores posibles.
ESTADOS_CHEQUE = ["En Cartera", "Depositado", "Cobrado", "Endosado", "Rechazado"]

# Estado con el que nace un cheque. Los demás se alcanzan por transición.
ESTADO_CHEQUE_INICIAL = "En Cartera"


def ahora_local():
    """Hora local del taller para los registros que se agrupan por día.

    El dashboard agrupa por fecha local: un pago cargado a las 22:00 fechado en
    UTC caía al día siguiente y, cerca de fin de mes, en el período equivocado.
    Consistente con gastos y cheques, que ya usan date.today().

    Ojo: HistorialStock e HistorialCheque siguen guardando UTC con timezone
    (son cronológicos, no contables). Mezclar unos con otros en Python lanza
    TypeError: unificarlos es una migración aparte.
    """
    return datetime.now()

class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    nombre_completo = Column(String, nullable=False)
    nombre_empresa = Column(String, nullable=True)
    dni_cuit = Column(String, index=True, nullable=False)
    telefono = Column(String, nullable=False)
    frecuencia_recompra_dias = Column(Integer, nullable=True)

    trabajos = relationship("Trabajo", back_populates="cliente")
    pagos = relationship("Movimiento", back_populates="cliente")

class Trabajo(Base):
    __tablename__ = "trabajos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    descripcion_producto = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    estado = Column(String, default="Aprobado")
    fecha_creacion = Column(Date, nullable=False)
    fecha_comienzo = Column(Date, nullable=True)
    fecha_entrega = Column(Date, nullable=True)
    precio_venta = Column(Money, nullable=False)
    costo_total_materiales = Column(Money, nullable=False)
    forma_pago_heredada = Column(String, nullable=True)
    notas_iniciales = Column(Text, nullable=True) # <-- Nota opcional al crear

    # --- Datos de la boleta física (orden de producción) ---
    # La "descripción" de la boleta es descripcion_producto, definido arriba.
    medida_terminado = Column(String, nullable=True)
    medida_pliego = Column(String, nullable=True)
    corte_pliego = Column(String, nullable=True)
    tintas = Column(String, nullable=True)
    troquelado = Column(String, nullable=True)
    barniz = Column(String, nullable=True)
    otros = Column(Text, nullable=True)

    # El papel se guarda dos veces a propósito y no es duplicación:
    # - papel_tipo es lo que se lee en la boleta (texto libre).
    # - papel_id es opcional y sólo existe para saber QUÉ descontar del stock.
    # Si el papel lo trae el cliente o se compra en el momento, hay texto sin FK
    # y al imprimir la orden no se descuenta nada.
    papel_tipo = Column(String, nullable=True)
    papel_id = Column(String, ForeignKey("stock.id"), nullable=True)
    cantidad_pliegos = Column(Cantidad, nullable=True) # consumo de papel (cantidad = unidades terminadas)

    # --- Emisión de la orden ---
    # orden_impresa es el guard de idempotencia: el stock se descuenta una sola
    # vez, cuando pasa de False a True. Reimprimir sólo regenera el PDF.
    orden_impresa = Column(Boolean, default=False)
    numero_orden = Column(String, index=True, nullable=True) # se asigna recién al imprimir
    fecha_orden_impresa = Column(DateTime, nullable=True)

    # Espejo de orden_impresa para el camino inverso: al cancelar un trabajo se
    # ofrece devolver los pliegos al stock, y este flag garantiza que el
    # reingreso pase una sola vez aunque se cancele y reactive varias veces.
    papel_devuelto = Column(Boolean, default=False)

    cliente = relationship("Cliente", back_populates="trabajos")
    notas = relationship("Nota", back_populates="trabajo")
    papel = relationship("ArticuloStock")

class Movimiento(Base):
    __tablename__ = "movimientos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)
    fecha = Column(DateTime, default=ahora_local)
    monto = Column(Money, nullable=False)
    tipo = Column(String, nullable=False) # 'Pago', 'Edición', 'Ajuste'
    metodo = Column(String, nullable=True) # Ej: 'Efectivo', 'Transferencia'
    descripcion = Column(String, nullable=False) # Ej: "Pago parcial factura X" o "Edición de cantidad"

    cliente = relationship("Cliente", back_populates="pagos")

class Nota(Base):
    __tablename__ = "notas"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)
    texto = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=ahora_local)

    trabajo = relationship("Trabajo", back_populates="notas")

class Presupuesto(Base):
    """Cabecera de un presupuesto. El detalle (uno o varios productos) vive en
    ItemPresupuesto: un presupuesto real de la gráfica lleva varios trabajos en
    el mismo comprobante (ej: bolsas + cajas + papel antigrasa).

    Los datos de cada producto (descripción, cantidad, precio, papel, costos)
    se movieron al ítem. Acá quedan sólo los datos de cabecera comunes a todo el
    presupuesto: cliente, número, estado, fecha y el historial de versiones.
    """
    __tablename__ = "presupuestos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # Opcional: un presupuesto se puede guardar como borrador sin cliente asignado
    # todavía. Se le carga el cliente más adelante, antes de convertirlo a trabajo.
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=True)
    version_de = Column(String, ForeignKey("presupuestos.id"), nullable=True) # Para el historial de duplicados
    numero_secuencia = Column(String, index=True, nullable=True) # Ej: "0001-000015" (número de comprobante)
    # Estado de cabecera. Con varios ítems convertidos a varios trabajos es
    # informativo ("mejor esfuerzo"): la verdad productiva vive en cada Trabajo.
    estado = Column(String, default="Borrador")
    convertido_a_trabajo = Column(Boolean, default=False)
    fecha_creacion = Column(Date, nullable=False)

    cliente = relationship("Cliente")
    # cascade delete-orphan: borrar el presupuesto (sólo si no está convertido y
    # no tiene versiones) borra sus ítems; reemplazar la lista en un PUT limpia
    # los huérfanos. Un ítem de un presupuesto no convertido es un borrador, no
    # un movimiento histórico.
    items = relationship(
        "ItemPresupuesto",
        back_populates="presupuesto",
        cascade="all, delete-orphan",
        order_by="ItemPresupuesto.orden",
    )


class ItemPresupuesto(Base):
    """Un producto dentro de un presupuesto. Al convertir el presupuesto, cada
    ítem se vuelve un Trabajo propio (uno se produce por separado del otro).

    El precio que ve el cliente es precio_unitario, que tipea el usuario; el
    total del ítem es cantidad * precio_unitario y el del presupuesto la suma de
    sus ítems. Los costos internos (detalles_costos) y el margen son opcionales:
    sólo alimentan la hoja de costos interna y el cálculo de ganancia, no el
    precio de venta.
    """
    __tablename__ = "items_presupuesto"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    presupuesto_id = Column(String, ForeignKey("presupuestos.id"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)  # posición en el comprobante

    # Lo que ve el cliente:
    descripcion = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Money, nullable=False)

    # Costos internos OPCIONALES (hoja de costos y ganancia). costo_materiales se
    # deriva de detalles_costos; el margen queda a título informativo.
    detalles_costos = Column(JSON, nullable=True)
    costo_materiales = Column(Money, nullable=True)
    margen_ganancia = Column(Money, nullable=True)

    # El papel se guarda dos veces, mismo criterio que en Trabajo:
    # - material/gramaje son texto libre y es lo que se lee en el presupuesto.
    # - papel_id es opcional y sólo existe para saber QUÉ descontar del stock.
    # El trabajo que nace de este ítem lo hereda al convertirse; sin esto la
    # orden de producción nunca descontaría papel.
    material = Column(String, nullable=True)
    gramaje = Column(String, nullable=True)
    papel_id = Column(String, ForeignKey("stock.id"), nullable=True)
    cantidad_pliegos = Column(Cantidad, nullable=True)

    # Trabajo generado al convertir ESTE ítem (1 ítem -> 1 trabajo). Reemplaza al
    # viejo Presupuesto.trabajo_id: el vínculo presupuesto<->trabajo es por ítem.
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)

    presupuesto = relationship("Presupuesto", back_populates="items")
    papel = relationship("ArticuloStock")

class Gasto(Base):
    __tablename__ = "gastos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True) # <-- ESTO ES LO NUEVO
    categoria = Column(String, nullable=False)
    concepto = Column(String, nullable=False)
    monto = Column(Money, nullable=False)
    fecha = Column(Date, nullable=False)
    metodo_pago = Column(String, default="Efectivo")     # <-- NUEVO
    comprobante = Column(String, default="Sin comprobante") # <-- NUEVO
    # Quién autorizó/hizo el gasto. 'General' es el gasto del taller sin dueño puntual.
    responsable = Column(String, default="General")

class ArticuloStock(Base):
    __tablename__ = "stock"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String, nullable=False)
    categoria = Column(String, default="General")
    proveedor = Column(String, nullable=True)
    cantidad = Column(Cantidad, default=0)
    unidad = Column(String, default="unidades")
    stock_minimo = Column(Cantidad, default=5)
    costo_unitario = Column(Money, default=0)
    ultima_actualizacion = Column(Date, nullable=False)
    # Dimensiones del papel (sólo papeles comprados por peso): permiten
    # recalcular pliegos en recompras sin volver a tipear los datos.
    largo_cm = Column(Cantidad, nullable=True)
    ancho_cm = Column(Cantidad, nullable=True)
    gramaje_grs = Column(Cantidad, nullable=True)

class HistorialStock(Base):
    __tablename__ = "historial_stock"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    articulo_id = Column(String, ForeignKey("stock.id"), nullable=False)
    diferencia = Column(Cantidad, nullable=False) # Guardaremos +50 o -200
    motivo = Column(String, nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc)) # Para saber hasta la hora

class Cheque(Base):
    __tablename__ = "cheques"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=True)
    # Recibido: cheque de un cliente (entra plata al cobrarse).
    # Emitido: cheque propio para pagarle a un proveedor (sale plata).
    clasificacion = Column(String, default="Recibido")
    # Opcional: trabajo al que se imputa el cobro de un cheque Recibido. Permite
    # calcular la ganancia proporcional cuando el cheque se marca 'Cobrado'.
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)
    banco = Column(String, nullable=False)
    numero = Column(String, nullable=False)
    monto = Column(Money, nullable=False)
    fecha_emision = Column(Date, nullable=False)
    fecha_cobro = Column(Date, nullable=False)
    estado = Column(String, default="En Cartera") # En Cartera, Depositado, Cobrado, Endosado, Rechazado
    destinatario_endoso = Column(String, nullable=True)
    # Fecha en la que el cheque se endosó. Endosar equivale a cobrar (el dinero
    # realiza la ganancia del trabajo) y a la vez pagar: por eso los cálculos la
    # usan igual que fecha_cobro. Se completa al pasar el cheque a 'Endosado'.
    fecha_endoso = Column(Date, nullable=True)

class HistorialCheque(Base):
    __tablename__ = "historial_cheques"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cheque_id = Column(String, ForeignKey("cheques.id"), nullable=False)
    estado_anterior = Column(String, nullable=True)
    estado_nuevo = Column(String, nullable=True)
    detalle = Column(String, nullable=False) # Ej: "monto 5000 -> 6000" o el motivo de una reversión
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))