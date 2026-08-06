"""
Armado del PDF de la Hoja de Ruta diaria (lo que el taller tiene para hacer hoy).

Hermano de los otros PDF del backend: no toca la base de datos ni tiene
efectos, sólo recibe los trabajos ya agrupados por estado y devuelve los bytes
del PDF, armado con ReportLab/Platypus para que pagine solo si hay muchos
trabajos cargados.

Reemplaza al viejo "Informe Diario", que era una captura de pantalla del
Kanban completo (html2pdf + html2canvas): salía como imagen, cortaba columnas
al pasar de página y no se podía leer con el tablero cargado. El pedido del
dueño para esta versión fue puntual: no hace falta repetir el tablero
entero, sólo lo que un técnico tiene una tarea pendiente en la mano HOY --
'En Diseño' y 'En Producción' -- así que 'Aprobado' y 'Entregado' quedan
afuera. Tampoco lleva precio ni costo: es una hoja de trabajo del taller, no
un documento de facturación (mismo espíritu que CAMPOS_DE_PLATA en
routers/trabajos.py, sólo que acá directamente no se piden esas columnas).
"""
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pdf.comun import texto

ANCHO, ALTO = landscape(A4)
MARGEN = 15 * mm

# Mismos colores que la columna del Kanban en frontend/style.css (--magenta y
# --amber), para que la hoja impresa se reconozca de un vistazo como "la misma
# etapa" que la pantalla.
COLOR_ESTADO = {
    "En Diseño": colors.HexColor("#E6007A"),
    "En Producción": colors.HexColor("#B87A1A"),
}
GRIS_BORDE = colors.HexColor("#dddddd")
GRIS_CABECERA = colors.HexColor("#f2f2f2")
GRIS_TEXTO = colors.HexColor("#8A7B87")

estilo_celda = ParagraphStyle("celda", fontName="Helvetica", fontSize=9, leading=11)
estilo_vacio = ParagraphStyle("vacio", fontName="Helvetica-Oblique", fontSize=9, textColor=GRIS_TEXTO)


def _identificador(trabajo):
    """Cómo se nombra el trabajo en la hoja: el número de orden si ya se
    imprimió, o el id corto (mismo criterio que el Kanban) si todavía no.
    """
    return trabajo.numero_orden or f"#{trabajo.id[:6].upper()}"


def _fecha_entrega(trabajo):
    return trabajo.fecha_entrega.strftime("%d/%m/%Y") if trabajo.fecha_entrega else "-"


def _nombre_papel(trabajo):
    if trabajo.papel is not None:
        return trabajo.papel.nombre
    return trabajo.papel_tipo


def _tabla_estado(trabajos):
    encabezado = ["N°", "Cliente", "Producto", "Cant.", "Papel", "Entrega"]
    filas = [encabezado]
    for t in trabajos:
        filas.append([
            texto(_identificador(t)),
            Paragraph(texto((t.cliente.nombre_empresa or t.cliente.nombre_completo) if t.cliente else None), estilo_celda),
            Paragraph(texto(t.descripcion_producto), estilo_celda),
            str(t.cantidad),
            Paragraph(texto(_nombre_papel(t)), estilo_celda),
            _fecha_entrega(t),
        ])

    ancho_util = ANCHO - 2 * MARGEN
    col_id, col_cant, col_papel, col_entrega = 24 * mm, 16 * mm, 45 * mm, 24 * mm
    resto = ancho_util - col_id - col_cant - col_papel - col_entrega
    col_cliente = resto * 0.4
    col_producto = resto - col_cliente

    tabla = Table(
        filas,
        colWidths=[col_id, col_cliente, col_producto, col_cant, col_papel, col_entrega],
        repeatRows=1,
    )
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CABECERA),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("ALIGN", (5, 0), (5, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


def _seccion(estado, trabajos):
    """Barra de color con el nombre de la etapa + la tabla (o el aviso de que
    no hay nada), en el orden en que va al story.
    """
    color = COLOR_ESTADO.get(estado, colors.black)
    barra = Table([[f"{estado.upper()}  ({len(trabajos)})"]], colWidths=[ANCHO - 2 * MARGEN])
    barra.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    piezas = [barra, Spacer(1, 4)]
    if trabajos:
        piezas.append(_tabla_estado(trabajos))
    else:
        piezas.append(Paragraph("Sin trabajos en esta etapa hoy.", estilo_vacio))
    piezas.append(Spacer(1, 14))
    return piezas


def _pie_pagina(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(GRIS_TEXTO)
    canvas_obj.drawString(
        MARGEN, 10 * mm,
        f"Gráfica Viamonte — Hoja de Ruta del {date.today().strftime('%d/%m/%Y')}",
    )
    canvas_obj.drawRightString(ANCHO - MARGEN, 10 * mm, f"Página {doc.page}")
    canvas_obj.restoreState()


def construir_informe_diario_pdf(por_estado: dict) -> bytes:
    """Devuelve los bytes de la hoja de ruta diaria.

    por_estado: {"En Diseño": [Trabajo, ...], "En Producción": [Trabajo, ...]},
    en el orden en que van las secciones. Cada trabajo trae su cliente y su
    papel ya cargados (ver routers/trabajos.py).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=MARGEN, bottomMargin=MARGEN + 6 * mm, leftMargin=MARGEN, rightMargin=MARGEN,
        title=f"Hoja de Ruta {date.today().strftime('%d-%m-%Y')}",
    )

    story = [
        Paragraph(
            f"Hoja de Ruta — {date.today().strftime('%d/%m/%Y')}",
            ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=18),
        ),
        Spacer(1, 10),
    ]
    for estado, trabajos in por_estado.items():
        story.extend(_seccion(estado, trabajos))

    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return buffer.getvalue()
