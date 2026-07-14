from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/cheques", tags=["Cheques"])

@router.get("/", response_model=list[schemas.ChequeResponse])
def listar_cheques(db: Session = Depends(get_db)):
    # Los ordenamos por fecha de cobro para que los más urgentes salgan primero
    return db.query(models.Cheque).order_by(models.Cheque.fecha_cobro.asc()).all()

@router.post("/", response_model=schemas.ChequeResponse)
def crear_cheque(cheque: schemas.ChequeCreate, db: Session = Depends(get_db)):
    nuevo_cheque = models.Cheque(**cheque.model_dump())
    db.add(nuevo_cheque)
    db.commit()
    db.refresh(nuevo_cheque)
    return nuevo_cheque

@router.patch("/{cheque_id}", response_model=schemas.ChequeResponse)
def actualizar_estado_cheque(cheque_id: str, update_data: schemas.ChequeUpdate, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    
    if update_data.estado is not None:
        db_cheque.estado = update_data.estado
    if update_data.destinatario_endoso is not None:
        db_cheque.destinatario_endoso = update_data.destinatario_endoso
        
    db.commit()
    db.refresh(db_cheque)
    return db_cheque

@router.delete("/{cheque_id}")
def eliminar_cheque(cheque_id: str, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    db.delete(db_cheque)
    db.commit()
    return {"mensaje": "Cheque eliminado"}