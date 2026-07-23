"""
Armado del PDF del Presupuesto (el comprobante que ve el cliente).

Módulo plano, hermano de orden_pdf.py: no toca la base de datos ni tiene
efectos. Recibe el presupuesto y el cliente ya cargados y devuelve los bytes del
PDF. La lógica de layout vive acá y no en el router para no meter cien líneas de
diseño adentro de un endpoint.

A diferencia de la orden de producción (que dibuja filas a mano con el canvas),
el presupuesto tiene una tabla real cuyas celdas envuelven texto en varias
líneas, así que se arma con platypus (Table/Paragraph): calcular esos saltos a
mano con el canvas sería frágil. El resto del comprobante (header, total, firma,
pie) se dibuja encima con el canvas.

Estructura, de arriba hacia abajo:
- Banda oscura: logo a la izquierda, "PRESUPUESTO" grande a la derecha.
- Datos de la gráfica a la izquierda / fecha de emisión a la derecha.
- Bloque del cliente.
- Tabla de ítems + caja TOTAL.
- Firma escaneada + firmante, y el pie con el contacto.

Fidelidad acordada con el usuario: limpio y profesional, no pixel-perfect. No se
clona la cola triangular del header del diseño original.
"""
import os
import sys
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ANCHO, ALTO = A4

MARGEN = 18 * mm
ALTO_HEADER = 42 * mm
ALTO_LOGO = 34 * mm

# Datos fijos del comprobante (los mismos que hoy pone el frontend a mano). Si
# alguna vez cambian, se tocan en un solo lugar.
EMPRESA = "Gráfica Viamonte"
EMPRESA_SUB = "de Soria Daniel Enrique"
CIUDAD = "S.M. de Tucumán"
MAIL = "igv.srl@hotmail.com"
WHATSAPP = "WhatsApp: +54 381 239-4798"
FIRMANTE = "Grafica Viamonte"
FIRMANTE_SUB = "de Soria Daniel Enrique"

# Paleta del comprobante.
NEGRO_HEADER = colors.HexColor("#111111")
GRIS_CABECERA = colors.HexColor("#e6e6e6")
GRIS_BORDE = colors.HexColor("#cccccc")
GRIS_TEXTO = colors.HexColor("#555555")


