from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from auditoria import asentar, cambios
from calculos import CATEGORIA_COSTO_PRESUPUESTADO
from database import get_db
from routers._comun import obtener_o_404
from seguridad import ROL_ADMIN, ROL_MOSTRADOR, requiere_rol, solo_admin, usuario_actual

# El mostrador carga los gastos del día (el flete, la caja chica). El encargado
# no tiene esta pestaña. Borrar queda sólo para el dueño: un gasto borrado
# cambia la ganancia del mes sin dejar rastro.
router = APIRouter(
    prefix="/api/gastos",
    tags=["Gastos"],
    dependencies=[Depends(requiere_rol(ROL_ADMIN, ROL_MOSTRADOR))],
)


# Cómo se llama esta entidad en el registro de auditoría.
ENTIDAD = "Gasto"


def _resumen(gasto: models.Gasto) -> str:
    """Cómo se nombra este gasto en el registro de auditoría.

    El monto va en el resumen y no sólo en el detalle: en un gasto es el dato
    por el que se lo busca, y en un borrado es lo único que queda.
    """
    return f"{gasto.concepto} — $ {gasto.monto} ({gasto.categoria})"


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
def crear_gasto(
    gasto: schemas.GastoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    _validar_costo_presupuestado(gasto.categoria, gasto.trabajo_id)
    nuevo_gasto = models.Gasto(**gasto.model_dump())
    db.add(nuevo_gasto)
    db.flush()  # necesitamos el id para el asiento de auditoría
    asentar(db, usuario, models.ACCION_ALTA, ENTIDAD, nuevo_gasto.id, _resumen(nuevo_gasto))
    db.commit()
    db.refresh(nuevo_gasto)
    return nuevo_gasto

@router.put("/{gasto_id}", response_model=schemas.GastoResponse)
def actualizar_gasto(
    gasto_id: str,
    gasto_update: schemas.GastoUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    db_gasto = obtener_o_404(db, models.Gasto, gasto_id, "Gasto no encontrado")

    update_data = gasto_update.model_dump(exclude_unset=True)

    # Se valida el estado resultante y no el payload: un update parcial que sólo
    # borra el trabajo esquivaría la validación si mirásemos únicamente lo enviado.
    _validar_costo_presupuestado(
        update_data.get("categoria", db_gasto.categoria),
        update_data.get("trabajo_id", db_gasto.trabajo_id),
    )

    for key, value in update_data.items():
        setattr(db_gasto, key, value)

    detalle = cambios(db_gasto)
    if detalle:
        asentar(db, usuario, models.ACCION_EDICION, ENTIDAD, db_gasto.id,
                _resumen(db_gasto), detalle)

    db.commit()
    db.refresh(db_gasto)
    return db_gasto

@router.delete("/{gasto_id}", dependencies=[Depends(solo_admin)])
def eliminar_gasto(
    gasto_id: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    db_gasto = obtener_o_404(db, models.Gasto, gasto_id, "Gasto no encontrado")

    # Un gasto borrado cambia la ganancia del mes: el asiento es lo único que
    # queda para explicar por qué el número de este mes no da lo mismo que ayer.
    asentar(db, usuario, models.ACCION_BAJA, ENTIDAD, db_gasto.id, _resumen(db_gasto))

    db.delete(db_gasto)
    db.commit()
    return {"mensaje": "Gasto eliminado"}