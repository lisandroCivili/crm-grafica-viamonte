from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/trabajos", tags=["Trabajos"])

@router.post("/", response_model=schemas.TrabajoResponse)
def crear_trabajo(trabajo: schemas.TrabajoCreate, db: Session = Depends(get_db)):
    nuevo_trabajo = models.Trabajo(**trabajo.model_dump())
    db.add(nuevo_trabajo)
    db.commit()
    db.refresh(nuevo_trabajo)
    return nuevo_trabajo

@router.get("/", response_model=list[schemas.TrabajoResponse])
def listar_trabajos(estado: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Trabajo)
    # Filtro ideal para el Kanban (ej: traer solo los "En Diseño")
    if estado:
        query = query.filter(models.Trabajo.estado == estado)
    return query.all()

@router.put("/{trabajo_id}", response_model=schemas.TrabajoResponse)
def actualizar_estado_trabajo(trabajo_id: str, trabajo_update: schemas.TrabajoUpdate, db: Session = Depends(get_db)):
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    # Actualizamos solo los campos que vengan en la petición (para mover la tarjeta)
    if trabajo_update.estado:
        db_trabajo.estado = trabajo_update.estado
    if trabajo_update.fecha_comienzo:
        db_trabajo.fecha_comienzo = trabajo_update.fecha_comienzo
    if trabajo_update.fecha_entrega:
        db_trabajo.fecha_entrega = trabajo_update.fecha_entrega
    # Adentro de actualizar_estado_trabajo... sumá estos IFs:
    if trabajo_update.descripcion_producto:
        db_trabajo.descripcion_producto = trabajo_update.descripcion_producto
    if trabajo_update.cantidad is not None:
        db_trabajo.cantidad = trabajo_update.cantidad
    if trabajo_update.precio_venta is not None:
        db_trabajo.precio_venta = trabajo_update.precio_venta
    if trabajo_update.monto_abonado is not None:
        db_trabajo.monto_abonado = trabajo_update.monto_abonado
        
    db.commit()
    db.refresh(db_trabajo)
    return db_trabajo