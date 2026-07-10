from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/gastos", tags=["Gastos"])

@router.post("/", response_model=schemas.GastoResponse)
def registrar_gasto(gasto: schemas.GastoCreate, db: Session = Depends(get_db)):
    nuevo_gasto = models.Gasto(**gasto.model_dump())
    db.add(nuevo_gasto)
    db.commit()
    db.refresh(nuevo_gasto)
    return nuevo_gasto

@router.get("/", response_model=list[schemas.GastoResponse])
def listar_gastos(db: Session = Depends(get_db)):
    # Los traemos ordenados por fecha, del más reciente al más antiguo
    return db.query(models.Gasto).order_by(models.Gasto.fecha.desc()).all()