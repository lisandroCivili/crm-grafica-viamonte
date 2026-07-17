from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
import models, schemas
from database import get_db
from datetime import date
from money import Q2, Q3

router = APIRouter(prefix="/api/stock", tags=["Stock"])

# (Largo cm x Ancho cm x Gramaje grs) / 10.000.000 = peso de 1 pliego en Kg
DIVISOR_PESO_PLIEGO = Decimal("10000000")


def _calcular_pliegos(largo_cm, ancho_cm, gramaje_grs, peso_total_kg, pos: int) -> Decimal:
    """Convierte una compra de papel por peso a cantidad de pliegos enteros.

    El paquete real siempre tiene pliegos enteros: el desvío del cálculo viene
    del peso nominal, por eso se redondea al entero más cercano (ROUND_HALF_UP).
    """
    datos = {
        "largo_cm": largo_cm,
        "ancho_cm": ancho_cm,
        "gramaje_grs": gramaje_grs,
        "peso_total_kg": peso_total_kg,
    }
    faltantes = [campo for campo, valor in datos.items() if valor is None]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"Ítem {pos}: para comprar papel por Kg faltan: {', '.join(faltantes)}.",
        )
    if any(valor <= 0 for valor in datos.values()):
        raise HTTPException(
            status_code=400,
            detail=f"Ítem {pos}: largo, ancho, gramaje y peso deben ser mayores a cero.",
        )
    peso_pliego_kg = (largo_cm * ancho_cm * gramaje_grs) / DIVISOR_PESO_PLIEGO
    return (peso_total_kg / peso_pliego_kg).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _procesar_item_compra(db: Session, item: schemas.CompraStockItem, pos: int) -> models.ArticuloStock:
    """Aplica un ítem del carrito: recompra (suma al existente) o alta nueva."""
    articulo = None
    if item.articulo_id:
        articulo = db.query(models.ArticuloStock).filter(models.ArticuloStock.id == item.articulo_id).first()
        if not articulo:
            raise HTTPException(status_code=404, detail=f"Ítem {pos}: artículo con ID {item.articulo_id} no encontrado.")
    elif not item.nombre or not item.unidad:
        raise HTTPException(status_code=400, detail=f"Ítem {pos}: nombre y unidad son obligatorios para un artículo nuevo.")

    unidad = item.unidad or articulo.unidad
    largo = item.largo_cm if item.largo_cm is not None else (articulo.largo_cm if articulo else None)
    ancho = item.ancho_cm if item.ancho_cm is not None else (articulo.ancho_cm if articulo else None)
    gramaje = item.gramaje_grs if item.gramaje_grs is not None else (articulo.gramaje_grs if articulo else None)

    if unidad == "Kg":
        # El papel comprado por peso se guarda ya convertido a pliegos, para
        # que la Orden de Trabajo pueda descontar pliegos enteros directo.
        cantidad = _calcular_pliegos(largo, ancho, gramaje, item.peso_total_kg, pos)
        unidad = "Pliegos"
        motivo = (
            f"Compra: {Q3(item.peso_total_kg)} kg → {cantidad} pliegos "
            f"({Q3(largo)}x{Q3(ancho)} cm, {Q3(gramaje)} grs)"
        )
    else:
        if item.cantidad is None or item.cantidad <= 0:
            raise HTTPException(status_code=400, detail=f"Ítem {pos}: la cantidad debe ser mayor a cero.")
        cantidad = Q3(item.cantidad)
        motivo = f"Compra: +{cantidad} {unidad}"

    costo_unitario = item.costo_unitario
    if item.costo_total is not None:
        costo_unitario = Q2(item.costo_total / cantidad)

    if articulo:
        articulo.cantidad = Q3(articulo.cantidad + cantidad)
        db.add(models.HistorialStock(articulo_id=articulo.id, diferencia=cantidad, motivo=motivo))
    else:
        articulo = models.ArticuloStock(
            nombre=item.nombre,
            categoria=item.categoria or "General",
            proveedor=item.proveedor,
            cantidad=cantidad,
            unidad=unidad,
            stock_minimo=item.stock_minimo if item.stock_minimo is not None else Decimal("5"),
        )
        db.add(articulo)

    if costo_unitario is not None:
        articulo.costo_unitario = costo_unitario
    if largo is not None:
        articulo.largo_cm = largo
    if ancho is not None:
        articulo.ancho_cm = ancho
    if gramaje is not None:
        articulo.gramaje_grs = gramaje
    articulo.ultima_actualizacion = date.today()
    return articulo

