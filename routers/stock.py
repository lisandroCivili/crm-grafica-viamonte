from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from datetime import date

router = APIRouter(prefix="/api/stock", tags=["Stock"])

@router.get("/", response_model=list[schemas.StockResponse])
def listar_stock(db: Session = Depends(get_db)):
    return db.query(models.ArticuloStock).order_by(models.ArticuloStock.nombre).all()

@router.post("/", response_model=schemas.StockResponse)
def crear_articulo(art: schemas.StockCreate, db: Session = Depends(get_db)):
    nuevo = models.ArticuloStock(**art.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

# REEMPLAZAR EL PATCH Y AGREGAR EL GET DE HISTORIAL
@router.patch("/{articulo_id}")
def actualizar_cantidad(articulo_id: str, update_data: schemas.StockUpdate, db: Session = Depends(get_db)):
    db_art = db.query(models.ArticuloStock).filter(models.ArticuloStock.id == articulo_id).first()
    if not db_art:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    
    if update_data.cantidad is not None:
        diferencia = update_data.cantidad - db_art.cantidad
        
        # MAGIA: Si hubo un cambio real, registramos el historial
        if diferencia != 0:
            historial = models.HistorialStock(
                articulo_id=db_art.id,
                diferencia=diferencia,
                motivo=update_data.motivo
            )
            db.add(historial)
            db_art.cantidad = update_data.cantidad

    if update_data.costo_unitario is not None:
        db_art.costo_unitario = update_data.costo_unitario
        
    db_art.ultima_actualizacion = date.today()
    db.commit()
    return {"mensaje": "Stock actualizado"}

@router.get("/{articulo_id}/historial", response_model=list[schemas.HistorialStockResponse])
def ver_historial(articulo_id: str, db: Session = Depends(get_db)):
    # Trae los movimientos del más nuevo al más viejo
    return db.query(models.HistorialStock).filter(models.HistorialStock.articulo_id == articulo_id).order_by(models.HistorialStock.fecha.desc()).all()