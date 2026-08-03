"""
Armado del PDF de la Hoja de Costos Internos (desglose de costos y margen por
presupuesto).

Hermano de pdf/presupuesto.py: no toca la base de datos ni tiene efectos, sólo
recibe el presupuesto (con sus ítems ya cargados) y el cliente y devuelve los
bytes del PDF. A diferencia de los otros tres comprobantes (una sola página,
armados a mano con canvas), acá el contenido es variable -- un presupuesto
puede traer de uno a una docena de productos, cada uno con su propia tabla de
costos -- así que se arma con SimpleDocTemplate/Platypus para que ReportLab
pagine solo. Antes se armaba en el navegador con html2pdf (captura de
pantalla): sin paginación real, una tabla de costos se cortaba a la mitad de
una fila al pasar de página.

Uso exclusivamente interno: lleva costos y margen de ganancia, nunca se
entrega al cliente (mismo criterio que CAMPOS_DE_PLATA / _trabajo_visible en
routers/trabajos.py: el margen no es un dato para mostrar afuera del taller).
"""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from pdf.comun import pesos, texto

ANCHO, ALTO = A4
MARGEN = 18 * mm

ROSA = colors.HexColor("#D5006D")
GRIS_CABECERA = colors.HexColor("#eeeeee")
GRIS_BORDE = colors.HexColor("#dddddd")
ROSA_SUBTOTAL = colors.HexColor("#ffe6f2")

estilo_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=6)
estilo_normal = ParagraphStyle("normal", fontName="Helvetica", fontSize=10, leading=13)
estilo_producto = ParagraphStyle("producto", fontName="Helvetica-Bold", fontSize=11, spaceBefore=4, spaceAfter=4)
estilo_celda = ParagraphStyle("celda_costo", fontName="Helvetica", fontSize=9, leading=11)


def _fecha(presupuesto):
    return presupuesto.fecha_creacion.strftime("%d/%m/%Y") if presupuesto.fecha_creacion else "-"


def _tabla_costos(item, total_item):
    """Ítem de costo / Monto, con el subtotal y la ganancia estimada al pie."""
    costo = item.costo_materiales or Decimal("0")
    filas = [["Ítem de costo", "Monto"]]
    detalles = item.detalles_costos or {}
    if detalles:
        for nombre, monto in detalles.items():
            filas.append([Paragraph(texto(nombre), estilo_celda), f"$ {pesos(monto)}"])
    else:
        filas.append([Paragraph("Sin costos cargados", estilo_celda), ""])

    ganancia_label = "Ganancia estimada"
    if item.margen_ganancia is not None:
        ganancia_label += f" ({texto(item.margen_ganancia)}%)"
    filas.append(["SUBTOTAL COSTOS", f"$ {pesos(costo)}"])
    filas.append([ganancia_label, f"$ {pesos(total_item - costo)}"])

    ancho_util = ANCHO - 2 * MARGEN
    tabla = Table(filas, colWidths=[ancho_util - 32 * mm, 32 * mm])
    n = len(filas)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CABECERA),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("BACKGROUND", (0, n - 2), (-1, n - 2), ROSA_SUBTOTAL),
        ("FONTNAME", (0, n - 2), (-1, n - 2), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


def _bloque_producto(idx, item):
    """Un producto completo (encabezado + tabla de costos), envuelto en
    KeepTogether para que Platypus lo empuje entero a la página siguiente si no
    entra en lo que queda de la actual, en vez de cortarlo a la mitad -- es la
    paginación real que html2pdf no ofrecía.
    """
    total_item = item.cantidad * item.precio_unitario
    gramaje = f"{texto(item.gramaje)} g/m²" if item.gramaje else "-"
    bloque = KeepTogether([
        Paragraph(f"Producto {idx}: {item.cantidad}x {texto(item.descripcion)}", estilo_producto),
        Paragraph(
            f"<b>Material:</b> {texto(item.material)} &nbsp;|&nbsp; <b>Gramaje:</b> {gramaje}",
            estilo_normal,
        ),
        Paragraph(
            f"<b>Precio unitario:</b> $ {pesos(item.precio_unitario)} &nbsp;|&nbsp; "
            f"<b>Total:</b> $ {pesos(total_item)}",
            estilo_normal,
        ),
        Spacer(1, 4),
        _tabla_costos(item, total_item),
        Spacer(1, 14),
    ])
    return bloque, total_item


def construir_costos_pdf(presupuesto, cliente) -> bytes:
    """Devuelve los bytes de la hoja de costos internos (uso interno)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=MARGEN, bottomMargin=MARGEN, leftMargin=MARGEN, rightMargin=MARGEN,
        title=f"Costos internos {presupuesto.numero_secuencia or 's/n'}",
    )

    nombre_cliente = cliente.nombre_completo if cliente else "Sin cliente"
    short_id = presupuesto.id[:6].upper()

    story = [
        Paragraph(f"[INTERNO] Hoja de Costos — #{short_id}", estilo_titulo),
        Paragraph(
            f"<b>Cliente:</b> {texto(nombre_cliente)} &nbsp;|&nbsp; <b>Fecha:</b> {_fecha(presupuesto)}",
            estilo_normal,
        ),
        Spacer(1, 6),
        HRFlowable(width="100%", color=GRIS_BORDE, thickness=0.7),
        Spacer(1, 10),
    ]

    total_presupuesto = Decimal("0")
    for idx, item in enumerate(presupuesto.items, start=1):
        bloque, total_item = _bloque_producto(idx, item)
        total_presupuesto += total_item
        story.append(bloque)

    story.append(Paragraph(
        f"PRECIO FINAL COBRADO: $ {pesos(total_presupuesto)}",
        ParagraphStyle("total", fontName="Helvetica-Bold", fontSize=13, textColor=ROSA, alignment=2),
    ))

    doc.build(story)
    return buffer.getvalue()
