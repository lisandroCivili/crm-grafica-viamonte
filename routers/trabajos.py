from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from datetime import date, datetime, timezone
from money import Q3
from orden_pdf import construir_orden_pdf

router = APIRouter(prefix="/api/trabajos", tags=["Trabajos"])


def _generar_numero_orden(db: Session) -> str:
    """Número correlativo de orden: OP-000001, OP-000002...

    Mismo criterio que generar_numero_secuencia() de presupuestos, con prefijo
    propio para no confundir una orden con un presupuesto. Se asigna recién al
    imprimir, así los trabajos que nunca llegan a producción no dejan huecos.
    """
    ultimo = (
        db.query(models.Trabajo)
        .filter(models.Trabajo.numero_orden.isnot(None))
        .order_by(models.Trabajo.numero_orden.desc())
        .first()
    )

    if not ultimo or not ultimo.numero_orden:
        return "OP-000001"

    partes = ultimo.numero_orden.split("-")
    if len(partes) == 2:
        nuevo_numero = str(int(partes[1]) + 1).zfill(6)
        return f"OP-{nuevo_numero}"

    return "OP-000001"


def _validar_cambio_estado(db_trabajo: models.Trabajo, nuevo_estado: str):
    """Reglas de flujo de la orden. Lanza HTTPException si la transición no va."""
    if nuevo_estado not in models.ESTADOS_TRABAJO:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido: '{nuevo_estado}'. Válidos: {', '.join(models.ESTADOS_TRABAJO)}.",
        )

    # Pasar a diseño exige registrar el monto abonado, y eso no entra en un PUT
    # genérico sin mezclarle cobranza al schema. Va por su endpoint.
    if nuevo_estado == "En Diseño" and db_trabajo.estado != "En Diseño":
        raise HTTPException(
            status_code=400,
            detail="Para pasar a En Diseño usá Iniciar Diseño: hay que registrar el monto abonado.",
        )

    # La orden se imprime ANTES de que el trabajo baje a máquina.
    if nuevo_estado == "En Producción" and not db_trabajo.orden_impresa:
        raise HTTPException(
            status_code=400,
            detail="Imprimí la orden de producción antes de mandar el trabajo a producción.",
        )


def _buscar_papel(db: Session, papel_id: str) -> models.ArticuloStock:
    """Trae el artículo de stock y verifica que sea papel medido en pliegos.

    El selector de papel históricamente listaba TODO el stock, así que nada
    impedía vincular una orden a un bidón de tinta y restarle "3 pliegos".
    Las compras por Kg ya se normalizan a "Pliegos" en stock.py, así que la
    validación no deja afuera al papel comprado por peso.
    """
    articulo = (
        db.query(models.ArticuloStock)
        .filter(models.ArticuloStock.id == papel_id)
        .first()
    )
    if not articulo:
        raise HTTPException(status_code=404, detail="El papel indicado no existe en el stock.")

    if articulo.unidad != "Pliegos":
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{articulo.nombre}' se mide en {articulo.unidad}, no en pliegos. "
                "Elegí un papel del stock."
            ),
        )
    return articulo


def _validar_pliegos(cantidad_pliegos) -> None:
    """Los pliegos son unidades físicas: no existe medio pliego.

    Sólo se aplica sobre lo que entra por la API. _descontar_papel no lo usa
    porque hay trabajos históricos con cantidades fraccionarias y el descuento
    no debe romperse por eso.
    """
    if cantidad_pliegos is None:
        return

    pliegos = Q3(cantidad_pliegos)
    if pliegos <= Decimal("0"):
        raise HTTPException(status_code=400, detail="La cantidad de pliegos debe ser mayor a cero.")
    if pliegos != pliegos.to_integral_value():
        raise HTTPException(
            status_code=400,
            detail=f"La cantidad de pliegos debe ser un número entero (recibido: {pliegos}).",
        )


def _validar_papel(db: Session, papel_id, cantidad_pliegos) -> None:
    """Valida el papel elegido, si se eligió uno. Compartido con presupuestos.

    Los dos campos van juntos: un papel sin pliegos no descuenta nada (el guard
    de _descontar_papel lo saltea) y el stock queda desfasado en silencio, que
    es el mismo síntoma que tenía el presupuesto convertido. Pliegos sin papel
    no tienen a qué aplicarse.

    Dejar los dos en null sí es válido: significa que el papel lo trae el
    cliente o se compra en el momento, y entonces no hay nada que descontar.
    """
    if papel_id and cantidad_pliegos is None:
        raise HTTPException(
            status_code=400,
            detail="Elegiste un papel del stock: indicá cuántos pliegos consume, si no la orden no puede descontarlo.",
        )
    if cantidad_pliegos is not None and not papel_id:
        raise HTTPException(
            status_code=400,
            detail="Cargaste una cantidad de pliegos pero no elegiste de qué papel del stock descontarlos.",
        )
    if papel_id:
        _buscar_papel(db, papel_id)
        _validar_pliegos(cantidad_pliegos)


