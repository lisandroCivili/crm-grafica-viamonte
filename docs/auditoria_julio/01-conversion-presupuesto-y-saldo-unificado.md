-# Prioridad 1 — Conversión Presupuesto→Trabajo transaccional + Saldo de cliente unificado

> Auditoría julio 2026. Hallazgos **C1** y **C4** (Críticos).
> Motivo de la prioridad: ambos generan decisiones comerciales sobre datos falsos
> (trabajos que "se convirtieron" pero no existen, clientes que figuran morosos estando al día).

---

## C1. `convertirATrabajo` no valida nada y reporta éxito falso

### Archivos involucrados
- `frontend/app.js` — función `convertirATrabajo` (~línea 1551-1637)
- `routers/presupuestos.py` — endpoint `marcar_convertido` (~línea 210-221)
- `routers/trabajos.py` — `crear_trabajo` (no valida existencia de `cliente_id`/`papel_id` antes del commit → FK falla con 500)
- `schemas.py` — `TrabajoBase.cliente_id: str` (obligatorio)

### Escenario de fallo (verificado en código)
Con un presupuesto **sin cliente asignado** (`cliente_id` es nullable en el modelo `Presupuesto`):

1. `convertirATrabajo` arma `dataTrabajo` con `cliente_id: null` y hace
   `POST /api/trabajos/` **sin chequear `resp.ok`** → el backend responde **422**
   (`cliente_id` es obligatorio en `TrabajoBase`).
2. `nuevoTrabajo.id` queda `undefined` → llama
   `PUT /api/presupuestos/{id}/convertir/undefined`.
3. `marcar_convertido` **no valida nada**: ni que el trabajo exista, ni que el
   presupuesto no esté ya convertido, ni duplicados. Intenta commitear
   `trabajo_id="undefined"` → la FK (activada por PRAGMA en `database.py`) lo
   rechaza → **500**.
4. El frontend tampoco chequea ese response → ejecuta `Swal.fire('¡Enviado!', ...)`.
   **El usuario cree que el trabajo está en el tablero y no existe.**

Problema adicional aun con cliente asignado: el flujo son **dos requests sin
transacción**. Si el paso 2 falla, queda un trabajo creado sin presupuesto
vinculado (aparece con badge "⚠️ Sin presupuesto" sin que nadie lo decidiera).

Ojo también con el flujo de "versión corregida": `convertirATrabajo` cancela el
trabajo anterior (~app.js:1614-1621) — ese paso también va sin control de errores.

### Solución propuesta
1. **Backend**: crear un endpoint único y transaccional
   `POST /api/presupuestos/{presupuesto_id}/convertir` que:
   - Valide que el presupuesto existe → 404 si no.
   - Valide `presupuesto.cliente_id is not None` → 400 "Asigná un cliente antes de convertir".
   - Valide que no esté ya convertido (`estado == 'Convertido'` o `trabajo_id` ya seteado) → 409.
   - Cree el `Trabajo` (copiando descripción, precio, cantidad, etc. — reusar la
     lógica que hoy arma el frontend en `dataTrabajo`) y marque el presupuesto
     `estado='Convertido'` + `trabajo_id` **en la misma transacción** (un solo commit).
   - Devuelva el `TrabajoResponse` creado.
   - **No eliminar** el endpoint viejo `PUT /convertir/{trabajo_id}` (regla CLAUDE.md:
     no romper endpoints), pero sí agregarle validaciones: trabajo existe (404),
     presupuesto no convertido (409).
2. **Frontend** (`convertirATrabajo`):
   - Antes de nada: si `!p.cliente_id`, mostrar Swal pidiendo asignar cliente y abortar.
   - Reemplazar los dos fetch por uno solo al endpoint nuevo.
   - Chequear `resp.ok`; si falla, mostrar el `detail` del error en un Swal de error,
     nunca "¡Enviado!".
   - Mantener el flujo de cancelar la versión anterior, también con chequeo de `resp.ok`.

### Verificación
- [x] Convertir presupuesto sin cliente → mensaje claro, no se crea trabajo, no se marca convertido.
- [x] Convertir presupuesto válido → trabajo aparece en kanban y presupuesto queda convertido (flag `convertido_a_trabajo`; ver notas post-implementación).
- [x] Convertir dos veces el mismo presupuesto → 409, no se duplica el trabajo.
- [x] Matar el backend a mitad de conversión → no queda trabajo huérfano (transacción única, `db.flush()` + un solo commit).
- [x] El endpoint viejo sigue respondiendo (compatibilidad), ahora con 404/409 en vez de 500.

