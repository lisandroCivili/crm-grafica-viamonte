import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base

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
    precio_venta = Column(Float, nullable=False)
    costo_total_materiales = Column(Float, nullable=False)
    monto_abonado = Column(Float, default=0.0)
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
    monto = Column(Float, nullable=False)
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
    descripcion = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    costo_materiales = Column(Float, nullable=False)
    detalles_costos = Column(JSON, nullable=True)
    margen_ganancia = Column(Float, nullable=False)
    precio_final = Column(Float, nullable=False)
    estado = Column(String, default="Borrador")
    convertido_a_trabajo = Column(Boolean, default=False)
    fecha_creacion = Column(Date, nullable=False)

    cliente = relationship("Cliente")