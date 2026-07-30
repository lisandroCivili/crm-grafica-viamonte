"""Remitos (Entrega): el papel que firma el cliente al retirar mercadería.

Es su propio recurso y no un sub-recurso de /trabajos porque un remito puede
combinar VARIOS trabajos de un mismo cliente en una sola entrega física (ej:
el cliente retira parte de dos pedidos distintos en la misma visita) — no
tiene un único trabajo_id en el que anidarse. La cabecera es Entrega
(cliente, número, fecha) y el detalle son las filas ItemEntrega (trabajo +
cantidad), mismo patrón que Presupuesto/ItemPresupuesto.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models, schemas
from auditoria import asentar
from database import get_db
from pdf import construir_entrega_pdf
from routers._comun import obtener_o_404
from trabajos_comun import resumen_trabajo, saldo_pendiente_entrega
from seguridad import TODOS_LOS_ROLES, requiere_rol, usuario_actual

router = APIRouter(
    prefix="/api/entregas",
    tags=["Entregas"],
    dependencies=[Depends(requiere_rol(*TODOS_LOS_ROLES))],
)

# Se audita por cada Trabajo tocado (entra en su propia historia), no por el
# remito en sí: no hay pantalla de auditoría para "Entrega" y lo que a Facundo
# le interesa rastrear es qué le pasó a cada trabajo.
ENTIDAD_TRABAJO = "Trabajo"

# Cuántas filas reales entran en la mitad de la hoja del talonario (ver
# pdf/entrega.py) sin que el remito se corte. Un remito con más trabajos que
# esto tiene que dividirse en dos.
MAX_ITEMS_POR_REMITO = 6


def _generar_numero_remito(db: Session) -> str:
    """Número correlativo del remito: RE-000001, RE-000002..."""
    ultimo = (
        db.query(models.Entrega)
        .order_by(models.Entrega.numero_remito.desc())
        .first()
    )

    if not ultimo or not ultimo.numero_remito:
        return "RE-000001"

    partes = ultimo.numero_remito.split("-")
    if len(partes) == 2:
        nuevo_numero = str(int(partes[1]) + 1).zfill(6)
        return f"RE-{nuevo_numero}"

    return "RE-000001"


@router.post("")
def registrar_entrega(
    entrega_in: schemas.EntregaCreate,
    forzar: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    """Registra un remito (una o varias filas, cada una de un trabajo del
    mismo cliente) y lo emite en PDF.

    No hay guard de "primera vez": cada llamada es un remito real y
    repetible, así que siempre asigna un número nuevo (ver GET
    /{entrega_id}/pdf para reimprimir uno ya emitido sin generar otro).

    Si algún ítem supera su saldo pendiente, corta con 400 salvo que
    forzar=true (mismo criterio que el stock insuficiente de imprimir_orden
    en routers/trabajos.py): puede haber una reposición legítima que exceda
    lo originalmente pedido.
    """
    cliente = obtener_o_404(db, models.Cliente, entrega_in.cliente_id, "Cliente no encontrado")

    if len(entrega_in.items) > MAX_ITEMS_POR_REMITO:
        raise HTTPException(
            status_code=400,
            detail=f"Un remito admite hasta {MAX_ITEMS_POR_REMITO} trabajos; dividí la entrega en dos remitos.",
        )

    trabajos_por_id = {
        t.id: t for t in db.query(models.Trabajo)
        .filter(models.Trabajo.id.in_([item.trabajo_id for item in entrega_in.items]))
        .all()
    }

    excedidos = []
    for item in entrega_in.items:
        trabajo = trabajos_por_id.get(item.trabajo_id)
        if not trabajo:
            raise HTTPException(status_code=404, detail=f"Trabajo {item.trabajo_id} no encontrado.")
        if trabajo.cliente_id != entrega_in.cliente_id:
            raise HTTPException(
                status_code=400,
                detail=f"El trabajo '{trabajo.descripcion_producto}' no es de este cliente.",
            )
        pendiente = saldo_pendiente_entrega(trabajo)
        if item.cantidad > pendiente:
            excedidos.append((trabajo, pendiente))

    if excedidos and not forzar:
        detalle = "; ".join(f"{t.descripcion_producto} (quedan {p})" for t, p in excedidos)
        raise HTTPException(
            status_code=400,
            detail=f"Supera el saldo pendiente en: {detalle}. ¿Registrar igual?",
        )

    intentos_restantes = 3
    while True:
        numero_remito = _generar_numero_remito(db)
        entrega = models.Entrega(
            cliente_id=entrega_in.cliente_id,
            numero_remito=numero_remito,
            fecha=datetime.now(timezone.utc),
        )
        db.add(entrega)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            intentos_restantes -= 1
            if not intentos_restantes:
                raise HTTPException(status_code=409, detail="No se pudo numerar el remito, reintentá.")

    ids_excedidos = {t.id for t, _ in excedidos}
    combinado = len(entrega_in.items) > 1
    for item in entrega_in.items:
        db.add(models.ItemEntrega(entrega_id=entrega.id, trabajo_id=item.trabajo_id, cantidad=item.cantidad))

        trabajo = trabajos_por_id[item.trabajo_id]
        detalle = f"entrega de {item.cantidad} registrada, remito {numero_remito} emitido"
        if combinado:
            detalle += f" (remito combinado con {len(entrega_in.items) - 1} trabajo(s) más)"
        if item.trabajo_id in ids_excedidos:
            detalle += " (forzada: excede el saldo pendiente)"
        asentar(db, usuario, models.ACCION_EDICION, ENTIDAD_TRABAJO, trabajo.id, resumen_trabajo(trabajo), detalle)

    db.commit()
    db.refresh(entrega)

    pdf = construir_entrega_pdf(entrega, cliente)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="remito_{numero_remito}.pdf"'},
    )


@router.get("/{entrega_id}/pdf")
def reimprimir_entrega(
    entrega_id: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    """Reimprime un remito ya emitido. Sin efectos: no crea nada ni toca
    auditoría, sólo vuelve a armar el mismo PDF con las mismas filas.
    """
    entrega = obtener_o_404(db, models.Entrega, entrega_id, "Entrega no encontrada")

    pdf = construir_entrega_pdf(entrega, entrega.cliente)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="remito_{entrega.numero_remito}.pdf"'},
    )
