from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/stock", tags=["Stock"])

@router.post("/", response_model=schemas.StockResponse)
def crear_insumo(stock: schemas.StockCreate, db: Session = Depends(get_db)):
    nuevo_insumo = models.Stock(**stock.model_dump())
    db.add(nuevo_insumo)
    db.commit()
    db.refresh(nuevo_insumo)
    return nuevo_insumo

@router.get("/", response_model=list[schemas.StockResponse])
def listar_stock(db: Session = Depends(get_db)):
    return db.query(models.Stock).all()

@router.get("/alertas", response_model=list[schemas.StockResponse])
def listar_alertas_stock(db: Session = Depends(get_db)):
    # Devuelve SOLO los insumos cuya cantidad actual sea menor o igual a la mínima
    return db.query(models.Stock).filter(models.Stock.cantidad_actual <= models.Stock.cantidad_minima).all()

@router.put("/{stock_id}", response_model=schemas.StockResponse)
def actualizar_cantidad(stock_id: str, stock_update: schemas.StockUpdate, db: Session = Depends(get_db)):
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not db_stock:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    
    db_stock.cantidad_actual = stock_update.cantidad_actual
    db.commit()
    db.refresh(db_stock)
    return db_stock