---

## C4. Tres definiciones de "saldo de cliente"; dos ignoran los cheques

### Archivos involucrados
- `calculos.py` — `calcular_saldo_cliente` (~105-120) y `calcular_saldo_trabajo`:
  **fuente de verdad correcta** = facturado (trabajos no Cancelados) −
  (movimientos 'Pago' + cheques Recibidos no Rechazados). Usada por la ficha
  (`GET /api/movimientos/saldo/{cliente_id}`).
- `frontend/app.js` — `cargarClientes` (~702-714): calcula saldo **solo con
  movimientos**, ignora cheques.
- `frontend/app.js` — dashboard morosos / "Plata en la calle" (~2632-2637 y
  ~2713-2729): ídem, solo movimientos.

### Escenario de fallo
Cliente paga el 100% con cheque (En Cartera o Cobrado):
- Su **ficha** dice "$0, al día" (verde) — backend.
- La **tabla de clientes** lo muestra debiendo todo (rojo) — frontend.
- Si el trabajo está Entregado, aparece en el **semáforo de morosos** del dashboard.

Dos pantallas de la misma app se contradicen sobre quién debe plata.

### Solución propuesta
Unificar en el backend como única fuente de verdad:
1. **Nuevo endpoint batch** `GET /api/clientes/saldos` (o `/api/reportes/saldos`)
   que devuelva `[{cliente_id, saldo}]` para todos los clientes usando
   `calcular_saldo_cliente` — evita N requests desde el listado. Cuidado con N+1:
   traer trabajos, movimientos y cheques en 3 queries y agrupar en memoria
   (mismo patrón que `informe-trabajos` en `routers/presupuestos.py`).
2. `cargarClientes` consume ese endpoint y elimina su cálculo local.
3. Para morosos/"plata en la calle" del dashboard: mover el cálculo al backend
   (extender `GET /api/reportes/dashboard` con la lista de morosos usando
   `calcular_saldo_trabajo`, que ya contempla cheques con `trabajo_id`), o al
   menos hacer que el frontend sume también los cheques Recibidos no Rechazados
   por `trabajo_id`/cliente al armar `pagosPorTrabajo`.

### Nota de implementación
Los montos llegan al JS como **strings** (Pydantic v2 serializa Decimal como
string) — cualquier suma en el frontend debe pasar por `Number(...)`.
Ver archivo 02 de esta auditoría.

### Verificación
- [x] Cliente que pagó todo con cheque: saldo $0 en ficha, tabla y dashboard.
- [x] Cheque Rechazado: la deuda reaparece en las tres vistas.
- [x] Cliente con pagos mixtos (efectivo + cheque): mismo número en las tres vistas.
- [x] El listado de clientes no dispara una request por cliente (batch).

---

## Notas post-implementación (18/07/2026)

C1 y C4 quedaron implementados y verificados end-to-end. Ajustes respecto del
literal de este documento:

- **El presupuesto convertido queda en `estado="Aprobado"`, no "Convertido"**:
  el frontend decide qué mostrar por el flag `convertido_a_trabajo` (no por
  `estado`), y `routers/trabajos.py` sincroniza `presupuesto.estado =
  trabajo.estado` en cada cambio de estado del trabajo — un estado "Convertido"
  sería pisado en el primer PUT. La verificación "queda Convertido" se
  satisface con el flag.
- Los morosos del dashboard se movieron al **backend** (opción preferida):
  `GET /api/reportes/dashboard` ahora devuelve `plata_en_la_calle` y `morosos`
  (schema `MorosoResponse`). El cálculo local de `app.js` quedó solo como
  fallback si el backend no responde — ese fallback sigue ignorando cheques
  (ver archivo 05, menor 6).
- El batch quedó en `GET /api/clientes/saldos`. Si algún día se agrega
  `GET /api/clientes/{cliente_id}`, la ruta `/saldos` debe declararse antes
  (hay comentario en `routers/clientes.py`).
- Hallazgo lateral de la verificación: `notas_iniciales` nunca se guardaba en
  la conversión vieja (Pydantic lo descartaba en silencio); ahora persiste,
  pero no se expone en `TrabajoResponse`. Detalle en archivo 05, menor 14.