def _descontar_papel(db: Session, db_trabajo: models.Trabajo, numero_orden: str, forzar: bool):
    """Descuenta del stock el papel que consume la orden y lo deja en el historial.

    No hace commit: lo hace el endpoint, para que descuento y marcado de la
    orden entren o fallen juntos.
    """
    if not db_trabajo.papel_id or not db_trabajo.cantidad_pliegos:
        return  # Papel del cliente o comprado en el momento: no hay qué descontar.

    articulo = _buscar_papel(db, db_trabajo.papel_id)

    pliegos = Q3(db_trabajo.cantidad_pliegos)
    if pliegos <= Decimal("0"):
        return

    faltante = pliegos - articulo.cantidad
    if faltante > Decimal("0") and not forzar:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No alcanza el papel '{articulo.nombre}': hay {articulo.cantidad} "
                f"{articulo.unidad} y la orden necesita {pliegos}. Faltan {faltante}."
            ),
        )

    motivo = f"Orden {numero_orden}"
    if faltante > Decimal("0"):
        motivo += " (forzado, stock insuficiente)"

    # Mismo patrón que el PATCH de stock: la cantidad nunca se toca sin historial.
    db.add(models.HistorialStock(articulo_id=articulo.id, diferencia=-pliegos, motivo=motivo))
    articulo.cantidad = Q3(articulo.cantidad - pliegos)
    articulo.ultima_actualizacion = date.today()


def _devolver_papel(db: Session, db_trabajo: models.Trabajo):
    """Reingresa al stock los pliegos que consumió una orden que se cancela.

    Espejo de _descontar_papel. Tampoco hace commit: lo hace el endpoint, para
    que el cambio de estado y el reingreso entren o fallen juntos.

    Idempotente vía papel_devuelto: cancelar, reactivar y volver a cancelar no
    duplica el reingreso. Nota: un trabajo reactivado tampoco vuelve a
    descontar, porque orden_impresa sigue en True y el guard de imprimir_orden
    no redescuenta. Rehacer el ciclo completo imprimir/cancelar/reimprimir
    exige repensar ambos guards juntos.
    """
    if db_trabajo.papel_devuelto:
        return  # Ya se devolvió en una cancelación anterior.
    if not db_trabajo.orden_impresa:
        return  # Nunca se descontó: no hay nada que reingresar.
    if not db_trabajo.papel_id or not db_trabajo.cantidad_pliegos:
        return

    articulo = _buscar_papel(db, db_trabajo.papel_id)

    pliegos = Q3(db_trabajo.cantidad_pliegos)
    if pliegos <= Decimal("0"):
        return

    motivo = f"Devolución por cancelación {db_trabajo.numero_orden or 'orden sin número'}"
    db.add(models.HistorialStock(articulo_id=articulo.id, diferencia=pliegos, motivo=motivo))
    articulo.cantidad = Q3(articulo.cantidad + pliegos)
    articulo.ultima_actualizacion = date.today()
    db_trabajo.papel_devuelto = True


