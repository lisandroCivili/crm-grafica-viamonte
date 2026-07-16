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
    
    nuevo_cliente = models.Cliente(
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

@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def actualizar_cliente(cliente_id: str, cliente_update: schemas.ClienteUpdate, db: Session = Depends(get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    update_data = cliente_update.model_dump(exclude_unset=True)

    # Si cambia el DNI/CUIT, verificamos que no choque con otro cliente existente
    nuevo_cuit = update_data.get("dni_cuit")
    if nuevo_cuit and nuevo_cuit != db_cliente.dni_cuit:
        duplicado = db.query(models.Cliente).filter(
            models.Cliente.dni_cuit == nuevo_cuit,
            models.Cliente.id != cliente_id
        ).first()
        if duplicado:
            raise HTTPException(status_code=400, detail="Este DNI/CUIT ya está registrado por otro cliente.")

    for key, value in update_data.items():
        setattr(db_cliente, key, value)

    db.commit()
    db.refresh(db_cliente)
    return db_cliente

@router.delete("/{cliente_id}")
def eliminar_cliente(cliente_id: str, db: Session = Depends(get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    tiene_trabajos = db.query(models.Trabajo).filter(models.Trabajo.cliente_id == cliente_id).first()
    if tiene_trabajos:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene trabajos asociados.")

    tiene_movimientos = db.query(models.Movimiento).filter(models.Movimiento.cliente_id == cliente_id).first()
    if tiene_movimientos:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene movimientos de cuenta corriente asociados.")

    tiene_presupuestos = db.query(models.Presupuesto).filter(models.Presupuesto.cliente_id == cliente_id).first()
    if tiene_presupuestos:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene presupuestos asociados.")

    tiene_notas = db.query(models.Nota).filter(models.Nota.cliente_id == cliente_id).first()
    if tiene_notas:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene notas asociadas.")

    tiene_cheques = db.query(models.Cheque).filter(models.Cheque.cliente_id == cliente_id).first()
    if tiene_cheques:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene cheques asociados.")

    db.delete(db_cliente)
    db.commit()
    return {"mensaje": "Cliente eliminado"}