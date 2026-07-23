from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from datetime import date, datetime, timezone
from money import Q2, Q3
from calculos import calcular_saldo_trabajo
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


def _aplicar_saldo_favor(db: Session, db_trabajo: models.Trabajo) -> tuple[Decimal, Decimal]:
    """Cubre el saldo pendiente de un trabajo con el saldo a favor del cliente.

    El saldo a favor (la seña de un trabajo cancelado, un pago a cuenta sin
    imputar) ya es plata real: existe como Movimiento/Cheque. Crear un pago nuevo
    para "abonar" el trabajo la DUPLICARÍA (inflaría los ingresos y volvería a
    dejar el saldo del cliente en negativo). Por eso acá NO se crea plata: se
    RE-IMPUTAN esos pagos a este trabajo (se cambia su trabajo_id) y, si un pago
    es más grande que lo que falta cubrir, se PARTE: la porción que cubre el
    trabajo se imputa acá y el resto sigue como saldo a favor suelto.

    Re-imputar y partir preservan total_pagado y total_facturado del cliente, así
    que su saldo neto y los ingresos por período quedan idénticos: sólo cambia a
    qué trabajo está atribuida la plata.

    No hace commit: lo hace el endpoint. Devuelve (monto_aplicado, saldo_restante).

    Limitaciones (v1): sólo se toma como crédito la plata sin imputar o de
    trabajos cancelados (no la sobre-paga de un trabajo vivo); los cheques sólo se
    re-imputan enteros (un cheque es un documento físico, no se parte).
    """
    movimientos_cliente = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.cliente_id == db_trabajo.cliente_id)
        .all()
    )
    cheques_cliente = (
        db.query(models.Cheque)
        .filter(models.Cheque.cliente_id == db_trabajo.cliente_id)
        .all()
    )

    movs_del_trabajo = [m for m in movimientos_cliente if m.trabajo_id == db_trabajo.id]
    cheques_del_trabajo = [ch for ch in cheques_cliente if ch.trabajo_id == db_trabajo.id]
    saldo_pendiente = calcular_saldo_trabajo(
        db_trabajo.precio_venta, movs_del_trabajo, cheques_del_trabajo
    )
    if saldo_pendiente <= Decimal("0"):
        raise HTTPException(
            status_code=400,
            detail="El trabajo ya está pago: no hay saldo pendiente que cubrir.",
        )

    # Trabajos cancelados del cliente: la plata imputada a ellos quedó a favor.
    ids_cancelados = {
        row[0]
        for row in db.query(models.Trabajo.id)
        .filter(
            models.Trabajo.cliente_id == db_trabajo.cliente_id,
            models.Trabajo.estado == "Cancelado",
        )
        .all()
    }

    def es_movible(trabajo_id) -> bool:
        # Plata que no está cubriendo un trabajo vivo: sin imputar o de cancelado.
        return trabajo_id is None or trabajo_id in ids_cancelados

    # Los Movimiento "Pago" se pueden partir; los cheques sólo re-imputar enteros.
    movs_movibles = sorted(
        (
            m for m in movimientos_cliente
            if m.tipo == "Pago" and m.monto is not None and es_movible(m.trabajo_id)
        ),
        key=lambda m: m.fecha or datetime.min,
    )
    cheques_movibles = [
        ch for ch in cheques_cliente
        if getattr(ch, "clasificacion", "Recibido") == "Recibido"
        and ch.estado != "Rechazado"
        and ch.monto is not None
        and es_movible(ch.trabajo_id)
    ]

    total_movible = (
        sum((Q2(m.monto) for m in movs_movibles), Decimal("0"))
        + sum((Q2(ch.monto) for ch in cheques_movibles), Decimal("0"))
    )
    if total_movible <= Decimal("0"):
        raise HTTPException(
            status_code=400,
            detail="El cliente no tiene saldo a favor disponible para aplicar.",
        )

    monto_a_aplicar = min(saldo_pendiente, total_movible)
    restante = monto_a_aplicar

    # Leer el crédito y moverlo son pasos separados: dos requests concurrentes (un
    # doble clic) leen ambos el mismo pago a favor y lo aplican dos veces,
    # imputando más plata de la que existe y descuadrando la caja. Por eso cada
    # consumo se hace con un UPDATE condicional: la base es el único árbitro y gana
    # uno solo; el que pierde ve rowcount 0 y no re-aplica. Mismo criterio que el
    # guard de imprimir_orden.

    # Movimientos primero (divisibles): permiten cubrir el monto exacto.
    for m in movs_movibles:
        if restante <= Decimal("0"):
            break
        monto = Q2(m.monto)
        if monto <= restante:
            # Re-imputación entera. El WHERE sobre el trabajo_id original es el
            # candado: si otro request ya lo movió, el rowcount es 0 y no cuenta.
            candado_origen = (
                models.Movimiento.trabajo_id.is_(None)
                if m.trabajo_id is None
                else models.Movimiento.trabajo_id == m.trabajo_id
            )
            reclamado = (
                db.query(models.Movimiento)
                .filter(models.Movimiento.id == m.id, candado_origen)
                .update({"trabajo_id": db_trabajo.id}, synchronize_session=False)
            )
            if reclamado:
                restante = Q2(restante - monto)
        else:
            # Parte el pago: la porción que cubre el trabajo se imputa acá; el
            # resto queda en el movimiento original como saldo a favor suelto. La
            # fecha se hereda para no mover ingresos de período (calculos.py los
            # cuenta por fecha). El candado es el monto observado: si otro request
            # ya lo tocó, el monto cambió y el UPDATE no matchea.
            reclamado = (
                db.query(models.Movimiento)
                .filter(models.Movimiento.id == m.id, models.Movimiento.monto == m.monto)
                .update({"monto": Q2(monto - restante)}, synchronize_session=False)
            )
            if reclamado:
                db.add(models.Movimiento(
                    cliente_id=db_trabajo.cliente_id,
                    trabajo_id=db_trabajo.id,
                    monto=restante,
                    tipo="Pago",
                    metodo=m.metodo,
                    fecha=m.fecha,
                    descripcion=f"Aplicación de saldo a favor ({db_trabajo.descripcion_producto})",
                ))
                restante = Decimal("0")

    # Cheques: sólo enteros y sólo si entran dentro de lo que todavía falta.
    for ch in cheques_movibles:
        if restante <= Decimal("0"):
            break
        monto = Q2(ch.monto)
        if monto <= restante:
            candado_origen = (
                models.Cheque.trabajo_id.is_(None)
                if ch.trabajo_id is None
                else models.Cheque.trabajo_id == ch.trabajo_id
            )
            reclamado = (
                db.query(models.Cheque)
                .filter(models.Cheque.id == ch.id, candado_origen)
                .update({"trabajo_id": db_trabajo.id}, synchronize_session=False)
            )
            if reclamado:
                restante = Q2(restante - monto)

    aplicado = Q2(monto_a_aplicar - restante)
    if aplicado <= Decimal("0"):
        # No se movió nada: o el único crédito está en un cheque más grande que la
        # deuda (no se parte), o otra operación concurrente ya lo consumió.
        if cheques_movibles:
            detalle = "El saldo a favor está en un cheque que no se puede dividir para cubrir este trabajo."
        else:
            detalle = "No se pudo aplicar el saldo a favor: otra operación ya lo consumió. Volvé a intentarlo."
        raise HTTPException(status_code=400, detail=detalle)

    return aplicado, Q2(saldo_pendiente - aplicado)


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
            for row in db.query(models.ItemPresupuesto.trabajo_id)
            .filter(models.ItemPresupuesto.trabajo_id.isnot(None))
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

    # Sincronizar el estado con su Presupuesto madre (a través del ítem que
    # originó este trabajo). Con varios trabajos por presupuesto el estado de
    # cabecera es informativo: refleja el último trabajo que cambió.
    if trabajo_update.estado:
        db_item = db.query(models.ItemPresupuesto).filter(models.ItemPresupuesto.trabajo_id == trabajo_id).first()
        if db_item:
            db_item.presupuesto.estado = trabajo_update.estado

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

    tiene_presupuesto = db.query(models.ItemPresupuesto).filter(models.ItemPresupuesto.trabajo_id == trabajo_id).first()
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

    # Mismo criterio que el PUT: el presupuesto madre sigue el estado del trabajo
    # (a través del ítem que originó este trabajo).
    db_item = db.query(models.ItemPresupuesto).filter(models.ItemPresupuesto.trabajo_id == trabajo_id).first()
    if db_item:
        db_item.presupuesto.estado = "En Diseño"

    db.commit()
    db.refresh(db_trabajo)
    return db_trabajo


@router.post("/{trabajo_id}/aplicar-saldo-favor", response_model=schemas.AplicarSaldoFavorResponse)
def aplicar_saldo_favor(trabajo_id: str, db: Session = Depends(get_db)):
    """Cubre el saldo pendiente de un trabajo con el saldo a favor del cliente.

    No crea un pago nuevo (eso duplicaría la plata): re-imputa a este trabajo los
    pagos que ya existen a favor del cliente. Ver _aplicar_saldo_favor.
    """
    db_trabajo = db.query(models.Trabajo).filter(models.Trabajo.id == trabajo_id).first()
    if not db_trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if db_trabajo.estado == "Cancelado":
        raise HTTPException(
            status_code=400,
            detail="No se puede aplicar saldo a favor a un trabajo cancelado.",
        )

    monto_aplicado, saldo_pendiente_restante = _aplicar_saldo_favor(db, db_trabajo)
    db.commit()
    return schemas.AplicarSaldoFavorResponse(
        monto_aplicado=monto_aplicado,
        saldo_pendiente_restante=saldo_pendiente_restante,
    )


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