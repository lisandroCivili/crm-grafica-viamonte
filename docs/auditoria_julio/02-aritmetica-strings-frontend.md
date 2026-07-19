# Prioridad 2 — Aritmética sobre montos-string en el frontend (fixes de una línea)

> Auditoría julio 2026. Hallazgos **C2** y **C3** (Críticos).
> Motivo de la prioridad: arreglos triviales (`Number(...)`) con impacto alto e inmediato.

## Contexto técnico (raíz común de ambos bugs)

**Pydantic v2 serializa `Decimal` como string JSON** (verificado empíricamente con
las versiones instaladas: pydantic 2.12.4 / fastapi 0.135.3 → `{"monto": "1500.00"}`).
Todos los campos `Money`/`Cantidad` (`money.py`) llegan al JS como **strings**:
`monto`, `precio_venta`, `cantidad`, `stock_minimo`, `costo_unitario`, etc.

En JS: `0 + "1500.00"` concatena ("01500.00") y `"9.000" <= "10.000"` compara
**lexicográficamente**. La mayor parte de `app.js` ya usa `Number(...)` correctamente;
estos son los puntos que quedaron crudos.

---

## C2. Suma de pagos por concatenación en la ficha del cliente

### Ubicación
`frontend/app.js` — `abrirFicha`, ~líneas 218-225:

```js
const pagosTrabajo = movimientos
    .filter(m => m.trabajo_id === t.id && m.tipo === 'Pago')
    .reduce((suma, m) => suma + m.monto, 0);   // ← concatena strings
```

### Escenario de fallo
- Con **1 pago**: `0 + "1500.00"` = `"01500.00"`; la resta posterior coacciona a número y zafa de casualidad.
- Con **2+ pagos**: `"01500.00" + "200.00"` = `"01500.00200.00"` → operaciones posteriores dan `NaN` → `fmtMoney(NaN)` devuelve `0,00`.
- Resultado visible: un trabajo con dos pagos parciales muestra **"Debe: $0,00 (Abonó: $0,00)"** en el acordeón de la ficha del cliente. Información financiera directamente errónea.

### Solución
```js
.reduce((suma, m) => suma + Number(m.monto), 0);
```

### Mejora recomendada en la misma pasada
Definir un helper único arriba de `app.js` y usarlo en todos los puntos que
suman/comparan montos de la API:

```js
const num = (v) => Number(v) || 0;
```

Y hacer una pasada con grep por `reduce(`, `+ m.monto`, `+ t.precio`, `<=` sobre
campos de la API para cazar otros casos crudos.

---

## C3. Alerta de stock mínimo con comparación lexicográfica

### Ubicación
`frontend/app.js` — `cargarStock`, ~línea 2458:

```js
const enAlerta = s.cantidad <= s.stock_minimo;   // ← compara strings
```

`s.cantidad` y `s.stock_minimo` llegan como strings tipo `"9.000"` (formato Q3 de `money.py`).

### Escenario de fallo
- `"9.000" <= "10.000"` → **false** (el "9" es mayor que el "1" del "10"): con 9 pliegos y mínimo 10, **no alerta**.
- `"100.000" <= "20.000"` → **true**: con 100 pliegos y mínimo 20, **falsa alarma ¡COMPRAR!**.

El semáforo de stock es hoy esencialmente aleatorio según los primeros dígitos.

### Solución
```js
const enAlerta = Number(s.cantidad) <= Number(s.stock_minimo);
```

---

## Otros puntos menores del mismo origen (arreglar de paso, opcional)

- `abrirDrawerPago` muestra `(Total: $${t.precio_venta})` sin formato → usar `fmtMoney(Number(t.precio_venta))`.
- Verificar todo cálculo del dashboard local (`app.js` ~2614-2778) — la mayoría ya usa `Number(...)`, confirmar que no quede ninguno crudo.

## Verificación
- [ ] Ficha de cliente con trabajo que tiene 2+ pagos parciales → "Debe"/"Abonó" muestran los montos reales.
- [ ] Artículo con cantidad 9 / mínimo 10 → alerta encendida.
- [ ] Artículo con cantidad 100 / mínimo 20 → sin alerta.
- [ ] Grep por `reduce(` y comparaciones `<=`/`>=` sobre campos de la API: todos con `Number(...)`.
