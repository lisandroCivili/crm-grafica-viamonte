from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from routers._comun import obtener_o_404
from seguridad import TODOS_LOS_ROLES, requiere_rol

# Entran los tres puestos: las notas son los post-it de la ficha del cliente
# ("llamar antes de entregar", "pidió que le avisen cuando esté"), no un
# registro contable. Por eso acá el borrado tampoco queda sólo para el dueño.
router = APIRouter(
    prefix="/api/notas",
    tags=["Notas"],
    dependencies=[Depends(requiere_rol(*TODOS_LOS_ROLES))],
)

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

@router.put("/{nota_id}", response_model=schemas.NotaResponse)
def actualizar_nota(nota_id: str, nota_update: schemas.NotaUpdate, db: Session = Depends(get_db)):
    db_nota = obtener_o_404(db, models.Nota, nota_id, "Nota no encontrada")

    db_nota.texto = nota_update.texto
    db.commit()
    db.refresh(db_nota)
    return db_nota

@router.delete("/{nota_id}")
def eliminar_nota(nota_id: str, db: Session = Depends(get_db)):
    db_nota = obtener_o_404(db, models.Nota, nota_id, "Nota no encontrada")

    db.delete(db_nota)
    db.commit()
    return {"mensaje": "Nota eliminada"}