@router.post("/", response_model=schemas.TrabajoResponse)
def crear_trabajo(trabajo: schemas.TrabajoCreate, db: Session = Depends(get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == trabajo.cliente_id).first()
    if not db_cliente:
        raise HTTPException(status_code=404, detail="El cliente indicado no existe.")

    _validar_papel(db, trabajo.papel_id, trabajo.cantidad_pliegos)

    nuevo_trabajo = models.Trabajo(**trabajo.model_dump())
    db.add(nuevo_trabajo)
    db.commit()
    db.refresh(nuevo_trabajo)
    return nuevo_trabajo

@router.get("/", response_model=list[schemas.TrabajoResponse])
def listar_trabajos(estado: str = None, sin_presupuesto: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Trabajo)
    # Filtro ideal para el Kanban (ej: traer solo los "En Diseño")
    if estado:
        query = query.filter(models.Trabajo.estado == estado)
    trabajos = query.all()

    # Sólo los trabajos que todavía no tienen un presupuesto asociado. Alimenta
    # el selector "asociar a trabajo existente" del form de presupuesto, el
    # distintivo del Kanban y la tarjeta de "no contemplados" del dashboard.
    if sin_presupuesto:
        ids_con_presupuesto = {
            row[0]
            for row in db.query(models.Presupuesto.trabajo_id)
            .filter(models.Presupuesto.trabajo_id.isnot(None))
            .all()
        }
        trabajos = [t for t in trabajos if t.id not in ids_con_presupuesto]
    return trabajos

@router.put("/{trabajo_id}", response_model=schemas.TrabajoResponse)
def actualizar_trabajo(
    trabajo_id: str,
    trabajo_update: schemas.TrabajoUpdate,
    devolver_papel: bool = False,
    db: Session = Depends(get_db),
):
    """Actualiza un trabajo.

    devolver_papel sólo tiene efecto al pasar a 'Cancelado': reingresa al stock
    los pliegos que había descontado la orden impresa. Va por query param (y no
    en el schema) por el mismo criterio que 'forzar' en imprimir-orden: es una
    decisión del operador en el momento, no un dato del trabajo.
    """
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    update_data = trabajo_update.model_dump(exclude_unset=True)

    if trabajo_update.estado:
        _validar_cambio_estado(db_trabajo, trabajo_update.estado)

    # La orden ya impresa descontó stock contra estos valores: si cambiaran, el
    # descuento quedaría mintiendo. Mismo criterio que un presupuesto convertido.
    if db_trabajo.orden_impresa:
        for campo in ("papel_id", "cantidad_pliegos"):
            if campo in update_data and update_data[campo] != getattr(db_trabajo, campo):
                raise HTTPException(
                    status_code=400,
                    detail="No se puede cambiar el papel ni los pliegos: la orden ya fue impresa y descontó stock.",
                )

    # El PUT no validaba nada del papel: se podía dejar un trabajo apuntando a un
    # artículo inexistente o con la unidad equivocada. Validamos contra el valor
    # efectivo (lo que viene en el update, o lo que ya tenía el trabajo).
    if "papel_id" in update_data or "cantidad_pliegos" in update_data:
        _validar_papel(
            db,
            update_data.get("papel_id", db_trabajo.papel_id),
            update_data.get("cantidad_pliegos", db_trabajo.cantidad_pliegos),
        )

    for key, value in update_data.items():
        setattr(db_trabajo, key, value)

    # MAGIA: Si el estado pasa a Diseño o Producción, clavamos la fecha de hoy
    if trabajo_update.estado in ["En Diseño", "En Producción"] and not db_trabajo.fecha_comienzo:
        db_trabajo.fecha_comienzo = date.today()
        
    # El papel de una orden cancelada vuelve al stock si el operador lo pide.
    # Dentro de la misma transacción que el cambio de estado.
    if trabajo_update.estado == "Cancelado" and devolver_papel:
        _devolver_papel(db, db_trabajo)

    # Sincronizar el estado con su Presupuesto madre
    if trabajo_update.estado:
        db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.trabajo_id == trabajo_id).first()
        if db_presupuesto:
            db_presupuesto.estado = trabajo_update.estado

    db.commit()
    db.refresh(db_trabajo)
    return db_trabajo

@router.delete("/{trabajo_id}")
def eliminar_trabajo(trabajo_id: str, db: Session = Depends(get_db)):
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    tiene_movimientos = db.query(models.Movimiento).filter(models.Movimiento.trabajo_id == trabajo_id).first()
    if tiene_movimientos:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el trabajo tiene pagos registrados. Cancelalo en su lugar.")

    tiene_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.trabajo_id == trabajo_id).first()
    if tiene_presupuesto:
        raise HTTPException(status_code=400, detail="No se puede eliminar: hay un presupuesto convertido a este trabajo.")

    tiene_gastos = db.query(models.Gasto).filter(models.Gasto.trabajo_id == trabajo_id).first()
    if tiene_gastos:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el trabajo tiene gastos asociados.")

    # Los cheques también apuntan al trabajo por FK y faltaban en esta lista: el
    # DELETE llegaba a la base y salía por IntegrityError como un 500 sin
    # explicación. Un cheque imputado es plata comprometida, mismo criterio que
    # un pago: el trabajo se cancela, no se borra.
    tiene_cheques = db.query(models.Cheque).filter(models.Cheque.trabajo_id == trabajo_id).first()
    if tiene_cheques:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el trabajo tiene cheques imputados. Cancelalo en su lugar.")

    db.query(models.Nota).filter(models.Nota.trabajo_id == trabajo_id).update({"trabajo_id": None})
    db.delete(db_trabajo)
    db.commit()
    return {"mensaje": "Trabajo eliminado"}


