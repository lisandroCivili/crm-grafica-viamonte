import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from calculos import sumar_detalles_costos, calcular_saldo_trabajo
from money import Q2
from presupuesto_pdf import construir_presupuesto_pdf
# El papel del presupuesto se valida con las mismas reglas que el del trabajo
# (que exista, que se mida en pliegos, que la cantidad sea un entero positivo y
# que papel y pliegos vayan juntos). Se importa en vez de duplicarla para que no
# puedan divergir: el presupuesto le pasa el papel al trabajo al convertirse, así
# que si las reglas difirieran, un presupuesto válido podría producir un trabajo
# inválido.
from routers.trabajos import _validar_papel

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


def _construir_item(db: Session, item: schemas.ItemPresupuestoCreate, orden: int) -> models.ItemPresupuesto:
    """Valida y arma un ItemPresupuesto listo para agregar (sin commitear).

    El papel se valida con las mismas reglas que el trabajo. El costo se deriva
    de detalles_costos: es la fuente de verdad del backend, no se confía en lo
    que mande el cliente. El precio_unitario se persiste tal cual (es lo que ve
    el cliente); el total se calcula al leer, no se guarda.
    """
    _validar_papel(db, item.papel_id, item.cantidad_pliegos)
    costo_materiales = sumar_detalles_costos(item.detalles_costos)
    return models.ItemPresupuesto(
        orden=orden,
        descripcion=item.descripcion,
        cantidad=item.cantidad,
        precio_unitario=item.precio_unitario,
        detalles_costos=item.detalles_costos,
        costo_materiales=costo_materiales,
        margen_ganancia=item.margen_ganancia,
        material=item.material,
        gramaje=item.gramaje,
        papel_id=item.papel_id,
        cantidad_pliegos=item.cantidad_pliegos,
    )


@router.post("/", response_model=schemas.PresupuestoResponse)
def crear_presupuesto(presupuesto: schemas.PresupuestoCreate, db: Session = Depends(get_db)):
    # El cliente es opcional (borrador sin cliente). Solo si viene, validamos que exista.
    if presupuesto.cliente_id:
        db_cliente = db.query(models.Cliente).filter(models.Cliente.id == presupuesto.cliente_id).first()
        if not db_cliente:
            raise HTTPException(status_code=404, detail="El cliente indicado no existe.")

    nuevo_presupuesto = models.Presupuesto(
        cliente_id=presupuesto.cliente_id,
        version_de=presupuesto.version_de,
        estado=presupuesto.estado,
        convertido_a_trabajo=presupuesto.convertido_a_trabajo,
        fecha_creacion=presupuesto.fecha_creacion,
        numero_secuencia=generar_numero_secuencia(db),
    )
    nuevo_presupuesto.items = [
        _construir_item(db, item, orden=i)
        for i, item in enumerate(presupuesto.items)
    ]

    # Asociación a un trabajo existente sin presupuesto: recién con esto el
    # trabajo aporta ganancia al dashboard. Solo tiene sentido con UN ítem: es
    # ese ítem el que se vincula al trabajo ya creado.
    if presupuesto.trabajo_asociado_id:
        if len(nuevo_presupuesto.items) != 1:
            raise HTTPException(
                status_code=400,
                detail="Asociar a un trabajo existente solo se puede con un presupuesto de un único ítem.",
            )
        db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == presupuesto.trabajo_asociado_id).first()
        if not db_trabajo:
            raise HTTPException(status_code=404, detail="El trabajo indicado no existe.")
        ya_tiene = db.query(models.ItemPresupuesto).filter(
            models.ItemPresupuesto.trabajo_id == presupuesto.trabajo_asociado_id
        ).first()
        if ya_tiene:
            raise HTTPException(status_code=409, detail="Ese trabajo ya tiene un presupuesto asociado.")
        # El presupuesto nace ya convertido y hereda el estado del trabajo.
        nuevo_presupuesto.items[0].trabajo_id = presupuesto.trabajo_asociado_id
        nuevo_presupuesto.convertido_a_trabajo = True
        nuevo_presupuesto.estado = db_trabajo.estado

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

    # Una fila por ÍTEM: el informe siempre fue "un renglón por producto", y
    # ahora cada ítem es (o será) su propio trabajo.
    filas: list[schemas.InformeTrabajoRow] = []
    for p in presupuestos:
        cliente = clientes.get(p.cliente_id)
        for item in p.items:
            trabajo = trabajos.get(item.trabajo_id) if item.trabajo_id else None

            # Valores por defecto para un ítem todavía no convertido.
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
                descripcion_material=item.material or "",
                gramaje=item.gramaje or "",
                colores=colores,
                cantidad=item.cantidad,
                fecha_entrega=fecha_entrega,
                dias_produccion=dias_produccion,
                estado=estado,
                cobrado=cobrado,
                observaciones=observaciones,
            ))

    return filas


def _nombre_archivo_pdf(presupuesto: models.Presupuesto) -> str:
    """Nombre de descarga: Presupuesto_<Cliente>_<dd-mm-aaaa>.pdf.

    Sanitiza el nombre del cliente igual que el frontend (sólo alfanumérico,
    lo demás a '_') para que sirva de nombre de archivo en cualquier sistema.
    """
    cliente = presupuesto.cliente
    crudo = cliente.nombre_completo if cliente else "SinCliente"
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", crudo).strip("_") or "SinCliente"
    fecha = presupuesto.fecha_creacion.strftime("%d-%m-%Y") if presupuesto.fecha_creacion else date.today().strftime("%d-%m-%Y")
    return f"Presupuesto_{limpio}_{fecha}.pdf"


