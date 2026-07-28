"""Registro de quién modificó qué.

Vive en la raíz y no en routers/ porque lo importan todos los routers, igual que
seguridad.py, database.py o rutas.py: infraestructura transversal.

Son dos funciones y nada más:

- asentar() agrega la fila al log.
- cambios() arma el "de qué a qué" leyéndolo del propio SQLAlchemy.

El modelo (models.Auditoria) explica por qué la tabla es como es; acá está el
cómo se la escribe.
"""
from sqlalchemy import inspect
from sqlalchemy.orm import Session

import models


def asentar(
    db: Session,
    usuario: models.Usuario | None,
    accion: str,
    entidad: str,
    entidad_id: str | None,
    resumen: str,
    detalle: str | None = None,
) -> None:
    """Agrega una fila al log. NO commitea.

    Se suma a la sesión del endpoint y viaja con SU commit, mismo criterio que
    _asentar() en routers/cheques.py. Es lo que garantiza que un endpoint que
    falla después (un 400 de validación, un IntegrityError) no deje una fila
    diciendo que algo pasó cuando no pasó nada.

    usuario en None es el intento de ingreso fallido: no hay a quién apuntar,
    pero el intento igual queda. En ese caso el llamador pasa el nombre tipeado
    como resumen y acá se guarda 'desconocido' como autor.
    """
    db.add(models.Auditoria(
        usuario_id=usuario.id if usuario else None,
        usuario_nombre=usuario.nombre if usuario else "desconocido",
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        resumen=resumen,
        detalle=detalle,
    ))


def cambios(obj, ocultar: tuple[str, ...] = ()) -> str | None:
    """Qué columnas cambiaron y de qué a qué: "estado: Aprobado -> En Diseño".

    Lo lee del historial de atributos de SQLAlchemy en vez de pedirle a cada
    endpoint que se guarde una copia del objeto antes de tocarlo: serían veinte
    bloques de diff repetidos, que es justo la duplicación que el proyecto evita.

    CUÁNDO SE LLAMA: después de los setattr y ANTES del commit. Un flush() en el
    medio limpia el historial y esto devolvería None (o sea, "no cambió nada").
    Funciona porque las sesiones son autoflush=False (database.py).

    Devuelve None si no hubo ningún cambio real: un PUT que manda los mismos
    valores que ya estaban no tiene por qué ensuciar el log.

    'ocultar' es para los campos que no pueden terminar escritos en una pantalla
    (password_hash). Hoy ningún endpoint edita usuarios; el día que exista, el
    hash no se copia al log.
    """
    estado = inspect(obj)
    partes = []

    for attr in estado.mapper.column_attrs:
        if attr.key in ocultar:
            continue

        historia = estado.attrs[attr.key].history
        if not historia.has_changes():
            continue

        # deleted/added son listas porque la API contempla colecciones; para una
        # columna simple traen a lo sumo un elemento.
        anterior = historia.deleted[0] if historia.deleted else None
        nuevo = historia.added[0] if historia.added else None

        # Un campo que estaba vacío y sigue vacío no es un cambio: pasa cuando
        # el formulario manda "" donde la base tiene None.
        if anterior == nuevo:
            continue

        partes.append(f"{attr.key}: {_mostrar(anterior)} -> {_mostrar(nuevo)}")

    return "; ".join(partes) or None


def _mostrar(valor) -> str:
    """El valor como se lee en el log. None se escribe '(vacío)' y no 'None'."""
    if valor is None or valor == "":
        return "(vacío)"
    return str(valor)