@router.get("/", response_model=list[schemas.StockResponse])
def listar_stock(db: Session = Depends(get_db)):
    return db.query(models.ArticuloStock).order_by(models.ArticuloStock.nombre).all()

@router.post("/", response_model=schemas.StockResponse)
def crear_articulo(art: schemas.StockCreate, db: Session = Depends(get_db)):
    nuevo = models.ArticuloStock(**art.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.post("/compras", response_model=list[schemas.StockResponse], status_code=status.HTTP_201_CREATED)
def registrar_compra(items: list[schemas.CompraStockItem], db: Session = Depends(get_db)):
    """Registra una compra de 1 o más ítems (carrito) en una sola transacción.

    Cada ítem puede ser un alta nueva o una recompra (articulo_id): la recompra
    suma cantidad al artículo y queda registrada en su historial. El papel
    comprado por Kg se convierte a pliegos enteros. Si un ítem falla, no se
    aplica ninguno (rollback total).
    """
    if not items:
        raise HTTPException(status_code=400, detail="La compra debe incluir al menos un ítem.")

    try:
        articulos = [_procesar_item_compra(db, item, pos) for pos, item in enumerate(items, start=1)]
        db.commit()
    except Exception:
        db.rollback()
        raise

    for art in articulos:
        db.refresh(art)
    return articulos

# REEMPLAZAR EL PATCH Y AGREGAR EL GET DE HISTORIAL
@router.patch("/{articulo_id}")
def actualizar_cantidad(articulo_id: str, update_data: schemas.StockUpdate, db: Session = Depends(get_db)):
    db_art = db.query(models.ArticuloStock).filter(models.ArticuloStock.id == articulo_id).first()
    if not db_art:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    # Campos descriptivos: se pisan directo, no generan historial (el historial es solo para cantidad)
    for campo in ("nombre", "categoria", "proveedor", "unidad", "stock_minimo", "largo_cm", "ancho_cm", "gramaje_grs"):
        valor = getattr(update_data, campo)
        if valor is not None:
            setattr(db_art, campo, valor)

    if update_data.cantidad is not None:
        diferencia = update_data.cantidad - db_art.cantidad

        # MAGIA: Si hubo un cambio real, registramos el historial
        if diferencia != 0:
            historial = models.HistorialStock(
                articulo_id=db_art.id,
                diferencia=diferencia,
                motivo=update_data.motivo
            )
            db.add(historial)
            db_art.cantidad = update_data.cantidad

    if update_data.costo_unitario is not None:
        db_art.costo_unitario = update_data.costo_unitario

    db_art.ultima_actualizacion = date.today()
    db.commit()
    return {"mensaje": "Stock actualizado"}

@router.get("/{articulo_id}/historial", response_model=list[schemas.HistorialStockResponse])
def ver_historial(articulo_id: str, db: Session = Depends(get_db)):
    # Trae los movimientos del más nuevo al más viejo
    return db.query(models.HistorialStock).filter(models.HistorialStock.articulo_id == articulo_id).order_by(models.HistorialStock.fecha.desc()).all()

@router.delete("/{articulo_id}")
def eliminar_articulo(articulo_id: str, db: Session = Depends(get_db)):
    db_art = db.query(models.ArticuloStock).filter(models.ArticuloStock.id == articulo_id).first()
    if not db_art:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    lo_usa_un_trabajo = db.query(models.Trabajo).filter(models.Trabajo.papel_id == articulo_id).first()
    if lo_usa_un_trabajo:
        raise HTTPException(status_code=400, detail="No se puede eliminar: hay trabajos que usan este artículo como papel.")

    # El historial de ajustes pertenece al artículo: se borra junto con él.
    db.query(models.HistorialStock).filter(models.HistorialStock.articulo_id == articulo_id).delete()
    db.delete(db_art)
    db.commit()
    return {"mensaje": "Artículo eliminado"}