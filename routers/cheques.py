from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/cheques", tags=["Cheques"])

# Estados finales: el cheque ya impactó la caja (o quedó anulado). Salir de ellos
# deshace un ingreso, así que exige un motivo que queda asentado en el historial.
ESTADOS_FINALES = {"Cobrado", "Endosado", "Rechazado"}

# Transiciones permitidas desde cada estado no final.
_TRANSICIONES = {
    "En Cartera": {"Depositado", "Endosado", "Rechazado"},
    "Depositado": {"Cobrado", "Rechazado"},
}


def _validar_transicion(actual: str, nuevo: str, motivo: str | None) -> None:
    """Valida el paso de un estado a otro. Lanza HTTPException si no corresponde.

    Que 'nuevo' sea un estado existente ya lo garantiza el schema contra
    models.ESTADOS_CHEQUE: acá sólo se decide si el paso es legítimo.
    """
    if actual in ESTADOS_FINALES:
        # Revertir un estado final se permite, pero nunca en silencio.
        if not motivo:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El cheque está en estado '{actual}' (final). Para revertirlo "
                    "indicá un motivo, que quedará registrado en el historial."
                ),
            )
        return

    permitidos = _TRANSICIONES.get(actual, set())
    if nuevo not in permitidos:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Transición inválida: '{actual}' no puede pasar a '{nuevo}'. "
                f"Permitidos desde '{actual}': {', '.join(sorted(permitidos)) or 'ninguno'}."
            ),
        )


def _asentar(db: Session, cheque_id: str, detalle: str,
             estado_anterior: str | None = None, estado_nuevo: str | None = None) -> None:
    """Agrega una fila al historial del cheque (no commitea)."""
    db.add(models.HistorialCheque(
        cheque_id=cheque_id,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        detalle=detalle,
    ))


@router.get("/", response_model=list[schemas.ChequeResponse])
def listar_cheques(db: Session = Depends(get_db)):
    # Los ordenamos por fecha de cobro para que los más urgentes salgan primero
    return db.query(models.Cheque).order_by(models.Cheque.fecha_cobro.asc()).all()

@router.post("/", response_model=schemas.ChequeResponse)
def crear_cheque(cheque: schemas.ChequeCreate, db: Session = Depends(get_db)):
    nuevo_cheque = models.Cheque(**cheque.model_dump())
    db.add(nuevo_cheque)
    db.flush()  # necesitamos el id para el historial
    _asentar(
        db, nuevo_cheque.id,
        detalle=f"Cheque {nuevo_cheque.clasificacion} creado por $ {nuevo_cheque.monto}",
        estado_nuevo=nuevo_cheque.estado,
    )
    db.commit()
    db.refresh(nuevo_cheque)
    return nuevo_cheque

@router.patch("/{cheque_id}", response_model=schemas.ChequeResponse)
def actualizar_estado_cheque(cheque_id: str, update_data: schemas.ChequeUpdate, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")

    cambios = update_data.model_dump(exclude_unset=True)
    motivo = cambios.pop("motivo", None)  # no es columna del cheque

    estado_actual = db_cheque.estado
    nuevo_estado = cambios.get("estado")
    cambia_estado = nuevo_estado is not None and nuevo_estado != estado_actual

    if cambia_estado:
        _validar_transicion(estado_actual, nuevo_estado, motivo)

    # Un cheque ya cobrado o endosado impactó ingresos y ganancia: cambiarle el
    # monto o la clasificación reescribiría el pasado.
    if estado_actual in {"Cobrado", "Endosado"}:
        for campo in ("monto", "clasificacion"):
            if campo in cambios and cambios[campo] != getattr(db_cheque, campo):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No se puede modificar '{campo}' de un cheque en estado "
                        f"'{estado_actual}'. Revertí el estado indicando un motivo."
                    ),
                )

    # La fecha de endoso la completa ChequeUpdate (schemas.py) para que valga
    # igual al crear y al editar; acá ya llega resuelta.

    # Historial: primero los cambios de monto/clasificación, después el de estado.
    for campo in ("monto", "clasificacion"):
        if campo in cambios and cambios[campo] != getattr(db_cheque, campo):
            _asentar(
                db, db_cheque.id,
                detalle=f"{campo} {getattr(db_cheque, campo)} -> {cambios[campo]}",
            )

    if cambia_estado:
        detalle = f"Estado {estado_actual} -> {nuevo_estado}"
        if motivo:
            detalle += f" (motivo: {motivo})"
        _asentar(db, db_cheque.id, detalle=detalle,
                 estado_anterior=estado_actual, estado_nuevo=nuevo_estado)

    for key, value in cambios.items():
        setattr(db_cheque, key, value)

    db.commit()
    db.refresh(db_cheque)
    return db_cheque

@router.get("/{cheque_id}/historial", response_model=list[schemas.HistorialChequeResponse])
def historial_cheque(cheque_id: str, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")
    return (
        db.query(models.HistorialCheque)
        .filter(models.HistorialCheque.cheque_id == cheque_id)
        .order_by(models.HistorialCheque.fecha.desc())
        .all()
    )

@router.delete("/{cheque_id}")
def eliminar_cheque(cheque_id: str, db: Session = Depends(get_db)):
    db_cheque = db.query(models.Cheque).filter(models.Cheque.id == cheque_id).first()
    if not db_cheque:
        raise HTTPException(status_code=404, detail="Cheque no encontrado")

    # Un cheque cobrado o endosado ya movió plata: borrarlo distorsiona ingresos y ganancia.
    if db_cheque.estado in {"Cobrado", "Endosado"}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede eliminar un cheque en estado '{db_cheque.estado}' "
                "porque ya impactó los ingresos. Marcalo como 'Rechazado' si corresponde."
            ),
        )

    # El historial no sobrevive al cheque: sin la fila padre queda huérfano.
    db.query(models.HistorialCheque).filter(
        models.HistorialCheque.cheque_id == cheque_id
    ).delete(synchronize_session=False)
    db.delete(db_cheque)
    db.commit()
    return {"mensaje": "Cheque eliminado"}
