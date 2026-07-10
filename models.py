import uuid
from sqlalchemy import Column, String, Integer, Float, Date, ForeignKey, JSON
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
    presupuestos = relationship("Presupuesto", back_populates="cliente")

class Trabajo(Base):
    __tablename__ = "trabajos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    descripcion_producto = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    estado = Column(String, default="Pendiente de Pago")
    fecha_creacion = Column(Date, nullable=False)
    fecha_comienzo = Column(Date, nullable=True)
    fecha_entrega = Column(Date, nullable=True)
    precio_venta = Column(Float, nullable=False)
    costo_total_materiales = Column(Float, nullable=False)
    forma_pago_heredada = Column(String, nullable=True)

    cliente = relationship("Cliente", back_populates="trabajos")

class Presupuesto(Base):
    __tablename__ = "presupuestos"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    numero_secuencia = Column(String, unique=True, index=True, nullable=False)
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    detalle_costos_interno = Column(JSON, nullable=False) 
    porcentaje_ganancia = Column(Float, nullable=False)
    precio_final_neto = Column(Float, nullable=False)
    fecha_emision = Column(Date, nullable=False)
    metodo_pago_elegido = Column(String, nullable=False)
    recargo_descuento_porcentaje = Column(Float, default=0.0)

    cliente = relationship("Cliente", back_populates="presupuestos")


class Cheque(Base):
    __tablename__ = "cheques"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tipo = Column(String, nullable=False) # 'Recibido' o 'Emitido'
    numero_cheque = Column(String, nullable=False)
    banco = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    fecha_cobro = Column(Date, nullable=False)
    estado = Column(String, default="Pendiente") # 'Pendiente', 'Cobrado', 'Rechazado'


class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    concepto = Column(String, nullable=False) # Ej: "Luz Taller"
    categoria = Column(String, nullable=False) # Ej: "Servicios", "Insumos Varios"
    monto = Column(Float, nullable=False)
    fecha = Column(Date, nullable=False)


class Stock(Base):
    __tablename__ = "stock"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    material = Column(String, nullable=False)
    cantidad_actual = Column(Float, nullable=False)
    cantidad_minima = Column(Float, nullable=False) # Gatillo para alertas rojas
    unidad = Column(String, nullable=False) # Ej: "resmas", "pliegos"