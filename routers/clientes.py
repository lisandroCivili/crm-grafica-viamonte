from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from calculos import calcular_saldo_cliente
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

# OJO: si algún día se agrega GET /{cliente_id}, esta ruta debe declararse antes
# para que "saldos" no se interprete como un id de cliente.
@router.get("/saldos", response_model=list[schemas.SaldoResponse])
def saldos_clientes(db: Session = Depends(get_db)):
    """Saldo de todos los clientes en una sola respuesta.

    Única fuente de verdad para el listado de clientes: mismo cálculo que la
    ficha (calcular_saldo_cliente, que incluye cheques recibidos no rechazados).
    Una consulta por tabla y cruce en memoria, sin N+1.
    """
    clientes = db.query(models.Cliente).all()

    trabajos_por_cliente = defaultdict(list)
    for t in db.query(models.Trabajo).all():
        trabajos_por_cliente[t.cliente_id].append(t)

    movs_por_cliente = defaultdict(list)
    for m in db.query(models.Movimiento).all():
        movs_por_cliente[m.cliente_id].append(m)

    cheques_por_cliente = defaultdict(list)
    for ch in db.query(models.Cheque).all():
        if ch.cliente_id:  # Los cheques emitidos pueden no tener cliente.
            cheques_por_cliente[ch.cliente_id].append(ch)

    saldos = []
    for c in clientes:
        total_facturado, total_pagado, saldo = calcular_saldo_cliente(
            trabajos_por_cliente[c.id],
            movs_por_cliente[c.id],
            cheques_por_cliente[c.id],
        )
        saldos.append(schemas.SaldoResponse(
            cliente_id=c.id,
            total_facturado=total_facturado,
            total_pagado=total_pagado,
            saldo=saldo,
        ))
    return saldos

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