from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/trabajos", tags=["Trabajos"])

@router.post("/", response_model=schemas.TrabajoResponse)
def crear_trabajo(trabajo: schemas.TrabajoCreate, db: Session = Depends(get_db)):
    nuevo_trabajo = models.Trabajo(**trabajo.model_dump())
    db.add(nuevo_trabajo)
    db.commit()
    db.refresh(nuevo_trabajo)
    return nuevo_trabajo

@router.get("/", response_model=list[schemas.TrabajoResponse])
def listar_trabajos(estado: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Trabajo)
    # Filtro ideal para el Kanban (ej: traer solo los "En Diseño")
    if estado:
        query = query.filter(models.Trabajo.estado == estado)
    return query.all()

@router.put("/{trabajo_id}", response_model=schemas.TrabajoResponse)
def actualizar_trabajo(trabajo_id: str, trabajo_update: schemas.TrabajoUpdate, db: Session = Depends(get_db)):
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    # Magia de FastAPI: Extrae solo los datos que mandó el Front-End y los actualiza
    update_data = trabajo_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_trabajo, key, value)
        
    db.commit()
    db.refresh(db_trabajo)
    return db_trabajo