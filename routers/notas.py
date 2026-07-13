from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/notas", tags=["Notas"])

@router.post("/", response_model=schemas.NotaResponse)
def crear_nota(nota: schemas.NotaCreate, db: Session = Depends(get_db)):
    nuevo = models.Nota(**nota.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/{cliente_id}", response_model=list[schemas.NotaResponse])
def listar_notas(cliente_id: str, db: Session = Depends(get_db)):
    return db.query(models.Nota).filter(models.Nota.cliente_id == cliente_id).order_by(models.Nota.fecha_creacion.desc()).all()