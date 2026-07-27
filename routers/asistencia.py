from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from calculos import CERO, horas_trabajadas
from database import get_db

router = APIRouter(prefix="/api/asistencia", tags=["Asistencia"])


def _fila_vacia(fila: schemas.FilaPlanillaGuardar) -> bool:
    """Una fila sin nada cargado: ese empleado no tiene nada anotado ese día."""
    return (
        fila.hora_entrada is None
        and fila.hora_salida is None
        and not (fila.observaciones or "").strip()
    )


def _validar_empleados_de_la_planilla(db: Session, filas) -> None:
    """Corta antes de tocar la base si las filas no son consistentes.

    Dos filas del mismo empleado se procesarían una encima de la otra y la
    segunda pisaría a la primera sin avisar. Un empleado inexistente reventaría
    contra la foreign key con un 500 opaco.
    """
    ids = [f.empleado_id for f in filas]

    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise HTTPException(
            status_code=400,
            detail="La planilla trae más de una fila para el mismo empleado.",
        )

    existentes = {
        e.id for e in db.query(models.Empleado.id).filter(models.Empleado.id.in_(ids)).all()
    }
    faltantes = set(ids) - existentes
    if faltantes:
        raise HTTPException(
            status_code=404,
            detail=f"Hay {len(faltantes)} empleado(s) de la planilla que ya no existen.",
        )


def _armar_planilla(db: Session, fecha: date) -> schemas.PlanillaDiaResponse:
    """La grilla de un día: una fila por empleado, tenga registro o no.

    Van los activos, más cualquier inactivo que tenga algo cargado esa fecha:
    si alguien se dio de baja en marzo, su día de febrero tiene que seguir
    viéndose al abrir febrero.

    Dos consultas y cruce en memoria, sin N+1.
    """
    registros = db.query(models.RegistroAsistencia).filter(
        models.RegistroAsistencia.fecha == fecha
    ).all()
    registro_por_empleado = {r.empleado_id: r for r in registros}

    empleados = db.query(models.Empleado).filter(
        (models.Empleado.activo == True) | (models.Empleado.id.in_(registro_por_empleado.keys()))
    ).order_by(models.Empleado.nombre).all()

    filas = []
    for e in empleados:
        registro = registro_por_empleado.get(e.id)
        filas.append(schemas.FilaPlanillaResponse(
            empleado_id=e.id,
            nombre=e.nombre,
            hora_entrada=registro.hora_entrada if registro else None,
            hora_salida=registro.hora_salida if registro else None,
            observaciones=registro.observaciones if registro else None,
        ))

    return schemas.PlanillaDiaResponse(fecha=fecha, filas=filas)


# OJO: 'planilla' y 'resumen' son rutas literales. Si algún día se agrega
# GET /{registro_id}, tiene que declararse DESPUÉS de estas dos o FastAPI va a
# interpretar "planilla" como un id. Mismo cuidado que en routers/clientes.py.
@router.get("/planilla", response_model=schemas.PlanillaDiaResponse)
def ver_planilla(fecha: date = None, db: Session = Depends(get_db)):
    """La planilla de un día. Sin fecha, la de hoy."""
    return _armar_planilla(db, fecha or date.today())

@router.post("/planilla", response_model=schemas.PlanillaDiaResponse)
def guardar_planilla(planilla: schemas.PlanillaGuardarRequest, db: Session = Depends(get_db)):
    """Guarda el día entero de una sola vez.

    Por cada fila hace upsert contra (empleado, fecha): si ya había registro lo
    actualiza y si no lo crea. Una fila que llega vacía borra el registro que
    hubiera: es la forma de deshacer una carga equivocada sin un endpoint aparte.

    Un solo commit al final, así el día se guarda entero o no se guarda: media
    planilla cargada es peor que ninguna, porque nadie se da cuenta.

    Devuelve la planilla ya guardada, con las horas recalculadas por el backend,
    para que el frontend refresque contra la fuente de verdad sin pedirla de nuevo.
    """
    _validar_empleados_de_la_planilla(db, planilla.filas)

    ids = [f.empleado_id for f in planilla.filas]
    registro_por_empleado = {
        r.empleado_id: r
        for r in db.query(models.RegistroAsistencia).filter(
            models.RegistroAsistencia.fecha == planilla.fecha,
            models.RegistroAsistencia.empleado_id.in_(ids),
        ).all()
    }

    for fila in planilla.filas:
        registro = registro_por_empleado.get(fila.empleado_id)

        if _fila_vacia(fila):
            if registro:
                db.delete(registro)
            continue

        if registro is None:
            registro = models.RegistroAsistencia(
                empleado_id=fila.empleado_id, fecha=planilla.fecha
            )
            db.add(registro)

        registro.hora_entrada = fila.hora_entrada
        registro.hora_salida = fila.hora_salida
        registro.observaciones = (fila.observaciones or "").strip() or None

    db.commit()
    return _armar_planilla(db, planilla.fecha)

@router.get("/resumen", response_model=list[schemas.ResumenEmpleadoResponse])
def resumen_por_periodo(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Horas y días trabajados por empleado entre dos fechas, ambas incluidas.

    Sale de los registros del período y no de la lista de empleados activos: el
    que se dio de baja en marzo tiene que seguir apareciendo en el resumen de
    febrero, con las horas que hizo.

    Sólo cuenta los días con la jornada completa. Un día a medio cargar (entró y
    todavía no se anotó la salida) no aporta horas, así que tampoco suma como
    día trabajado; si contara, el promedio por día saldría mal.
    """
    if desde > hasta:
        raise HTTPException(
            status_code=400,
            detail="La fecha 'desde' no puede ser posterior a la fecha 'hasta'.",
        )

    registros = db.query(models.RegistroAsistencia).filter(
        models.RegistroAsistencia.fecha >= desde,
        models.RegistroAsistencia.fecha <= hasta,
    ).all()

    acumulado = {}
    for r in registros:
        horas = horas_trabajadas(r.hora_entrada, r.hora_salida)
        if horas is None:
            continue
        dias, total = acumulado.get(r.empleado_id, (0, CERO))
        acumulado[r.empleado_id] = (dias + 1, total + horas)

    if not acumulado:
        return []

    empleados = db.query(models.Empleado).filter(
        models.Empleado.id.in_(acumulado.keys())
    ).order_by(models.Empleado.nombre).all()

    return [
        schemas.ResumenEmpleadoResponse(
            empleado_id=e.id,
            nombre=e.nombre,
            dias_trabajados=acumulado[e.id][0],
            total_horas=acumulado[e.id][1],
        )
        for e in empleados
    ]
