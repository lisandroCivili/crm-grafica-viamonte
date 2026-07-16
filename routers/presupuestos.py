from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from calculos import sumar_detalles_costos, calcular_precio_presupuesto

router = APIRouter(prefix="/api/presupuestos", tags=["Presupuestos"])

def generar_numero_secuencia(db: Session) -> str:
    # Buscamos el último presupuesto creado, ordenado por el número
    ultimo = (
        db.query(models.Presupuesto)
        .filter(models.Presupuesto.numero_secuencia.isnot(None))
        .order_by(models.Presupuesto.numero_secuencia.desc())
        .first()
    )

    if not ultimo or not ultimo.numero_secuencia:
        return "0001-000001"

    # Extraemos el número final y le sumamos 1
    # Ejemplo: "0001-000015" -> separamos por el guion y tomamos "000015"
    partes = ultimo.numero_secuencia.split("-")
    if len(partes) == 2:
        numero_actual = int(partes[1])
        nuevo_numero = str(numero_actual + 1).zfill(6)
        return f"0001-{nuevo_numero}"

    return "0001-000001"


@router.post("/", response_model=schemas.PresupuestoResponse)
def crear_presupuesto(presupuesto: schemas.PresupuestoCreate, db: Session = Depends(get_db)):
    # Verificamos que el cliente exista
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == presupuesto.cliente_id).first()
    if not db_cliente:
        raise HTTPException(status_code=404, detail="El cliente indicado no existe.")

    datos = presupuesto.model_dump()

    # FUENTE DE VERDAD EN EL BACKEND: recalculamos costo y precio final.
    # Ignoramos los valores que manda el cliente para costo_materiales/precio_final.
    costo_materiales = sumar_detalles_costos(datos.get("detalles_costos"))
    _, _, precio_final = calcular_precio_presupuesto(costo_materiales, datos["margen_ganancia"])
    datos["costo_materiales"] = costo_materiales
    datos["precio_final"] = precio_final

    # Generamos el número de presupuesto automático
    datos["numero_secuencia"] = generar_numero_secuencia(db)

    nuevo_presupuesto = models.Presupuesto(**datos)
    db.add(nuevo_presupuesto)
    db.commit()
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto


@router.get("/", response_model=list[schemas.PresupuestoResponse])
def listar_presupuestos(db: Session = Depends(get_db)):
    # Devolvemos los presupuestos ordenados desde el más nuevo al más viejo
    return db.query(models.Presupuesto).order_by(models.Presupuesto.fecha_creacion.desc()).all()


@router.put("/{presupuesto_id}", response_model=schemas.PresupuestoResponse)
def actualizar_presupuesto(presupuesto_id: str, presupuesto_update: schemas.PresupuestoUpdate, db: Session = Depends(get_db)):
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if db_presupuesto.convertido_a_trabajo:
        raise HTTPException(status_code=400, detail="No se puede editar: este presupuesto ya fue convertido a trabajo.")

    update_data = presupuesto_update.model_dump(exclude_unset=True)

    if "cliente_id" in update_data:
        db_cliente = db.query(models.Cliente).filter(models.Cliente.id == update_data["cliente_id"]).first()
        if not db_cliente:
            raise HTTPException(status_code=404, detail="El cliente indicado no existe.")

    for key, value in update_data.items():
        setattr(db_presupuesto, key, value)

    # FUENTE DE VERDAD EN EL BACKEND: recalculamos costo y precio final igual que al crear.
    costo_materiales = sumar_detalles_costos(db_presupuesto.detalles_costos)
    _, _, precio_final = calcular_precio_presupuesto(costo_materiales, db_presupuesto.margen_ganancia)
    db_presupuesto.costo_materiales = costo_materiales
    db_presupuesto.precio_final = precio_final

    db.commit()
    db.refresh(db_presupuesto)
    return db_presupuesto


@router.delete("/{presupuesto_id}")
def eliminar_presupuesto(presupuesto_id: str, db: Session = Depends(get_db)):
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if db_presupuesto.convertido_a_trabajo:
        raise HTTPException(status_code=400, detail="No se puede eliminar: este presupuesto ya fue convertido a trabajo.")

    tiene_versiones = db.query(models.Presupuesto).filter(models.Presupuesto.version_de == presupuesto_id).first()
    if tiene_versiones:
        raise HTTPException(status_code=400, detail="No se puede eliminar: existen versiones/duplicados hechos a partir de este presupuesto.")

    db.delete(db_presupuesto)
    db.commit()
    return {"mensaje": "Presupuesto eliminado"}


@router.put("/{presupuesto_id}/convertir/{trabajo_id}", response_model=schemas.PresupuestoResponse)
def marcar_convertido(presupuesto_id: str, trabajo_id: str, db: Session = Depends(get_db)):
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    db_presupuesto.convertido_a_trabajo = True
    db_presupuesto.trabajo_id = trabajo_id
    db_presupuesto.estado = "Aprobado"
    db.commit()
    db.refresh(db_presupuesto)
    return db_presupuesto
