from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
import uuid

# Instanciamos el router específico para Clientes
router = APIRouter(
    prefix="/api/clientes",
    tags=["Clientes"]
)

@router.post("/", response_model=schemas.ClienteResponse)
def crear_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    # Verificamos que no exista ya un cliente con ese mismo CUIT/DNI
    db_cliente = db.query(models.Cliente).filter(models.Cliente.dni_cuit == cliente.dni_cuit).first()
    if db_cliente:
        raise HTTPException(status_code=400, detail="Este DNI/CUIT ya está registrado.")
    
    # Creamos el registro con un UUID generado automáticamente
    nuevo_cliente = models.Cliente(
        id=str(uuid.uuid4()),
        **cliente.model_dump()
    )
    
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

@router.get("/", response_model=list[schemas.ClienteResponse])
def listar_clientes(buscar: str = None, db: Session = Depends(get_db)):
    # Consulta base
    query = db.query(models.Cliente)
    
    # Si viene un parámetro "buscar" desde la barra de búsqueda del HTML, aplicamos los filtros
    if buscar:
        filtro = f"%{buscar}%"
        query = query.filter(
            (models.Cliente.nombre_completo.ilike(filtro)) |
            (models.Cliente.nombre_empresa.ilike(filtro)) |
            (models.Cliente.dni_cuit.ilike(filtro))
        )
        
    return query.all()