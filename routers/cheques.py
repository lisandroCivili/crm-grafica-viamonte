from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/cheques", tags=["Cheques"])

@router.post("/", response_model=schemas.ChequeResponse)
def crear_cheque(cheque: schemas.ChequeCreate, db: Session = Depends(get_db)):
    nuevo_cheque = models.Cheque(**cheque.model_dump())
    db.add(nuevo_cheque)
    db.commit()
    db.refresh(nuevo_cheque)
    return nuevo_cheque

@router.get("/", response_model=list[schemas.ChequeResponse])
def listar_cheques(tipo: str = None, estado: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Cheque)
    
    if tipo:
        query = query.filter(models.Cheque.tipo == tipo)
    if estado:
        query = query.filter(models.Cheque.estado == estado)
        
    return query.order_by(models.Cheque.fecha_cobro.asc()).all()

@router.put("/{cheque_id}", response_model=schemas.ChequeResponse)
def actualizar_estado_cheque(cheque_id: str, cheque_update: schemas.ChequeUpdate, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    
    db_cheque.estado = cheque_update.estado
    db.commit()
    db.refresh(db_cheque)
    return db_cheque