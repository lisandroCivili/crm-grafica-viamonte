"""Lógica sobre un Trabajo compartida por routers/trabajos.py y
routers/entregas.py.

Vive en la raíz y no en ninguno de los dos routers por el mismo criterio que
ya usa validar_papel en papel.py ("para que no puedan divergir", ver el
comentario en routers/presupuestos.py): el proyecto evita que un router
importe de otro, así que lo que necesitan los dos sale a un módulo propio en
vez de compartirse de uno a otro.
"""


def resumen_trabajo(trabajo) -> str:
    """Cómo se nombra este trabajo en el registro de auditoría.

    Por el número de orden cuando ya se imprimió, que es como lo llaman en el
    taller; hasta entonces, por lo que es. El cliente va siempre: en una lista
    de cambios "Volantes A5" sin apellido no alcanza para saber cuál era.
    """
    quien = trabajo.cliente.nombre_completo if trabajo.cliente else "sin cliente"
    que = trabajo.numero_orden or f"{trabajo.cantidad}x {trabajo.descripcion_producto}"
    return f"{que} ({quien})"


def saldo_pendiente_entrega(trabajo) -> int:
    """Cuánto falta entregar del trabajo, sumando todos los remitos que lo
    incluyeron (trabajo.entregas: filas de ItemEntrega, ver models.py)."""
    return trabajo.cantidad - sum(item.cantidad for item in trabajo.entregas)
