from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas
from auditoria import asentar, cambios
from database import get_db
from routers._comun import obtener_o_404
from seguridad import TODOS_LOS_ROLES, requiere_rol, usuario_actual

# Entran los tres puestos: las notas son los post-it de la ficha del cliente
# ("llamar antes de entregar", "pidió que le avisen cuando esté"), no un
# registro contable. Por eso acá el borrado tampoco queda sólo para el dueño.
router = APIRouter(
    prefix="/api/notas",
    tags=["Notas"],
    dependencies=[Depends(requiere_rol(*TODOS_LOS_ROLES))],
)

# Cómo se llama esta entidad en el registro de auditoría.
ENTIDAD = "Nota"

# Una nota puede ser larga; en el log alcanza con reconocerla.
LARGO_RESUMEN = 60


def _resumen(nota: models.Nota) -> str:
    """Cómo se nombra esta nota en el registro de auditoría: por su texto."""
    texto = (nota.texto or "").strip()
    return texto if len(texto) <= LARGO_RESUMEN else f"{texto[:LARGO_RESUMEN]}…"

@router.post("/", response_model=schemas.NotaResponse)
def crear_nota(
    nota: schemas.NotaCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    nuevo = models.Nota(**nota.model_dump())
    db.add(nuevo)
    db.flush()  # necesitamos el id para el asiento de auditoría
    asentar(db, usuario, models.ACCION_ALTA, ENTIDAD, nuevo.id, _resumen(nuevo))
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/{cliente_id}", response_model=list[schemas.NotaResponse])
def listar_notas(cliente_id: str, db: Session = Depends(get_db)):
    return db.query(models.Nota).filter(models.Nota.cliente_id == cliente_id).order_by(models.Nota.fecha_creacion.desc()).all()

@router.put("/{nota_id}", response_model=schemas.NotaResponse)
def actualizar_nota(
    nota_id: str,
    nota_update: schemas.NotaUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    db_nota = obtener_o_404(db, models.Nota, nota_id, "Nota no encontrada")

    db_nota.texto = nota_update.texto

    detalle = cambios(db_nota)
    if detalle:
        asentar(db, usuario, models.ACCION_EDICION, ENTIDAD, db_nota.id,
                _resumen(db_nota), detalle)

    db.commit()
    db.refresh(db_nota)
    return db_nota

@router.delete("/{nota_id}")
def eliminar_nota(
    nota_id: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    db_nota = obtener_o_404(db, models.Nota, nota_id, "Nota no encontrada")

    asentar(db, usuario, models.ACCION_BAJA, ENTIDAD, db_nota.id, _resumen(db_nota))

    db.delete(db_nota)
    db.commit()
    return {"mensaje": "Nota eliminada"}