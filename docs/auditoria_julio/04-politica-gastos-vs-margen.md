# Prioridad 4 — Política de gastos vs. margen de presupuesto (ganancia neta)

> Auditoría julio 2026. Hallazgos **I10**, **I11**, **I12** (Importantes) + **I9** (gastos UI).
>
> ✅ **RESUELTO** (julio 2026). Decisiones tomadas: **I10 → Opción B** (categoría
> explícita `Costo Presupuestado`), **I11 → solución "Mejor"** (fracción de
> ganancia efectiva), **I9 → implementado**. **I12 → sin acción** por decisión de
> negocio: el desfase temporal se entiende y no amerita cambiar el cálculo.
> La regla vigente está documentada en el docstring de `calculos.py`.

## Cómo se calcula hoy la ganancia (referencias)

- `calculos.py` — `ganancia_bruta_realizada` (~171-189):
  `ganancia = Σ cobrado_por_trabajo × margen/(100+margen)` — solo trabajos con presupuesto.
  El margen viene de `Presupuesto.margen_ganancia`; los costos (papel, tinta,
  troquel) están en `detalles_costos` del presupuesto y **ya están descontados**
  implícitamente por la fracción de margen.
- `routers/reportes.py` (~53-56): `ganancia_neta = ganancia_bruta − egresos`,
  donde egresos = suma de la tabla `gastos` del período (`calculos.py` ~192-198).
- `models.py` — `Gasto`: `responsable` (General/Facundo/Daniel), `trabajo_id` nullable, `categoria`.

---

## I10. Doble descuento de costos (el bache principal)

### Escenario de fallo
1. Presupuesto de 1000 tarjetas: costos $10.000 (papel+tinta) + margen 40% → precio $14.000.
2. El cliente paga todo → ganancia bruta realizada = 14.000 × 40/140 = **$4.000** ✔
   (los $10.000 de costo ya quedaron afuera).
3. Facundo carga como **Gasto** la compra de ese papel ($10.000, categoría Insumos,
   incluso asociado al trabajo).
4. Dashboard: ganancia neta = 4.000 − 10.000 = **−$6.000**. El costo se restó **dos veces**.

Y el caso inverso: si nadie carga los insumos como gasto, el número da bien "de
casualidad", sin regla que lo garantice.

Hoy no existe nada que distinga "gasto que ya estaba costeado en el presupuesto"
de "gasto general del taller" (alquiler, sueldos, librería).

### Opciones a decidir (presentar al usuario antes de implementar)
- **Opción A (recomendada por simplicidad)**: los gastos con `trabajo_id` apuntando
  a un trabajo **con presupuesto** NO restan de la ganancia neta (su costo ya está
  dentro del margen). Los gastos sin trabajo, o de trabajos manuales sin presupuesto,
  sí restan. Es un cambio solo en `calculos.py`/`reportes.py`, sin tocar modelo.
- **Opción B**: nueva categoría explícita "Costo presupuestado" excluida del cálculo;
  requiere disciplina de carga y cambio en el form de gastos.
- **Opción C**: abandonar el margen y calcular ganancia = cobrado − gastos reales
  por trabajo. Cambio grande, más preciso pero exige cargar TODOS los costos como
  gastos. No recomendada ahora.

Cualquiera sea la elegida: **documentarla** en `calculos.py` (docstring) y en la
doc del proyecto, y explicarla en el dashboard (tooltip/leyenda del KPI).

### ✅ Resuelto — se implementó la Opción B

Categoría nueva `Costo Presupuestado` (constante `CATEGORIA_COSTO_PRESUPUESTADO`
en `calculos.py`, única fuente de verdad; el frontend la replica en `app.js`).

- `total_gastos` no cambió: sigue siendo **todo** lo que salió de la caja y es lo
  que muestra el KPI de Egresos.
- `total_gastos_operativos` (nueva) es la que resta de la ganancia y excluye esos
  gastos. **Red de seguridad**: sólo los excluye si el trabajo efectivamente
  tiene presupuesto; si no, ese costo nunca estuvo dentro de ningún margen y
  resta normal, en vez de desaparecer e inflar la ganancia.
- `routers/gastos.py` rechaza con 400 un gasto de esa categoría sin trabajo
  asociado, validando el **estado resultante** también en el PUT parcial.
- El dashboard expone `costos_presupuestados` y lo explica con una leyenda bajo
  el KPI: *"No descuenta $X ya contemplados en presupuestos"*.

---

## I11. El margen usado queda congelado en el presupuesto original

