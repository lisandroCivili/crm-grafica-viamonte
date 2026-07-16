import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from money import Money, Cantidad

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

    cliente = relationship("Cliente", back_populates="trabajos")
    notas = relationship("Nota", back_populates="trabajo")

class Movimiento(Base):
    __tablename__ = "movimientos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    monto = Column(Money, nullable=False)
    tipo = Column(String, nullable=False) # 'Pago', 'Edición', 'Ajuste'
    metodo = Column(String, nullable=True) # Ej: 'Efectivo', 'Transferencia'
    descripcion = Column(String, nullable=False) # Ej: "Pago parcial factura X" o "Edición de cantidad"

    cliente = relationship("Cliente", back_populates="pagos")

class Nota(Base):
    __tablename__ = "notas"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False) # <--- AGREGAR ESTO
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True)
    texto = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    trabajo = relationship("Trabajo", back_populates="notas")

class Presupuesto(Base):
    __tablename__ = "presupuestos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True) # Para sincronizar estado
    version_de = Column(String, ForeignKey("presupuestos.id"), nullable=True) # Para el historial de duplicados
    numero_secuencia = Column(String, index=True, nullable=True) # Ej: "0001-000015" (número de comprobante)
    descripcion = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    costo_materiales = Column(Money, nullable=False)
    detalles_costos = Column(JSON, nullable=True)
    margen_ganancia = Column(Money, nullable=False)
    precio_final = Column(Money, nullable=False)
    estado = Column(String, default="Borrador")
    convertido_a_trabajo = Column(Boolean, default=False)
    fecha_creacion = Column(Date, nullable=False)

    cliente = relationship("Cliente")

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
    banco = Column(String, nullable=False)
    numero = Column(String, nullable=False)
    monto = Column(Money, nullable=False)
    fecha_emision = Column(Date, nullable=False)
    fecha_cobro = Column(Date, nullable=False)
    estado = Column(String, default="En Cartera") # En Cartera, Depositado, Endosado, Rechazado
    destinatario_endoso = Column(String, nullable=True)