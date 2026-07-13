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