### Escenario
`TrabajoUpdate` permite editar `precio_venta` (ej. descuento del 20% al cliente),
pero `ganancia_bruta_realizada` sigue aplicando el `margen_ganancia` del presupuesto
original sobre lo cobrado → la fracción de ganancia ya no es real.

### Solución propuesta (elegir una)
- Mínima: al editar `precio_venta` de un trabajo con presupuesto, aviso en la UI:
  "El margen de ganancia del dashboard seguirá siendo el del presupuesto original".
- Mejor: persistir en el trabajo la **fracción de ganancia efectiva** al convertir
  (costo_total del presupuesto congelado) y calcular
  `ganancia = cobrado × (precio_actual − costo_congelado)/precio_actual`.
  Requiere campo nuevo en `Trabajo` (+ migración) y ajuste en `calculos.py`.

### ✅ Resuelto — solución "Mejor", **sin campo nuevo ni migración**

El costo congelado ya existía: es `Presupuesto.costo_materiales` (NOT NULL), que
es exactamente lo que la conversión copia al trabajo (`presupuestos.py:234`).
Como `ganancia_bruta_realizada` ya recorre los presupuestos para sacar el margen,
sale del mismo objeto en la misma pasada.

Se usa el costo del **presupuesto** y no `Trabajo.costo_total_materiales` porque
un trabajo cargado a mano y vinculado a un presupuesto después
(`PUT /{presupuesto_id}/convertir/{trabajo_id}`) tiene ese campo en 0, lo que
daría una ganancia del 100%.

`fraccion_ganancia_efectiva` (nueva) devuelve `(precio − costo)/precio`, con dos
salvaguardas: sin costo congelado (o costo 0) cae al margen histórico, y con
precio 0 devuelve 0. Si el precio nunca se editó da **idéntico** al margen viejo
—`(precio − costo)/precio = m/(100+m)`—, así que sólo cambian los números de los
trabajos con precio editado, que es justamente el bug. Vender bajo costo da
ganancia negativa a propósito: es una pérdida real.

---

## I12. Desfase temporal caja vs. gasto (no es bug — comunicarlo)

La ganancia del período es proporcional a lo **cobrado** en el período; los gastos
van por su **fecha de gasto**. Un mes con compra grande de material y poca cobranza
muestra ganancia negativa "engañosa". Es inherente al modelo de caja elegido (razonable).

**Acción**: no cambiar el cálculo; agregar una leyenda/tooltip en el KPI de ganancia
neta del dashboard: "Ganancia por cobros del período − gastos del período. Un mes
con compras grandes puede dar negativo sin ser pérdida real."

### ⏸️ Sin acción (decisión de negocio, julio 2026)

El desfase se entiende y no se consideró un problema. No se agregó tooltip.
Queda documentado acá por si en algún momento confunde a alguien más.

---

## I9. Editar un gasto de un trabajo Entregado pierde la asociación en silencio

### Ubicación
`frontend/app.js` — `abrirDrawerGasto` (~1838) puebla el select `fg_trabajo_id`
solo con trabajos **activos**; `editarGasto` setea el value con `g.trabajo_id`,
pero si ese trabajo está Entregado/Cancelado la opción no existe → el select queda
en "Ninguno" → al guardar se manda `trabajo_id: null` y **el vínculo se borra sin aviso**.

### Solución
En `editarGasto`: si `g.trabajo_id` no está entre las opciones, inyectar una opción
extra `"(trabajo entregado) OP-XXXX — descripción"` con ese id y seleccionarla.
Así editar un gasto nunca rompe la asociación existente.

### ✅ Resuelto

`asegurarOpcionTrabajoGasto(trabajoId)` (nueva) inyecta la opción faltante como
`(entregado) #XXXXXX - 100x descripción`. `abrirDrawerGasto` guarda la lista de
trabajos en `trabajosParaGasto` para no pedirla dos veces. De paso `guardarGasto`
dejó de fallar en silencio: ahora muestra el `detail` del backend si el PUT/POST
no sale bien.

---

## Verificación
- [x] Regla de gastos elegida y confirmada por el usuario, documentada en `calculos.py` y docs.
- [x] Caso de prueba del doble descuento (ejemplo de arriba) da $4.000 de ganancia neta, no −$6.000.
- [x] Gasto general (sin trabajo) sigue restando normalmente.
- [x] Editar gasto de trabajo Entregado conserva el `trabajo_id`.
- [x] Leyenda del KPI de ganancia visible en el dashboard (sólo cuando hay costos presupuestados).
- [x] Precio editado a $11.200 sobre costo $10.000 da $1.200 de ganancia (antes $3.200).
- [x] Un trabajo con precio sin editar da el mismo número que antes del cambio (no regresión).
