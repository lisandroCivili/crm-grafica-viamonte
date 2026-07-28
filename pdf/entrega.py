"""
Armado del PDF de la Orden de Entrega (el remito que firma el cliente al retirar
la mercadería).

Hermano de pdf/orden.py y pdf/presupuesto.py: no toca la base de datos ni tiene
efectos, sólo recibe el trabajo y el cliente ya cargados y devuelve los bytes
del PDF. Los helpers compartidos (texto, ruta_asset) están en pdf/comun.py.

A diferencia de los otros dos comprobantes, el talonario físico se imprime por
duplicado en una sola hoja A4: el mismo remito arriba y abajo, separados por una
guía de corte a los 148.5mm (mitad exacta de la hoja), para cortar con
guillotina y quedarse con una copia archivada. Por eso todo el layout está en
_dibujar_remito(), parametrizado por la Y donde arranca cada mitad, y se llama
dos veces.

Un Trabajo es un solo ítem (ver ItemPresupuesto: un presupuesto multi-ítem
genera un Trabajo por ítem), así que la tabla del remito lleva una sola fila de
datos reales; el resto de renglones quedan en blanco para anotar a mano, igual
que en el talonario de papel.

El modelo Cliente hoy no tiene domicilio, localidad ni condición de IVA: esos
renglones se imprimen con línea punteada o casillero vacío para completar a
mano en el momento de la entrega, como se hacía en el talonario físico. Como
"logo.png" todavía no existe (mismo caso que orden.py), el encabezado cae al
nombre de la gráfica en texto.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from pdf.comun import ruta_asset, texto

ANCHO, ALTO = A4
MITAD = ALTO / 2  # 148.5mm: línea de corte con guillotina

MARGEN = 10 * mm
ANCHO_UTIL = ANCHO - 2 * MARGEN

ALTO_LOGO = 12 * mm
ALTO_HEADER = 30 * mm
ANCHO_CAJA_ORDEN = 58 * mm

ALTO_FILA_CLIENTE = 5.5 * mm
ANCHO_BLOQUE_IVA = 46 * mm
# Cada campo del cliente va emparejado con su casillero de IVA a la derecha,
# igual que en el talonario de papel (no van todos juntos en una fila aparte).
CAMPOS_CLIENTE_CON_IVA = [
    ("Domicilio", "Resp. Inscripto"),
    ("Localidad", "Consumidor Final"),
    ("Tel", "Exento"),
    ("C.U.I.T. N°", "Resp. Monotributo"),
]

FILAS_TABLA_BLANCO = 4
ALTO_HEADER_TABLA = 6 * mm
ALTO_FILA_TABLA = 7.5 * mm

ALTO_FOOTER = 30 * mm
ANCHO_CAJA_RECIBI = 70 * mm

GRIS_LINEA = colors.HexColor("#999999")
GRIS_CLARO = colors.HexColor("#e8e8e8")

DATOS_EMPRESA = [
    "Colombia 2950 - Tel.: 434-2890 / 7286",
    "e-mail: ingrafviamonte@arnet.com.ar",
    "4000 - San Miguel de Tucumán",
    "C.U.I.T.: 20-08285232-9 - Ing. Brutos: 20-08285232-9",
]


def _linea_punteada(c, x1, y, x2):
    c.saveState()
    c.setStrokeColor(GRIS_LINEA)
    c.setDash([1, 1.5], 0)
    c.setLineWidth(0.6)
    c.line(x1, y, x2, y)
    c.restoreState()


def _renglon(c, x0, y, ancho, etiqueta, valor=None):
    """'Etiqueta: ' seguida de una línea punteada hasta completar el ancho.

    Si valor viene, se imprime sobre la línea (dato ya conocido); si no, la
    línea queda vacía para completar a mano.
    """
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 7.5)
    c.drawString(x0, y, f"{etiqueta}:")
    ancho_etiqueta = c.stringWidth(f"{etiqueta}: ", "Helvetica", 7.5)
    x_linea_ini = x0 + ancho_etiqueta
    _linea_punteada(c, x_linea_ini, y - 0.8 * mm, x0 + ancho)
    if valor:
        c.drawString(x_linea_ini + 1 * mm, y, texto(valor))


def _dibujar_caja_orden(c, y, numero, fecha_str):
    """Recuadro de la derecha: casillero X, título, número y fecha."""
    x_caja = ANCHO - MARGEN - ANCHO_CAJA_ORDEN
    y_caja = y - ALTO_HEADER
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    c.rect(x_caja, y_caja, ANCHO_CAJA_ORDEN, ALTO_HEADER, fill=0, stroke=1)

    lado_x = 4.5 * mm
    x_check = x_caja + 3 * mm
    y_check = y - 5 * mm - lado_x
    c.rect(x_check, y_check, lado_x, lado_x, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(x_check + lado_x / 2, y_check + 1.3 * mm, "X")

    cx = x_caja + ANCHO_CAJA_ORDEN / 2
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx, y - 13 * mm, "ORDEN DE ENTREGA")
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, y - 19.5 * mm, f"N° {numero}")
    c.setFont("Helvetica", 8)
    c.drawCentredString(cx, y - 25.5 * mm, f"Fecha: {fecha_str}")


def _dibujar_header(c, y, numero, fecha_str):
    """Logo (o texto) y datos de la gráfica a la izquierda, recuadro de la
    orden a la derecha. y es el techo del bloque; devuelve la Y donde sigue el
    contenido.
    """
    x_izq = MARGEN

    logo = ruta_asset("logo.png")
    if logo:
        c.drawImage(
            logo, x_izq, y - ALTO_LOGO, height=ALTO_LOGO, width=ALTO_LOGO * 3,
            preserveAspectRatio=True, anchor="sw", mask="auto",
        )
        yy = y - ALTO_LOGO - 3.5 * mm
    else:
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.black)
        c.drawString(x_izq, y - 4.5 * mm, "GRÁFICA VIAMONTE")
        c.setFont("Helvetica", 7)
        c.drawString(x_izq, y - 9 * mm, "Daniel Enrique Soria")
        yy = y - 13 * mm

    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.black)
    for linea in DATOS_EMPRESA:
        c.drawString(x_izq, yy, linea)
        yy -= 3 * mm

    _dibujar_caja_orden(c, y, numero, fecha_str)

    return y - ALTO_HEADER - 3 * mm


def _casillero(c, x, y, etiqueta):
    """Cuadradito vacío + etiqueta, para tildar a mano (condición de IVA)."""
    lado = 3 * mm
    c.setStrokeColor(colors.black)
    c.rect(x, y - 0.3 * mm, lado, lado, fill=0, stroke=1)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.black)
    c.drawString(x + lado + 1.3 * mm, y, etiqueta)


def _dibujar_cliente(c, y, cliente):
    """Datos del cliente. Domicilio, Localidad y la condición de IVA se dejan
    en blanco: el modelo Cliente hoy no los tiene, se completan a mano igual
    que en el talonario de papel. Cada campo va emparejado con su casillero de
    IVA a la derecha, como en el original.
    """
    nombre = cliente.nombre_completo if cliente else None
    telefono = cliente.telefono if cliente else None
    cuit = cliente.dni_cuit if cliente else None

    x_campo = MARGEN
    x_check = ANCHO - MARGEN - ANCHO_BLOQUE_IVA
    ancho_campo = x_check - x_campo - 4 * mm

    _renglon(c, x_campo, y, ANCHO_UTIL, "Sres.", nombre)
    y -= ALTO_FILA_CLIENTE

    valores = {"Domicilio": None, "Localidad": None, "Tel": telefono, "C.U.I.T. N°": cuit}
    for etiqueta, iva in CAMPOS_CLIENTE_CON_IVA:
        _renglon(c, x_campo, y, ancho_campo, etiqueta, valores[etiqueta])
        _casillero(c, x_check, y, iva)
        y -= ALTO_FILA_CLIENTE

    return y


def _dibujar_leyenda_tabla(c, y):
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.black)
    c.drawString(MARGEN, y, "Entregamos a UD. la Mercadería detallada a continuación")
    return y - 4 * mm


def _dibujar_tabla(c, y, trabajo):
    """CANTIDAD / DESCRIPCION / OBSERVACIONES. Una sola fila con datos reales
    (un Trabajo es un solo ítem); el resto queda en blanco para anotar a mano.
    """
    ancho_cant = 22 * mm
    ancho_obs = 42 * mm
    ancho_desc = ANCHO_UTIL - ancho_cant - ancho_obs
    x0 = MARGEN
    x1 = x0 + ancho_cant
    x2 = x1 + ancho_desc
    x3 = x2 + ancho_obs

    total_filas = 1 + FILAS_TABLA_BLANCO
    alto_tabla = ALTO_HEADER_TABLA + total_filas * ALTO_FILA_TABLA
    y_header_bottom = y - ALTO_HEADER_TABLA
    y_bottom = y - alto_tabla

    c.setFillColor(GRIS_CLARO)
    c.rect(x0, y_header_bottom, ANCHO_UTIL, ALTO_HEADER_TABLA, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString((x0 + x1) / 2, y_header_bottom + 2 * mm, "CANTIDAD")
    c.drawCentredString((x1 + x2) / 2, y_header_bottom + 2 * mm, "DESCRIPCION")
    c.drawCentredString((x2 + x3) / 2, y_header_bottom + 2 * mm, "OBSERVACIONES")

    c.setLineWidth(0.75)
    c.setStrokeColor(colors.black)
    c.rect(x0, y_bottom, ANCHO_UTIL, alto_tabla, fill=0, stroke=1)
    c.line(x0, y_header_bottom, x3, y_header_bottom)
    c.line(x1, y_bottom, x1, y)
    c.line(x2, y_bottom, x2, y)

    yy = y_header_bottom
    for _ in range(total_filas):
        yy -= ALTO_FILA_TABLA
        c.line(x0, yy, x3, yy)

    y_primera_fila = y_header_bottom - ALTO_FILA_TABLA
    c.setFont("Helvetica", 8)
    c.drawCentredString((x0 + x1) / 2, y_primera_fila + 2.8 * mm, str(trabajo.cantidad))
    c.drawString(x1 + 2 * mm, y_primera_fila + 2.8 * mm, texto(trabajo.descripcion_producto))

    return y_bottom


def _dibujar_footer(c, y0):
    """Recuadro 'Recibí Conforme' y el texto legal, anclados al piso de la
    mitad (y0) para que su posición no dependa de cuánto ocupó la tabla.
    """
    y_legal = y0 + 5 * mm
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(colors.black)
    c.drawCentredString(
        ANCHO / 2, y_legal,
        "En el presente comprobante, implica la conformidad del retiro de la mercadería arriba detallada.",
    )

    alto_caja = ALTO_FOOTER - 10 * mm
    y_caja = y_legal + 5 * mm
    x_caja = ANCHO - MARGEN - ANCHO_CAJA_RECIBI
    top = y_caja + alto_caja

    c.setLineWidth(0.75)
    c.rect(x_caja, y_caja, ANCHO_CAJA_RECIBI, alto_caja, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(x_caja + ANCHO_CAJA_RECIBI / 2, top - 4 * mm, "Recibí Conforme")

    ancho_interno = ANCHO_CAJA_RECIBI - 6 * mm
    _renglon(c, x_caja + 3 * mm, top - 9 * mm, ancho_interno, "Firma")
    _renglon(c, x_caja + 3 * mm, top - 14 * mm, ancho_interno, "Aclaración")
    _renglon(c, x_caja + 3 * mm, top - 19 * mm, ancho_interno, "D.N.I. N°")


def _dibujar_remito(c, y0, numero, fecha_str, trabajo, cliente):
    """Un remito completo, dibujado dentro de la mitad que arranca en y0."""
    y = y0 + MITAD - 8 * mm
    y = _dibujar_header(c, y, numero, fecha_str)
    y = _dibujar_cliente(c, y, cliente)
    y -= 1.5 * mm
    y = _dibujar_leyenda_tabla(c, y)
    _dibujar_tabla(c, y, trabajo)
    _dibujar_footer(c, y0)


def _dibujar_guia_corte(c):
    c.saveState()
    c.setStrokeColor(colors.grey)
    c.setDash([3, 3], 0)
    c.setLineWidth(0.75)
    c.line(0, MITAD, ANCHO, MITAD)
    c.restoreState()


def construir_entrega_pdf(trabajo, cliente) -> bytes:
    """Devuelve los bytes del PDF de la orden de entrega (remito), duplicado
    en la mitad superior e inferior de una hoja A4 para cortar con guillotina.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    numero = texto(trabajo.numero_remito)
    c.setTitle(f"Orden de entrega {numero}")

    fecha = trabajo.fecha_remito_impreso or trabajo.fecha_creacion
    fecha_str = fecha.strftime("%d/%m/%Y") if fecha else "-"

    _dibujar_remito(c, MITAD, numero, fecha_str, trabajo, cliente)
    _dibujar_remito(c, 0, numero, fecha_str, trabajo, cliente)
    _dibujar_guia_corte(c)

    c.showPage()
    c.save()
    return buffer.getvalue()
