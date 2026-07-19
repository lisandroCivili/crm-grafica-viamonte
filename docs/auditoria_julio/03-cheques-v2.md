# Prioridad 3 — Paquete "Cheques v2": trabajo_id, historial + estados, Emitidos/Endosados

> Auditoría julio 2026. Hallazgos **I1**, **I2** e **I3** (Importantes), con **I4** e **I5** como complemento del mismo módulo.
> Motivo de la prioridad: los cheques ya impactan saldo e ingresos, pero les faltan
> las reglas que el CLAUDE.md exige ("nunca perder historial del cambio") y hay
> agujeros conceptuales que distorsionan ganancia y egresos.

## Estado actual (referencias)

- `models.py` — `Cheque`: `clasificacion` (Recibido/Emitido), `trabajo_id` (nullable),
  estados usados: En Cartera / Depositado / Cobrado / Endosado / Rechazado. **No existe** tabla de historial de cheques.
- `routers/cheques.py` (~21-32) — CRUD pelado: PATCH acepta cualquier cambio, DELETE sin restricciones.
- `calculos.py`:
  - `_monto_cheques_recibidos`: todo cheque Recibido no-Rechazado **salda deuda** del cliente.
  - `ingresos_reales`: cheques Recibidos **Cobrados** suman a ingresos por `fecha_cobro`.
  - `ganancia_bruta_realizada` (~171-189): agrupa cobros **por `trabajo_id`** → cheques sin trabajo no aportan ganancia jamás.
- `frontend/app.js` — drawer de cheques y KPI "Cheques en Cartera" (~2645-2663).
- `frontend/index.html` — form de cheques (~1228+): sin selector de trabajo, sin campo destinatario en alta.

---

## I1. Cheques recibidos sin `trabajo_id` nunca aportan ganancia

### Escenario de fallo
Un cheque cargado desde el módulo Cheques (no desde el drawer de Pago de la ficha)
nace sin `trabajo_id` porque el form no lo ofrece. Al marcarse **Cobrado**:
- ✔ suma a ingresos (`ingresos_reales`),
- ✔ salda la deuda del cliente,
- ✘ `ganancia_bruta_realizada` lo saltea (agrupa por `trabajo_id`),
- ✘ el flag "cobrado" del informe de trabajos tampoco lo ve.

**La ganancia neta del dashboard queda subestimada en silencio.**

### Solución propuesta
1. Agregar al form de cheques recibidos un **selector de trabajo (opcional)**,
   filtrado por el cliente elegido (mismo patrón que el drawer de gastos).
2. Si se guarda un cheque Recibido sin trabajo, mostrar un aviso no bloqueante:
   "Este cheque saldará la deuda del cliente pero no se imputará a ningún trabajo
   (no aportará ganancia al dashboard)".
3. Permitir asignar el trabajo después vía PATCH (el campo ya existe en `ChequeUpdate` — verificar).

---

## I2. Sin máquina de estados ni historial de cheques

### Escenario de fallo
`PATCH /api/cheques/{id}` hoy permite:
- `Cobrado → En Cartera` (deshace un ingreso sin rastro),
- cambiar el **monto** de un cheque ya Cobrado (modifica ingresos y ganancia retroactivamente),
- reclasificar `Recibido → Emitido` (cambia el saldo del cliente en silencio),
- `DELETE` de un cheque Cobrado.

Viola la regla del CLAUDE.md: "Cheque: puede pasar por distintos estados. Nunca perder historial del cambio."

### Solución propuesta
1. **Nueva tabla `HistorialCheque`** (mismo patrón que `HistorialStock`): id UUID,
   cheque_id FK, fecha, estado_anterior, estado_nuevo, detalle (texto libre, ej.
   "monto 5000→6000"). Crear asiento en cada PATCH que cambie estado, monto o clasificación.
   Requiere migración (`migracion_historial_cheques.py`, mismo patrón idempotente
   con backup que las migraciones existentes).
2. **Transiciones válidas** en el PATCH (función privada `_validar_transicion`):
   - `En Cartera → Depositado | Endosado | Rechazado`
   - `Depositado → Cobrado | Rechazado`
   - `Cobrado / Endosado / Rechazado` → estados finales (para revertir: exigir
     motivo en el body y registrarlo en historial; o directamente 409).
