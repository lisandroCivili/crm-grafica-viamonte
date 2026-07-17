from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from calculos import sumar_detalles_costos, calcular_precio_presupuesto, calcular_saldo_trabajo

router = APIRouter(prefix="/api/presupuestos", tags=["Presupuestos"])


def _fecha(valor) -> str:
    """Formatea una fecha para la tabla del informe; '' si no hay."""
    return valor.strftime("%d/%m/%Y") if valor else ""

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
    # El cliente es opcional (borrador sin cliente). Solo si viene, validamos que exista.
    if presupuesto.cliente_id:
        db_cliente = db.query(models.Cliente).filter(models.Cliente.id == presupuesto.cliente_id).first()
        if not db_cliente:
            raise HTTPException(status_code=404, detail="El cliente indicado no existe.")

    datos = presupuesto.model_dump()

    # Asociación a un trabajo existente sin presupuesto: recién con esto el
    # trabajo aporta ganancia al dashboard.
    if presupuesto.trabajo_id:
        db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == presupuesto.trabajo_id).first()
        if not db_trabajo:
            raise HTTPException(status_code=404, detail="El trabajo indicado no existe.")
        ya_tiene = db.query(models.Presupuesto).filter(models.Presupuesto.trabajo_id == presupuesto.trabajo_id).first()
        if ya_tiene:
            raise HTTPException(status_code=409, detail="Ese trabajo ya tiene un presupuesto asociado.")
        # El presupuesto nace ya convertido y hereda el estado del trabajo.
        datos["convertido_a_trabajo"] = True
        datos["estado"] = db_trabajo.estado

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


@router.get("/informe-trabajos", response_model=list[schemas.InformeTrabajoRow])
def informe_trabajos(db: Session = Depends(get_db)):
    """Informe general de trabajos a clientes.

    Se arma a partir de TODOS los presupuestos. Si el presupuesto ya se convirtió
    a trabajo, las columnas de producción (colores, entrega, estado, cobrado…)
    salen del trabajo; si sigue siendo presupuesto, el estado queda 'Pendiente'.

    Una sola consulta por tabla y cruce en memoria para no caer en N+1.
    """
    presupuestos = db.query(models.Presupuesto).order_by(models.Presupuesto.fecha_creacion.desc()).all()
    trabajos = {t.id: t for t in db.query(models.Trabajo).all()}
    clientes = {c.id: c for c in db.query(models.Cliente).all()}

    movs_por_trabajo = defaultdict(list)
    for m in db.query(models.Movimiento).all():
        if m.trabajo_id:
            movs_por_trabajo[m.trabajo_id].append(m)

    # Cheques recibidos imputados a un trabajo: cuentan para el flag 'cobrado'.
    cheques_por_trabajo = defaultdict(list)
    for ch in db.query(models.Cheque).all():
        if ch.trabajo_id:
            cheques_por_trabajo[ch.trabajo_id].append(ch)

    filas: list[schemas.InformeTrabajoRow] = []
    for p in presupuestos:
        cliente = clientes.get(p.cliente_id)
        trabajo = trabajos.get(p.trabajo_id) if p.trabajo_id else None

        # Valores por defecto para un presupuesto todavía no convertido.
        nro_trabajo = "-"
        fecha_entrada = _fecha(p.fecha_creacion)
        colores = ""
        fecha_entrega = ""
        dias_produccion = "-"
        estado = "Pendiente"
        cobrado = False
        observaciones = ""

        if trabajo is not None:
            nro_trabajo = trabajo.numero_orden or "-"
            fecha_entrada = _fecha(trabajo.fecha_creacion) or fecha_entrada
            colores = trabajo.tintas or ""
            fecha_entrega = _fecha(trabajo.fecha_entrega)
            estado = trabajo.estado or "Pendiente"
            observaciones = trabajo.notas_iniciales or ""

            if trabajo.fecha_comienzo and trabajo.fecha_entrega:
                dias_produccion = str((trabajo.fecha_entrega - trabajo.fecha_comienzo).days)

            saldo = calcular_saldo_trabajo(
                trabajo.precio_venta,
                movs_por_trabajo.get(trabajo.id, []),
                cheques_por_trabajo.get(trabajo.id, []),
            )
            cobrado = saldo <= 0

        filas.append(schemas.InformeTrabajoRow(
            nro_trabajo=nro_trabajo,
            fecha_entrada=fecha_entrada,
            cliente=cliente.nombre_completo if cliente else "Sin cliente",
            descripcion_material=p.material or "",
            gramaje=p.gramaje or "",
            colores=colores,
            cantidad=p.cantidad,
            fecha_entrega=fecha_entrega,
            dias_produccion=dias_produccion,
            estado=estado,
            cobrado=cobrado,
            observaciones=observaciones,
        ))

    return filas


@router.put("/{presupuesto_id}", response_model=schemas.PresupuestoResponse)
def actualizar_presupuesto(presupuesto_id: str, presupuesto_update: schemas.PresupuestoUpdate, db: Session = Depends(get_db)):
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if db_presupuesto.convertido_a_trabajo:
        raise HTTPException(status_code=400, detail="No se puede editar: este presupuesto ya fue convertido a trabajo.")

    update_data = presupuesto_update.model_dump(exclude_unset=True)

    # Solo validamos el cliente si se está asignando uno (permite dejarlo/volverlo a borrador).
    if update_data.get("cliente_id"):
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