@router.post("/{trabajo_id}/iniciar-diseno", response_model=schemas.TrabajoResponse)
def iniciar_diseno(trabajo_id: str, datos: schemas.IniciarDisenoRequest, db: Session = Depends(get_db)):
    """Pasa un trabajo Aprobado a En Diseño registrando lo que abonó el cliente.

    El monto no se guarda en el Trabajo: se registra como Movimiento de tipo
    'Pago', que es como el sistema ya calcula los saldos (calculos.py). Puede
    ser un pago parcial. Si no hubo seña, queda el motivo asentado como Nota.
    """
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if db_trabajo.estado != "Aprobado":
        raise HTTPException(
            status_code=400,
            detail=f"Sólo se puede iniciar el diseño de un trabajo Aprobado (este está en '{db_trabajo.estado}').",
        )

    if datos.monto > Decimal("0"):
        if (datos.metodo or "") == "Cheque":
            # La seña con cheque no es plata todavía: se registra como Cheque
            # recibido (imputado al trabajo) y recién cuenta como ingreso al
            # cobrarse. Así se evita el doble conteo con los movimientos.
            db.add(models.Cheque(
                cliente_id=db_trabajo.cliente_id,
                clasificacion="Recibido",
                trabajo_id=db_trabajo.id,
                banco=datos.banco,
                numero=datos.numero,
                monto=datos.monto,
                fecha_emision=date.today(),
                fecha_cobro=datos.fecha_cobro,
                estado="En Cartera",
            ))
        else:
            db.add(models.Movimiento(
                cliente_id=db_trabajo.cliente_id,
                trabajo_id=db_trabajo.id,
                monto=datos.monto,
                tipo="Pago",
                metodo=datos.metodo,
                descripcion=f"Seña — inicio de diseño ({db_trabajo.descripcion_producto})",
            ))
    else:
        # Sin seña: el motivo es obligatorio (lo valida IniciarDisenoRequest) y
        # queda asentado en el historial del cliente.
        db.add(models.Nota(
            cliente_id=db_trabajo.cliente_id,
            trabajo_id=db_trabajo.id,
            texto=f"Inicio de diseño sin seña: {datos.motivo.strip()}",
        ))

    db_trabajo.estado = "En Diseño"
    if not db_trabajo.fecha_comienzo:
        db_trabajo.fecha_comienzo = date.today()

    # Mismo criterio que el PUT: el presupuesto madre sigue el estado del trabajo.
    db_presupuesto = db.query(models.Presupuesto).filter(models.Presupuesto.trabajo_id == trabajo_id).first()
    if db_presupuesto:
        db_presupuesto.estado = "En Diseño"

    db.commit()
    db.refresh(db_trabajo)
    return db_trabajo


@router.post("/{trabajo_id}/imprimir-orden")
def imprimir_orden(trabajo_id: str, forzar: bool = False, db: Session = Depends(get_db)):
    """Emite la orden de producción en PDF y descuenta el papel del stock.

    El descuento pasa exactamente acá, la primera vez. orden_impresa es el guard
    de idempotencia: reimprimir devuelve el mismo PDF sin volver a tocar el stock.

    forzar=true permite emitir la orden aunque no alcance el papel (se compra en
    el momento), dejando constancia en el historial de stock.
    """
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if not db_trabajo.orden_impresa:
        numero_orden = _generar_numero_orden(db)

        # El reclamo de la impresión es un UPDATE condicional, y no un
        # `db_trabajo.orden_impresa = True`, porque leer el flag y escribirlo
        # son dos pasos: un doble clic mete dos requests en el medio, ambos lo
        # leen en False y ambos descuentan. El síntoma no es stock de menos
        # (las dos sesiones leen la misma cantidad y una pisa a la otra) sino
        # un historial con dos descuentos para una sola orden: el papel y la
        # auditoría dejan de coincidir. Acá gana uno solo: el WHERE lo resuelve
        # la base, que es el único punto donde los dos requests se cruzan.
        reclamada = (
            db.query(models.Trabajo)
            .filter(models.Trabajo.id == trabajo_id, models.Trabajo.orden_impresa.isnot(True))
            .update(
                {
                    "orden_impresa": True,
                    "numero_orden": numero_orden,
                    "fecha_orden_impresa": datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )

        if reclamada:
            # Si el papel no alcanza, _descontar_papel corta con un 400 y el
            # reclamo se va con la transacción: la orden queda sin imprimir.
            _descontar_papel(db, db_trabajo, numero_orden, forzar)
            db.commit()
        else:
            # Perdimos la carrera: el otro request ya la imprimió y descontó.
            db.rollback()
        db.refresh(db_trabajo)

    pdf = construir_orden_pdf(db_trabajo, db_trabajo.cliente, db_trabajo.papel)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="orden_{db_trabajo.numero_orden}.pdf"'},
    )