from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from auditoria import asentar, cambios
from database import get_db
from routers._comun import obtener_o_404
from seguridad import ROL_ADMIN, ROL_ENCARGADO, requiere_rol, solo_admin, usuario_actual

# Va de la mano con Asistencia: el encargado, que carga la planilla todos los
# días, tiene que poder agregar al que entró esta semana sin depender del dueño.
router = APIRouter(
    prefix="/api/empleados",
    tags=["Empleados"],
    dependencies=[Depends(requiere_rol(ROL_ADMIN, ROL_ENCARGADO))],
)

# Cómo se llama esta entidad en el registro de auditoría.
ENTIDAD = "Empleado"


@router.get("/", response_model=list[schemas.EmpleadoResponse])
def listar_empleados(incluir_inactivos: bool = False, db: Session = Depends(get_db)):
    """Los empleados en actividad, ordenados por nombre.

    Por defecto sólo los activos: es lo que necesita la planilla del día. El
    ABM pide incluir_inactivos para poder rehabilitar a alguien que volvió.
    """
    query = db.query(models.Empleado)

    if not incluir_inactivos:
        query = query.filter(models.Empleado.activo == True)

    return query.order_by(models.Empleado.nombre).all()

@router.post("/", response_model=schemas.EmpleadoResponse)
def crear_empleado(
    empleado: schemas.EmpleadoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    nuevo_empleado = models.Empleado(**empleado.model_dump())
    db.add(nuevo_empleado)
    db.flush()  # necesitamos el id para el asiento de auditoría
    asentar(db, usuario, models.ACCION_ALTA, ENTIDAD, nuevo_empleado.id, nuevo_empleado.nombre)
    db.commit()
    db.refresh(nuevo_empleado)
    return nuevo_empleado

@router.put("/{empleado_id}", response_model=schemas.EmpleadoResponse)
def actualizar_empleado(
    empleado_id: str,
    empleado_update: schemas.EmpleadoUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    """Renombra un empleado, lo da de baja o lo vuelve a habilitar.

    Dar de baja es activo=False: el empleado sale de la planilla del día pero
    sus horas históricas quedan intactas y siguen sumando en los resúmenes de
    períodos anteriores.
    """
    db_empleado = obtener_o_404(db, models.Empleado, empleado_id, "Empleado no encontrado")

    update_data = empleado_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_empleado, key, value)

    detalle = cambios(db_empleado)
    if detalle:
        asentar(db, usuario, models.ACCION_EDICION, ENTIDAD, db_empleado.id,
                db_empleado.nombre, detalle)

    db.commit()
    db.refresh(db_empleado)
    return db_empleado

@router.delete("/{empleado_id}", dependencies=[Depends(solo_admin)])
def eliminar_empleado(
    empleado_id: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    """Borra un empleado, sólo si nunca se le cargó asistencia.

    Borrar existe para corregir un alta equivocada, no para dar de baja a
    alguien que se fue: si tiene días cargados, borrarlo se llevaría puesto el
    historial de horas de esos meses. Para eso está activo=False.
    """
    db_empleado = obtener_o_404(db, models.Empleado, empleado_id, "Empleado no encontrado")

    dias_cargados = db.query(models.RegistroAsistencia).filter(
        models.RegistroAsistencia.empleado_id == empleado_id
    ).count()
    if dias_cargados:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede eliminar: {db_empleado.nombre} tiene {dias_cargados} "
                "día(s) de asistencia cargados. Dalo de baja en lugar de borrarlo "
                "para no perder el historial de horas."
            ),
        )

    asentar(db, usuario, models.ACCION_BAJA, ENTIDAD, db_empleado.id, db_empleado.nombre)

    db.delete(db_empleado)
    db.commit()
    return {"mensaje": "Empleado eliminado"}
