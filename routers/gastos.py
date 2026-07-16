from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/gastos", tags=["Gastos"])

@router.get("/", response_model=list[schemas.GastoResponse])
def listar_gastos(db: Session = Depends(get_db)):
    # Los ordenamos del más nuevo al más viejo
    return db.query(models.Gasto).order_by(models.Gasto.fecha.desc()).all()

@router.post("/", response_model=schemas.GastoResponse)
def crear_gasto(gasto: schemas.GastoCreate, db: Session = Depends(get_db)):
    nuevo_gasto = models.Gasto(**gasto.model_dump())
    db.add(nuevo_gasto)
    db.commit()
    db.refresh(nuevo_gasto)
    return nuevo_gasto

@router.put("/{gasto_id}", response_model=schemas.GastoResponse)
def actualizar_gasto(gasto_id: str, gasto_update: schemas.GastoUpdate, db: Session = Depends(get_db)):
    db_gasto = db.query(models.Gasto).filter(models.Gasto.id == gasto_id).first()
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    update_data = gasto_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_gasto, key, value)

    db.commit()
    db.refresh(db_gasto)
    return db_gasto

@router.delete("/{gasto_id}")
def eliminar_gasto(gasto_id: str, db: Session = Depends(get_db)):
    db_gasto = db.query(models.Gasto).filter(models.Gasto.id == gasto_id).first()
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db.delete(db_gasto)
    db.commit()
    return {"mensaje": "Gasto eliminado"}