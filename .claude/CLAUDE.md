# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CRM interno para la gestión del taller "Gráfica Viamonte": clientes, trabajos, presupuestos, stock, gastos, cheques y movimientos de caja. Es una app monolítica pensada para correr localmente en la PC del local (no multi-tenant, sin usuarios reales).

## Architecture

- **Backend**: FastAPI (`main.py`), SQLAlchemy ORM sobre SQLite (`viamonte.db`, archivo en la raíz del repo). `database.py` define el engine/sessionmaker y el helper `get_db()` usado como dependencia en todos los routers.
- **Modelos** (`models.py`) y **schemas Pydantic** (`schemas.py`) están cada uno en un único archivo grande y plano, no separados por módulo. Al agregar un campo a una entidad hay que tocar ambos archivos (el modelo SQLAlchemy y el/los schema Pydantic correspondientes — Create/Update/Response), además del router.
- **Routers** (`routers/`): un archivo por entidad (`clientes.py`, `trabajos.py`, `presupuestos.py`, `stock.py`, `gastos.py`, `cheques.py`, `movimientos.py`, `notas.py`, `auth.py`), cada uno con su propio `APIRouter(prefix="/api/...")`, montado en `main.py`. `routers/respaldo.py` está comentado/deshabilitado — la ruta de backup real vive directamente en `main.py` (`GET /api/backup`).
- **Relaciones clave**: `Cliente` → `Trabajo` (1-N), `Trabajo` → `Nota` (1-N), `Cliente` → `Movimiento` (pagos). `Presupuesto` tiene auto-referencia (`version_de`) para versionado/historial de duplicados y puede vincularse a un `Trabajo` una vez convertido (`convertido_a_trabajo`). `Gasto` puede opcionalmente asociarse a un `Trabajo`. `ArticuloStock` tiene `HistorialStock` para auditar ajustes de cantidad.
- **IDs**: todas las tablas usan UUID string como PK (`default=lambda: str(uuid.uuid4())`), no autoincrement.
- **Frontend**: HTML/CSS/JS plano sin build step, en `frontend/` (`index.html`, `app.js`, `style.css`). SPA de una sola página con tabs (`switchTab`), consume la API vía `fetch` contra `API_URL = 'http://localhost:8000/api'` (hardcodeado). Usa SweetAlert2 (`Swal`) para diálogos/alertas.
- **Auth**: extremadamente simple e intencionalmente hardcodeada (usuario/contraseña fijos `admin` / `viamonte2026`), sin tokens ni hashing — existe solo como candado básico para uso local. Hay dos endpoints de login duplicados: `POST /api/login` (en `main.py`) y `POST /api/auth/login` (en `routers/auth.py`); el frontend usa el segundo. La sesión se persiste en `localStorage` del browser (`viamonte_sesion`), no hay JWT/cookies de servidor.
- **CORS** está abierto a `*` — asumido seguro porque corre solo en localhost.

## Running the app

Backend (desde la raíz del repo):
```
uvicorn main:app --reload
```
Esto crea automáticamente las tablas en `viamonte.db` si no existen (`models.Base.metadata.create_all` en `main.py`).

Frontend: abrir `frontend/index.html` directamente en el navegador (no hay bundler/dev server; asume que el backend corre en `localhost:8000`).

No hay suite de tests, linter ni configuración de CI en el repo.
