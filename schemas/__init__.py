"""Schemas Pydantic del CRM, divididos por entidad.

Reemplaza al viejo schemas.py monolítico (583 líneas, las 9 entidades juntas).
Este __init__ re-exporta todos los nombres públicos, así que `import schemas` +
`schemas.TrabajoCreate` siguen funcionando igual en routers y tests: ningún
import de afuera tuvo que cambiar. Los Create/Update/Response de cada entidad se
mantienen separados, como pide la convención del proyecto.
"""
from .auth import LoginRequest, TokenResponse, UsuarioResponse
from .clientes import ClienteBase, ClienteCreate, ClienteResponse, ClienteUpdate
from .trabajos import (
    TrabajoBase,
    TrabajoCreate,
    TrabajoUpdate,
    TrabajoResponse,
    IniciarDisenoRequest,
    AplicarSaldoFavorResponse,
)
from .presupuestos import (
    ItemPresupuestoBase,
    ItemPresupuestoCreate,
    ItemPresupuestoResponse,
    PresupuestoBase,
    PresupuestoCreate,
    PresupuestoResponse,
    PresupuestoUpdate,
)
from .movimientos import MovimientoCreate, MovimientoResponse, MovimientoUpdate
from .notas import NotaCreate, NotaResponse, NotaUpdate
from .gastos import GastoBase, GastoCreate, GastoResponse, GastoUpdate
from .stock import (
    StockBase,
    StockCreate,
    StockUpdate,
    CompraStockItem,
    StockResponse,
    HistorialStockResponse,
)
from .cheques import (
    ChequeBase,
    ChequeCreate,
    ChequeUpdate,
    ChequeResponse,
    HistorialChequeResponse,
)
from .reportes import (
    InformeTrabajoRow,
    SaldoResponse,
    MorosoResponse,
    DashboardResponse,
)
from .asistencia import (
    EmpleadoBase,
    EmpleadoCreate,
    EmpleadoUpdate,
    EmpleadoResponse,
    FilaPlanillaGuardar,
    PlanillaGuardarRequest,
    FilaPlanillaResponse,
    PlanillaDiaResponse,
    ResumenEmpleadoResponse,
)