3. **Bloquear** en PATCH la edición de `monto` y `clasificacion` cuando el estado
   es Cobrado o Endosado (400 con mensaje claro).
4. **DELETE**: rechazar (409) si el estado es Cobrado o Endosado; para el resto,
   evaluar si conviene también bloquearlo y dejar solo "Rechazado/Anulado" como salida.
5. Schemas: agregar `HistorialChequeResponse` y endpoint `GET /api/cheques/{id}/historial`.

---

## I3. Emitidos y Endosados nunca tocan los egresos ni realizan ganancia

### Escenario de fallo
- Pagar a un proveedor con **cheque propio (Emitido)** o **endosando** uno recibido
  no genera `Gasto` → los egresos del dashboard (que solo suman la tabla `gastos`,
  `calculos.py` ~192-198) quedan subestimados → **ganancia neta sobrestimada**,
  salvo doble carga manual.
- Un cheque Recibido que se **Endosa** jamás pasa a "Cobrado" → ese dinero saldó
  la deuda del cliente y pagó a un proveedor, pero **nunca entra a ingresos ni
  realiza la ganancia del trabajo**. Conceptualmente, endosar = ingreso + egreso simultáneos.

### Solución propuesta
1. Al pasar un cheque a **Endosado** (o al crear/entregar un **Emitido**):
   ofrecer en el mismo flujo la creación del `Gasto` asociado (Swal con
   descripción/categoría/destinatario precargados). Como mínimo, aviso claro.
2. En `calculos.py`, tratar **Endosado como cobro** a efectos de `ingresos_reales`
   y `ganancia_bruta_realizada` (usar `fecha_endoso` o la fecha del cambio de
   estado del historial nuevo). Documentar la regla en el propio módulo, como ya
   se hace con las demás.
3. Decisión de negocio a confirmar con el usuario antes de implementar el punto 2:
   ¿el endoso cuenta como ingreso+egreso el mismo día, o prefieren netearlo?

---

## Complementos del mismo módulo

### I4. Rechazar `metodo="Cheque"` en movimientos (doble conteo latente)
`calcular_saldo_cliente` suma todos los movimientos 'Pago' (incluido `metodo="Cheque"`)
mientras `ingresos_reales` los excluye. La UI nunca los crea (bifurca bien a `/cheques/`),
pero la API lo permite → fila contada en saldo y jamás en ingresos; si el cheque físico
además está en Cheques, **saldo doble**.
**Fix**: en `POST /api/movimientos/` (y PUT), si `tipo=='Pago'` y `metodo=='Cheque'`
→ 400 "Los cheques se registran desde el módulo Cheques". No tocar filas históricas.

### I5. KPI "Cheques en Cartera" suma también los Emitidos
`app.js` ~2645-2663: no filtra por `clasificacion` → un cheque propio entregado a
un proveedor (plata que va a **salir**) se muestra como plata por cobrar, y aparece
en las alertas de vencimiento con cliente "Desc.".
**Fix**: filtrar `c.clasificacion === 'Recibido'` para el KPI y las alertas;
opcionalmente mostrar los Emitidos en cartera como KPI aparte ("Cheques a pagar").

---

## Verificación
- [ ] Cheque recibido con trabajo asignado, al cobrarse: aparece en ingresos Y en ganancia del trabajo.
- [ ] Cheque recibido sin trabajo: aviso al guardar; se puede asignar trabajo después.
- [ ] PATCH `Cobrado → En Cartera` directo: rechazado (o exige motivo y queda en historial).
- [ ] Cambiar monto de cheque Cobrado: 400.
- [ ] DELETE de cheque Cobrado: 409.
- [ ] Todo cambio de estado genera fila en `historial_cheques`.
- [ ] Endosar un cheque: ofrece crear el Gasto; ingresos/ganancia lo computan según la regla acordada.
- [ ] POST movimiento Pago con metodo Cheque: 400.
- [ ] KPI cartera solo suma Recibidos; Emitidos no aparecen como plata por cobrar.
- [ ] Migración corrida sobre copia de la DB real sin errores (idempotente, con backup).
