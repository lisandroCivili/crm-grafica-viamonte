from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from calculos import calcular_saldo_cliente

router = APIRouter(prefix="/api/movimientos", tags=["Movimientos"])

@router.get("/", response_model=list[schemas.MovimientoResponse])
def listar_todos_movimientos(db: Session = Depends(get_db)):
    return db.query(models.Movimiento).all()

@router.post("/", response_model=schemas.MovimientoResponse)
def crear_movimiento(mov: schemas.MovimientoCreate, db: Session = Depends(get_db)):
    # Un pago siempre tiene que ser un monto positivo.
    if mov.tipo == "Pago" and mov.monto <= Decimal("0"):
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0.")

    nuevo = models.Movimiento(**mov.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/saldo/{cliente_id}", response_model=schemas.SaldoResponse)
def obtener_saldo(cliente_id: str, db: Session = Depends(get_db)):
    # Saldo calculado por el backend: fuente de verdad única.
    trabajos = db.query(models.Trabajo).filter(models.Trabajo.cliente_id == cliente_id).all()
    movimientos = db.query(models.Movimiento).filter(models.Movimiento.cliente_id == cliente_id).all()
    total_facturado, total_pagado, saldo = calcular_saldo_cliente(trabajos, movimientos)
    return schemas.SaldoResponse(
        cliente_id=cliente_id,
        total_facturado=total_facturado,
        total_pagado=total_pagado,
        saldo=saldo,
    )

@router.get("/{cliente_id}", response_model=list[schemas.MovimientoResponse])
def listar_movimientos(cliente_id: str, db: Session = Depends(get_db)):
    return db.query(models.Movimiento).filter(models.Movimiento.cliente_id == cliente_id).all()

@router.put("/{movimiento_id}", response_model=schemas.MovimientoResponse)
def actualizar_movimiento(movimiento_id: str, mov_update: schemas.MovimientoUpdate, db: Session = Depends(get_db)):
    db_mov = db.query(models.Movimiento).filter(models.Movimiento.id == movimiento_id).first()
    if not db_mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    update_data = mov_update.model_dump(exclude_unset=True)

    nuevo_tipo = update_data.get("tipo", db_mov.tipo)
    nuevo_monto = update_data.get("monto", db_mov.monto)
    if nuevo_tipo == "Pago" and nuevo_monto <= Decimal("0"):
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0.")

    for key, value in update_data.items():
        setattr(db_mov, key, value)

    db.commit()
    db.refresh(db_mov)
    return db_mov

@router.delete("/{movimiento_id}")
def eliminar_movimiento(movimiento_id: str, db: Session = Depends(get_db)):
    db_mov = db.query(models.Movimiento).filter(models.Movimiento.id == movimiento_id).first()
    if not db_mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    db.delete(db_mov)
    db.commit()
    return {"mensaje": "Movimiento eliminado"}
