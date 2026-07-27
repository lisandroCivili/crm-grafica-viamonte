"""Schemas de Empleado y de la planilla de asistencia.

Las horas trabajadas nunca se reciben ni se persisten: se derivan de entrada y
salida con calculos.horas_trabajadas y se exponen como campo calculado, igual
que el total de un presupuesto se deriva de sus ítems.
"""
from pydantic import BaseModel, computed_field, model_validator
from typing import Optional
from datetime import date, time
from decimal import Decimal

from calculos import horas_trabajadas

# --- ESQUEMAS PARA EMPLEADOS ---
class EmpleadoBase(BaseModel):
    nombre: str
    activo: bool = True

class EmpleadoCreate(EmpleadoBase):
    pass

class EmpleadoResponse(EmpleadoBase):
    id: str
    model_config = {"from_attributes": True}

# Esquema para EDITAR un empleado existente (renombrar, dar de baja o rehabilitar)
class EmpleadoUpdate(BaseModel):
    nombre: Optional[str] = None
    activo: Optional[bool] = None


# --- ESQUEMAS PARA LA PLANILLA DEL DÍA ---
def _validar_salida_posterior_a_entrada(fila):
    """La salida tiene que ser más tarde que la entrada.

    No se interpreta como turno que cruza la medianoche porque en el taller no
    existe: si la salida da antes, es un error de tipeo (18:00 tecleado como
    8:00), y dejarlo pasar mete un día raro en el total de horas del mes.

    Compartido por las filas que se guardan; se corta acá para que un horario
    imposible no llegue nunca a la base.
    """
    if (
        fila.hora_entrada is not None
        and fila.hora_salida is not None
        and fila.hora_salida <= fila.hora_entrada
    ):
        raise ValueError(
            f"La hora de salida ({fila.hora_salida:%H:%M}) tiene que ser posterior "
            f"a la de entrada ({fila.hora_entrada:%H:%M})."
        )
    return fila


class FilaPlanillaGuardar(BaseModel):
    """Una fila de la planilla tal como la manda el frontend al guardar el día.

    Los tres campos son opcionales: una fila enteramente vacía significa que ese
    empleado no tiene nada cargado ese día, y el router la usa para borrar un
    registro anterior (así se deshace una carga equivocada).
    """
    empleado_id: str
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    observaciones: Optional[str] = None

    _horario_valido = model_validator(mode="after")(_validar_salida_posterior_a_entrada)

class PlanillaGuardarRequest(BaseModel):
    fecha: date
    filas: list[FilaPlanillaGuardar]

class FilaPlanillaResponse(BaseModel):
    """Un empleado activo y lo que tenga cargado esa fecha.

    Viene una fila por empleado, tenga registro o no: los que no trabajaron ese
    día llegan con las horas en null. Así el frontend dibuja la grilla completa
    sin tener que cruzar la lista de empleados con la de registros.
    """
    empleado_id: str
    nombre: str
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    observaciones: Optional[str] = None

    @computed_field
    @property
    def horas(self) -> Optional[Decimal]:
        return horas_trabajadas(self.hora_entrada, self.hora_salida)

class PlanillaDiaResponse(BaseModel):
    fecha: date
    filas: list[FilaPlanillaResponse]


# --- ESQUEMAS PARA EL RESUMEN POR PERÍODO ---
class ResumenEmpleadoResponse(BaseModel):
    """Cuánto trabajó un empleado entre dos fechas.

    dias_trabajados cuenta sólo los días con la jornada completa (entrada y
    salida): un día a medio cargar no suma horas, así que tampoco debería contar
    como día trabajado.
    """
    empleado_id: str
    nombre: str
    dias_trabajados: int
    total_horas: Decimal