@router.get("/{presupuesto_id}/pdf-cliente")
def pdf_cliente(presupuesto_id: str, db: Session = Depends(get_db)):
    """Genera el PDF del presupuesto para el cliente (mismo patrón que la orden).

    Trae el presupuesto con sus ítems + cliente y devuelve el PDF armado en el
    backend con ReportLab. Reemplaza al armado con html2pdf del frontend.
    """
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    pdf = construir_presupuesto_pdf(db_presupuesto, db_presupuesto.cliente)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_nombre_archivo_pdf(db_presupuesto)}"'},
    )


@router.put("/{presupuesto_id}", response_model=schemas.PresupuestoResponse)
def actualizar_presupuesto(presupuesto_id: str, presupuesto_update: schemas.PresupuestoUpdate, db: Session = Depends(get_db)):
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if db_presupuesto.convertido_a_trabajo:
        raise HTTPException(status_code=400, detail="No se puede editar: este presupuesto ya fue convertido a trabajo.")

    update_data = presupuesto_update.model_dump(exclude_unset=True)

    # Solo validamos el cliente si se está asignando uno (permite dejarlo/volverlo a borrador).
    if "cliente_id" in update_data:
        if update_data["cliente_id"]:
            db_cliente = db.query(models.Cliente).filter(models.Cliente.id == update_data["cliente_id"]).first()
            if not db_cliente:
                raise HTTPException(status_code=404, detail="El cliente indicado no existe.")
        db_presupuesto.cliente_id = update_data["cliente_id"]

    if "estado" in update_data:
        db_presupuesto.estado = update_data["estado"]

    # Si viene 'items', reemplaza toda la lista: el cascade delete-orphan borra
    # los ítems viejos. Cada ítem se valida y se le recalcula el costo igual que
    # al crear.
    if presupuesto_update.items is not None:
        if not presupuesto_update.items:
            raise HTTPException(status_code=400, detail="El presupuesto tiene que tener al menos un ítem.")
        db_presupuesto.items = [
            _construir_item(db, item, orden=i)
            for i, item in enumerate(presupuesto_update.items)
        ]

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


@router.post("/{presupuesto_id}/convertir", response_model=list[schemas.TrabajoResponse])
def convertir_presupuesto(presupuesto_id: str, db: Session = Depends(get_db)):
    """Convierte un presupuesto en trabajos en una sola transacción.

    Crea UN TRABAJO POR ÍTEM (cada producto se produce por separado) y marca el
    presupuesto como convertido con un único commit: si algo falla en el medio no
    quedan ni trabajos huérfanos ni presupuesto marcado a medias. Devuelve la
    lista de trabajos creados.
    """
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if not db_presupuesto.cliente_id:
        raise HTTPException(status_code=400, detail="Asigná un cliente al presupuesto antes de convertirlo.")

    if db_presupuesto.convertido_a_trabajo or any(i.trabajo_id for i in db_presupuesto.items):
        raise HTTPException(status_code=409, detail="Este presupuesto ya fue convertido a trabajo.")

    trabajos_creados = []
    for item in db_presupuesto.items:
        nuevo_trabajo = models.Trabajo(
            cliente_id=db_presupuesto.cliente_id,
            descripcion_producto=item.descripcion,
            cantidad=item.cantidad,
            # El precio de venta del trabajo es el total del ítem (lo que ve el
            # cliente); el costo congelado sale de los costos internos del ítem.
            precio_venta=Q2(item.cantidad * item.precio_unitario),
            costo_total_materiales=item.costo_materiales or Decimal("0"),
            notas_iniciales=f"Viene del presupuesto {db_presupuesto.numero_secuencia or 's/n'}",
            fecha_creacion=date.today(),
            estado="Aprobado",
            # El papel viaja con el trabajo: sin esto la orden de producción nunca
            # descontaba stock. papel_tipo (texto de la boleta) sale de material.
            papel_id=item.papel_id,
            cantidad_pliegos=item.cantidad_pliegos,
            papel_tipo=item.material,
        )
        db.add(nuevo_trabajo)
        db.flush()  # Asigna el id del trabajo sin commitear todavía.
        item.trabajo_id = nuevo_trabajo.id
        trabajos_creados.append(nuevo_trabajo)

    db_presupuesto.convertido_a_trabajo = True
    db_presupuesto.estado = "Aprobado"

    db.commit()
    for t in trabajos_creados:
        db.refresh(t)
    return trabajos_creados


@router.put("/{presupuesto_id}/convertir/{trabajo_id}", response_model=schemas.PresupuestoResponse)
def marcar_convertido(presupuesto_id: str, trabajo_id: str, db: Session = Depends(get_db)):
    """Asocia un presupuesto (de un solo ítem) a un trabajo ya existente.

    Sólo tiene sentido con un único ítem: es ese ítem el que se vincula.
    """
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.id == presupuesto_id).first()
    if not db_presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if len(db_presupuesto.items) != 1:
        raise HTTPException(
            status_code=400,
            detail="Asociar a un trabajo existente solo se puede con un presupuesto de un único ítem.",
        )

    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="El trabajo indicado no existe.")

    if db_presupuesto.convertido_a_trabajo or db_presupuesto.items[0].trabajo_id:
        raise HTTPException(status_code=409, detail="Este presupuesto ya fue convertido a trabajo.")

    ya_tiene = db.query(models.ItemPresupuesto).filter(
        models.ItemPresupuesto.trabajo_id == trabajo_id,
    ).first()
    if ya_tiene:
        raise HTTPException(status_code=409, detail="Ese trabajo ya tiene un presupuesto asociado.")

    db_presupuesto.items[0].trabajo_id = trabajo_id
    db_presupuesto.convertido_a_trabajo = True
    db_presupuesto.estado = "Aprobado"
    db.commit()
    db.refresh(db_presupuesto)
    return db_presupuesto
