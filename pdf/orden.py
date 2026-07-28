"""
Armado del PDF de la Orden de Producción (la boleta física del taller).

No toca la base de datos ni tiene efectos: recibe los objetos ya cargados y
devuelve los bytes del PDF. La lógica vive acá y no en el router para no meter
cien líneas de layout adentro de un endpoint. Los helpers compartidos con el
otro comprobante (texto, ruta_asset) viven en pdf/comun.py.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from pdf.comun import ruta_asset, texto

ANCHO, ALTO = A4

MARGEN = 15 * mm
ALTO_LOGO = 18 * mm


def _nombre_papel(trabajo, articulo_papel):
    """Qué papel se lee en la boleta.

    Si el trabajo está vinculado a un artículo de stock, manda el nombre del
    artículo (es lo que se va a buscar al depósito). Si no, el texto libre.
    """
    if articulo_papel is not None:
        return articulo_papel.nombre
    return texto(trabajo.papel_tipo)


def _dibujar_encabezado(c, trabajo):
    """Logo + número de orden + fecha. Devuelve la Y donde sigue el contenido."""
    y = ALTO - MARGEN

    logo = ruta_asset("logo.png")
    if logo:
        # preserveAspectRatio evita que el logo se deforme si cambia el archivo.
        c.drawImage(
            logo, MARGEN, y - ALTO_LOGO, height=ALTO_LOGO, width=ALTO_LOGO * 3,
            preserveAspectRatio=True, anchor="sw", mask="auto",
        )
    else:
        # Todavía no hay logo: dejamos el nombre para que la boleta sirva igual.
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGEN, y - 12, "Gráfica Viamonte")

    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(ANCHO - MARGEN, y - 6, "ORDEN DE PRODUCCIÓN")

    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(ANCHO - MARGEN, y - 22, f"N° {texto(trabajo.numero_orden)}")

    fecha = trabajo.fecha_orden_impresa or trabajo.fecha_creacion
    c.setFont("Helvetica", 10)
    c.drawRightString(
        ANCHO - MARGEN, y - 36,
        f"Fecha: {fecha.strftime('%d/%m/%Y') if fecha else '-'}",
    )

    y -= ALTO_LOGO + 6 * mm
    c.setLineWidth(1)
    c.line(MARGEN, y, ANCHO - MARGEN, y)
    return y - 8 * mm


def _dibujar_fila(c, y, etiqueta, valor, ancho_etiqueta=38 * mm):
    """Una línea 'Etiqueta: valor' del cuerpo de la boleta."""
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGEN, y, f"{etiqueta}:")
    c.setFont("Helvetica", 10)
    c.drawString(MARGEN + ancho_etiqueta, y, texto(valor))
    return y - 7 * mm


def _dibujar_recuadro_corte(c, y, lado=45 * mm):
    """Recuadro vacío para que el taller dibuje a mano el esquema de corte.

    Sale siempre en blanco: el corte se traza en el momento sobre la boleta, no
    es un dato que el sistema guarde. Va alineado con la columna de los valores
    de _dibujar_fila, justo debajo de 'Corte de pliego'.
    """
    tope = y + 3 * mm  # el texto de la fila anterior queda apenas arriba del marco
    c.setLineWidth(1)
    c.rect(MARGEN + 38 * mm, tope - lado, lado, lado, stroke=1, fill=0)
    return tope - lado - 5 * mm


def _dibujar_seccion(c, y, titulo):
    """Título de sección con fondo gris, al estilo de los rubros de la boleta."""
    alto = 6 * mm
    c.setFillColor(colors.HexColor("#e8e8e8"))
    c.rect(MARGEN, y - alto + 2 * mm, ANCHO - 2 * MARGEN, alto, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGEN + 2 * mm, y, titulo)
    return y - 9 * mm


def construir_orden_pdf(trabajo, cliente, articulo_papel=None) -> bytes:
    """Devuelve los bytes del PDF de la orden de producción.

    articulo_papel es el ArticuloStock vinculado (o None si el papel no sale
    del stock: lo trajo el cliente, se compró en el momento, etc.).
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Orden {texto(trabajo.numero_orden)}")

    y = _dibujar_encabezado(c, trabajo)

    y = _dibujar_seccion(c, y, "CLIENTE")
    y = _dibujar_fila(c, y, "Nombre", cliente.nombre_completo if cliente else None)
    if cliente and cliente.nombre_empresa:
        y = _dibujar_fila(c, y, "Empresa", cliente.nombre_empresa)
    y = _dibujar_fila(c, y, "Teléfono", cliente.telefono if cliente else None)
    y -= 2 * mm

    y = _dibujar_seccion(c, y, "TRABAJO")
    y = _dibujar_fila(c, y, "Descripción", trabajo.descripcion_producto)
    y = _dibujar_fila(c, y, "Medida terminado", trabajo.medida_terminado)
    y -= 2 * mm

    y = _dibujar_seccion(c, y, "PAPEL")
    y = _dibujar_fila(c, y, "Tipo", _nombre_papel(trabajo, articulo_papel))
    y = _dibujar_fila(c, y, "Medida pliego", trabajo.medida_pliego)
    y = _dibujar_fila(c, y, "Corte de pliego", trabajo.corte_pliego)
    y = _dibujar_recuadro_corte(c, y)
    y = _dibujar_fila(c, y, "Cantidad de pliegos", trabajo.cantidad_pliegos)
    y -= 2 * mm

    y = _dibujar_seccion(c, y, "IMPRESIÓN Y TERMINACIÓN")
    y = _dibujar_fila(c, y, "Tintas", trabajo.tintas)
    y = _dibujar_fila(c, y, "Troquelado", trabajo.troquelado)
    y = _dibujar_fila(c, y, "Barniz", trabajo.barniz)
    y = _dibujar_fila(c, y, "Otros", trabajo.otros)
    y -= 4 * mm

    # Espacio para que el taller anote a mano lo que pase en máquina.
    y = _dibujar_seccion(c, y, "OBSERVACIONES DE TALLER")
    c.setStrokeColor(colors.HexColor("#bbbbbb"))
    for _ in range(4):
        c.line(MARGEN, y, ANCHO - MARGEN, y)
        y -= 8 * mm
    c.setStrokeColor(colors.black)

    c.showPage()
    c.save()
    return buffer.getvalue()