def _ruta_asset(nombre):
    """Ruta de un asset de frontend/assets/, o None si no existe.

    Misma lógica que orden_pdf._ruta_logo: empaquetado con PyInstaller los
    archivos se extraen a sys._MEIPASS; en desarrollo se usa la carpeta del
    proyecto. El .spec ya incluye datas=[('frontend','frontend')].
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    ruta = os.path.join(base, "frontend", "assets", nombre)
    return ruta if os.path.exists(ruta) else None


def _texto(valor):
    """Normaliza un valor para imprimirlo: None y vacío se muestran como '-'."""
    if valor is None:
        return "-"
    texto = str(valor).strip()
    return texto if texto else "-"


def _pesos(valor):
    """Formatea un monto al estilo argentino: 1.890.000 o 1.890.500,50.

    Igual criterio que fmtMoney del frontend, pero omite los decimales cuando
    son cero, que es como se ve el PDF de referencia (precios enteros). Sin
    símbolo $: cada lugar decide si lo antepone.
    """
    numero = Decimal(valor or 0)
    entero = int(numero)
    centavos = int((abs(numero) - abs(entero)) * 100)
    miles = f"{entero:,}".replace(",", ".")
    return miles if centavos == 0 else f"{miles},{centavos:02d}"


def _fecha(presupuesto):
    return presupuesto.fecha_creacion.strftime("%d/%m/%Y") if presupuesto.fecha_creacion else "-"


# Y donde arranca a dibujarse el cuerpo del documento (tabla y siguientes), por
# debajo del encabezado. Coordenada absoluta A4 (595x842).
Y_INICIO_CUERPO = 700


def _dibujar_header(c, presupuesto, cliente):
    """Encabezado del comprobante, coordenadas absolutas A4 (595x842).

    Franja negra con muesca diagonal: es más ALTA del lado del logo (izquierda) y
    más BAJA del lado de 'PRESUPUESTO' (derecha), unidas por una diagonal en el
    medio. El logo va en blanco sobre el negro; debajo de la parte derecha (que es
    más baja) queda blanco, y ahí va la FECHA en negro. 'Cliente' va más abajo,
    también en negro sobre blanco.
    """
    ruta_logo = _ruta_asset("logo-presupuesto-cl.png")
    nombre_cliente = cliente.nombre_completo if cliente else "Sin cliente"
    fecha_str = _fecha(presupuesto)

    # 1. Franja negra con la muesca diagonal (misma forma que el diseño original).
    c.setFillColor(colors.black)
    p = c.beginPath()
    p.moveTo(0, 842)      # sup izq
    p.lineTo(595, 842)    # sup der
    p.lineTo(595, 776)    # baja por la derecha (parte corta, deja blanco abajo)
    p.lineTo(265, 776)    # hacia la izquierda por el borde de la parte corta
    p.lineTo(228, 748)    # diagonal bajando hacia la izquierda
    p.lineTo(0, 748)      # borde izquierdo (parte alta, bajo el logo)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # 2. Logo blanco, grande, sobre el negro (izquierda).
    if ruta_logo:
        c.drawImage(ruta_logo, -100, 700, width=450, height=190,
                    preserveAspectRatio=True, mask="auto")

    # 3. PRESUPUESTO en blanco (arriba a la derecha, sobre el negro).
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawRightString(565, 800, "PRESUPUESTO")

    # 4. Fecha en NEGRO sobre blanco, debajo de la parte derecha (corta) del negro.
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawRightString(565, 758, f"Fecha de emisión: {fecha_str} - S.M. de Tucumán.")

    # 5. Línea divisoria y 'Cliente' en negro sobre blanco (izquierda).
    c.setStrokeColor(GRIS_BORDE)
    c.setLineWidth(0.7)
    c.line(30, 742, 565, 742)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)
    c.drawString(30, 726, f"Cliente: {nombre_cliente}")


def _construir_tabla(presupuesto):
    """Tabla de ítems (Producto / Cantidad / P. Unitario / P. Total).

    Devuelve el Table de platypus ya estilado, listo para wrapOn/drawOn. La
    descripción va como Paragraph para que envuelva en varias líneas.
    """
    estilo_desc = ParagraphStyle("desc", fontName="Helvetica", fontSize=10, leading=13)

    encabezado = ["Producto", "Cantidad", "Precio\nUnitario", "Precio\nTotal"]
    filas = [encabezado]
    for item in presupuesto.items:
        total_item = item.cantidad * item.precio_unitario
        filas.append([
            Paragraph(_texto(item.descripcion), estilo_desc),
            _texto(item.cantidad),
            _pesos(item.precio_unitario),
            _pesos(total_item),
        ])

    ancho_util = ANCHO - 2 * MARGEN
    col_desc = ancho_util - (28 * mm + 32 * mm + 32 * mm)
    tabla = Table(filas, colWidths=[col_desc, 28 * mm, 32 * mm, 32 * mm])
    tabla.setStyle(TableStyle([
        # Cabecera gris claro con texto negro.
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (1, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        # Cuerpo: cantidad centrada, precios a la derecha, total en negrita.
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("ALIGN", (2, 1), (3, -1), "RIGHT"),
        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
        # Filas todas en blanco (como el diseño de referencia).
        # Rejilla y aire.
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return tabla


def _dibujar_total(c, y, presupuesto):
    """Caja TOTAL: rectángulo ancho con borde, debajo de la tabla.

    Fondo blanco, borde negro y el texto right-aligned adentro, como en el diseño
    de referencia (la caja ocupa buena parte del ancho, no sólo el texto).
    """
    total = sum((i.cantidad * i.precio_unitario for i in presupuesto.items), Decimal("0"))
    texto = f"TOTAL:  $ {_pesos(total)}"

    pad = 8 * mm
    alto_caja = 13 * mm
    x0 = ANCHO * 0.34          # arranca cerca del centro
    x1 = ANCHO - MARGEN        # termina en el margen derecho
    y0 = y - alto_caja

    c.setFillColor(colors.white)
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(x0, y0, x1 - x0, alto_caja, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(x1 - pad, y0 + 4.3 * mm, texto)


def _dibujar_firma_y_pie(c):
    """Firma escaneada + firmante centrados (algo a la derecha del centro), y el
    contacto centrado al pie de la página.

    La firma se ancla a una banda fija en el tercio inferior para que siempre
    caiga sobre el pie, independientemente de cuántos ítems tenga la tabla.
    """
    ancho_firma = 48 * mm
    alto_firma = 26 * mm
    # Eje de la firma: centrada un poco a la derecha del centro, como el diseño.
    eje_firma = ANCHO * 0.6

    firma = _ruta_asset("firma-facu.png")
    # Base de la imagen de la firma; el nombre va justo debajo.
    y_base_firma = 40 * mm
    if firma:
        c.drawImage(
            firma, eje_firma - ancho_firma / 2, y_base_firma, width=ancho_firma,
            height=alto_firma, preserveAspectRatio=True, anchor="s", mask="auto",
        )

    # Línea corta bajo la firma + nombre del firmante, sobre el mismo eje.
    c.setStrokeColor(GRIS_BORDE)
    c.setLineWidth(0.7)
    c.line(eje_firma - 30 * mm, y_base_firma - 1 * mm, eje_firma + 30 * mm, y_base_firma - 1 * mm)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(eje_firma, y_base_firma - 6 * mm, FIRMANTE)
    c.setFillColor(GRIS_TEXTO)
    c.setFont("Helvetica", 9)
    c.drawCentredString(eje_firma, y_base_firma - 11 * mm, FIRMANTE_SUB)

    # Pie: contacto centrado, al borde inferior.
    c.setFillColor(GRIS_TEXTO)
    c.setFont("Helvetica", 9)
    c.drawCentredString(ANCHO / 2, 12 * mm, f"{MAIL}   |   {WHATSAPP}")


def construir_presupuesto_pdf(presupuesto, cliente) -> bytes:
    """Devuelve los bytes del PDF del presupuesto para el cliente.

    presupuesto trae sus items ya cargados (relación items); cliente puede ser
    None (borrador sin cliente asignado), y en ese caso se imprime "Sin cliente".
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    nro = presupuesto.numero_secuencia or "s/n"
    c.setTitle(f"Presupuesto {nro}")

    _dibujar_header(c, presupuesto, cliente)

    # El cuerpo (tabla y siguientes) arranca debajo del encabezado.
    y = Y_INICIO_CUERPO
    tabla = _construir_tabla(presupuesto)
    ancho_tabla, alto_tabla = tabla.wrapOn(c, ANCHO - 2 * MARGEN, ALTO)
    tabla.drawOn(c, MARGEN, y - alto_tabla)
    y = y - alto_tabla - 8 * mm

    _dibujar_total(c, y, presupuesto)
    _dibujar_firma_y_pie(c)

    c.showPage()
    c.save()
    return buffer.getvalue()
