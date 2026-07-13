from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/movimientos", tags=["Movimientos"])

@router.post("/", response_model=schemas.MovimientoResponse)
def crear_movimiento(mov: schemas.MovimientoCreate, db: Session = Depends(get_db)):
    nuevo = models.Movimiento(**mov.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/{cliente_id}", response_model=list[schemas.MovimientoResponse])
def listar_movimientos(cliente_id: str, db: Session = Depends(get_db)):
    return db.query(models.Movimiento).filter(models.Movimiento.cliente_id == cliente_id).all()