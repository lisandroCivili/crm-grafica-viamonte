from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from calculos import CATEGORIA_COSTO_PRESUPUESTADO
from database import get_db

router = APIRouter(prefix="/api/gastos", tags=["Gastos"])


def _validar_costo_presupuestado(categoria: str, trabajo_id: str | None) -> None:
    """Un costo presupuestado sin trabajo no se puede compensar contra ningún margen.

    Como esa categoría no resta de la ganancia, dejarla suelta escondería un
    gasto real del taller y la inflaría sin que nadie lo note.
    """
    if categoria == CATEGORIA_COSTO_PRESUPUESTADO and not trabajo_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Un gasto de categoría '{CATEGORIA_COSTO_PRESUPUESTADO}' tiene que estar "
                "asociado a un trabajo. Si es un gasto general del taller, usá otra categoría."
            ),
        )

@router.get("/", response_model=list[schemas.GastoResponse])
def listar_gastos(db: Session = Depends(get_db)):
    # Los ordenamos del más nuevo al más viejo
    return db.query(models.Gasto).order_by(models.Gasto.fecha.desc()).all()

@router.post("/", response_model=schemas.GastoResponse)
def crear_gasto(gasto: schemas.GastoCreate, db: Session = Depends(get_db)):
    _validar_costo_presupuestado(gasto.categoria, gasto.trabajo_id)
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

    # Se valida el estado resultante y no el payload: un update parcial que sólo
    # borra el trabajo esquivaría la validación si mirásemos únicamente lo enviado.
    _validar_costo_presupuestado(
        update_data.get("categoria", db_gasto.categoria),
        update_data.get("trabajo_id", db_gasto.trabajo_id),
    )

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