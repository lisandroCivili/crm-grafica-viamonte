from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/presupuestos", tags=["Presupuestos"])

def generar_numero_secuencia(db: Session) -> str:
    # Buscamos el último presupuesto creado, ordenado por el número
    ultimo = db.query(models.Presupuesto).order_by(models.Presupuesto.numero_secuencia.desc()).first()
    
    if not ultimo:
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
def crear_presupuesto(presu: schemas.PresupuestoCreate, db: Session = Depends(get_db)):
    nuevo = models.Presupuesto(**presu.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/", response_model=list[schemas.PresupuestoResponse])
def listar_presupuestos(db: Session = Depends(get_db)):
    return db.query(models.Presupuesto).all()

# (Abajo de la ruta POST y GET que ya tenías)
# Reemplazá el PUT anterior por este:
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

@router.post("/", response_model=schemas.PresupuestoResponse)
def crear_presupuesto(presupuesto: schemas.PresupuestoCreate, db: Session = Depends(get_db)):
    # Verificamos que el cliente exista
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == presupuesto.cliente_id).first()
    if not db_cliente:
        raise HTTPException(status_code=404, detail="El cliente indicado no existe.")
    
    # Generamos el número de presupuesto automático
    nro_secuencia = generar_numero_secuencia(db)
    
    nuevo_presupuesto = models.Presupuesto(
        numero_secuencia=nro_secuencia,
        **presupuesto.model_dump()
    )
    db.add(nuevo_presupuesto)
    db.commit()
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto

@router.get("/", response_model=list[schemas.PresupuestoResponse])
def listar_presupuestos(db: Session = Depends(get_db)):
    # Devolvemos los presupuestos ordenados desde el más nuevo al más viejo
    return db.query(models.Presupuesto).order_by(models.Presupuesto.fecha_emision.desc()).all()