# Prioridad 5 — Endurecimiento de Stock + hallazgos menores

> Auditoría julio 2026. Hallazgos **I6**, **I7**, **I8** (Stock, Importantes) y la
> lista completa de **Menores**. Pasada final de endurecimiento, sin urgencia.

---

## Stock

### I6. El descuento de pliegos no valida la unidad del artículo

**Referencias**: `routers/trabajos.py` — `_descontar_papel` (~62-100);
`frontend/app.js` — `cargarSelectoresPapel` (~923-935).

La fórmula de conversión Kg→pliegos está bien
(`peso_pliego_kg = (largo×ancho×gramaje)/10.000.000`, redondeo a pliego entero) y
los tipos coinciden (`Cantidad`/Q3 en ambos lados). El problema es el borde:

- El selector de papel lista **todo** el stock (tinta en litros, resmas, paquetes).
- `_descontar_papel` descuenta `cantidad_pliegos` de lo que sea que esté vinculado,
  sin chequear `articulo.unidad == "Pliegos"` → se pueden restar "3 pliegos" de un
  bidón de 5 litros.
- Tampoco valida que `cantidad_pliegos` sea entero (el input acepta `step="0.001"`).

**Fix**:
1. Backend: en `_descontar_papel` (y al setear `papel_id` en crear/editar trabajo),
   validar `articulo.unidad == "Pliegos"` → 400 con mensaje claro; validar
   `cantidad_pliegos` entero positivo.
2. Frontend: `cargarSelectoresPapel` filtra por `unidad === 'Pliegos'`;
   input de cantidad con `step="1"`.

### I7. El alta de un artículo nuevo no registra historial de stock

**Referencia**: `routers/stock.py` — `_procesar_item_compra` (~76-88): el
`HistorialStock` solo se crea en la rama de recompra; el stock inicial de un
artículo nuevo nace sin asiento. Ídem el endpoint legacy `POST /api/stock/`.
Contradice la regla del CLAUDE.md: "nunca modificar cantidades sin registrar motivo".

**Fix**: crear asiento `"Alta inicial: +N (compra)"` en la rama de artículo nuevo
de `_procesar_item_compra`, y `"Alta inicial: +N"` en el POST legacy.

### I8. Cancelar un trabajo con orden impresa no devuelve los pliegos

**Referencias**: `routers/trabajos.py` — el descuento ocurre en `imprimir_orden`
(guard `orden_impresa`); el cambio de estado a Cancelado no lo compensa. Incluye
el flujo automático de "cancelar la versión anterior" al convertir un presupuesto
corregido (`app.js` ~1614-1621).

**Fix**: al pasar a `Cancelado` un trabajo con `orden_impresa == True` y `papel_id`:
preguntar en la UI "¿Devolver N pliegos al stock?"; si acepta, backend reingresa
la cantidad con asiento en `HistorialStock` ("Devolución por cancelación OP-XXXX").
Idempotente: registrar que la devolución ya se hizo (p.ej. flag o buscar el asiento)
para no devolver dos veces si el trabajo se cancela/reactiva.

### Menor relacionado: costo de compra por Kg
`armarItemCompraStock` solo manda `costo_total` si > 0 → si se deja en 0, el
`costo_unitario` del artículo queda desactualizado; en recompras el costo se pisa
con el de la última compra (sin promedio ponderado). Decisión defendible —
**documentarla** y, opcionalmente, avisar en la UI cuando una compra se carga sin costo.

---

## Menores (lista completa)

1. **Login duplicado**: `/api/login` en `main.py` (~82-93, campo `contrasenia`) es
   código muerto — el frontend usa `/api/auth/login` (campo `password`). Eliminar el
   de `main.py` (verificar antes con grep que nada lo llame). Credenciales
   hardcodeadas admin/viamonte2026 en ambos: aceptable para uso local, dejar
   anotado como limitación conocida.
2. **`routers/respaldo.py` no está montado** en `main.py` (archivo muerto). Decidir:
   montarlo o borrarlo. Nota: `/api/backup` en main.py funciona y no requiere auth.
3. **`cargarDashboard` definida dos veces** (`app.js` ~1214 y ~2610). La vieja
   referencia `chartComparativo` (no existe en el HTML) y quedó pisada por la
   segunda. Borrar la vieja. *(Confirmado en la verificación del 18/07/2026:
   la vieja tiene datos hardcodeados "Marzo/Abril/Mayo/Junio" y es código
   muerto — la declaración async posterior la pisa.)*
4. **Drawer legacy `#drawer-presupuesto`** (`index.html` ~605-700): sus inputs
   llaman a `calcularTotalPresupuesto()` que **no existe** en app.js →
   `ReferenceError` si alguien lo reactiva. Sin opener actual. Borrar el bloque.
   También borrar el `login-screen` comentado.
5. **Gráfico "Flujo de Caja Anual" con gastos filtrados** (`app.js` ~2774):
   `dibujarGraficoFlujo` recibe `gastosFiltrados` (filtro del selector de período)
   para un gráfico **anual** → con "Este mes" muestra gastos de un mes contra
   ingresos de todo el año. Pasarle los gastos sin filtrar (o filtrar por año).
6. **Fallback del dashboard**: si `GET /api/reportes/dashboard` falla,
   `ingresosReales = 0` sin cartel (el comentario dice "caemos a lo local" pero no
   hay fallback local para ingresos). Mostrar aviso de error en vez de KPIs en $0.
   *Agregado 18/07/2026 (fix prioridad 1)*: morosos y "plata en la calle" ahora
   vienen del backend; el loop local de `app.js` quedó solo como fallback y
   **sigue ignorando cheques** — si el backend falla, muestra deuda inflada sin
   avisar. Al resolver este ítem, preferir el aviso de error también para
   morosos en vez de mantener ese cálculo local duplicado.
7. **`innerHTML` sin escapar** en todo el frontend: una descripción con apóstrofo
   rompe los `onclick` inline (ej. `abrirModalEditarTrabajo('${t.descripcion_producto}')`,
   `app.js` ~241); con `<` se rompe la tabla. Fix incremental: helper `esc()` para
   texto interpolado y pasar ids (no textos) a los onclick, leyendo el objeto de
   un Map local en vez de serializar strings en el atributo.
8. **`fetch` sin `resp.ok`** en `guardarTrabajo`, `guardarCliente`, `guardarGasto`
   (este último silencia el error): ante un 422 el drawer queda abierto sin mensaje.
   Agregar manejo de error con Swal mostrando el `detail`.
9. **`Movimiento.fecha` en UTC naive** (`datetime.utcnow`): un pago cargado a las
   22:00 de Argentina queda fechado al día siguiente → cerca de fin de mes cae en
   el período equivocado del dashboard. Fix: usar hora local o fecha local al
   registrar (consistente con gastos/cheques que usan `date`). Ojo: no tocar filas históricas.
10. **`lbl-pres-id` muestra número aleatorio** (`app.js` ~1254: `Nº 0001-` + random)
    que nunca coincide con el `numero_secuencia` real del backend. Mostrar
    "(se asigna al guardar)" o el número real post-guardado.
11. **Movimientos y gastos con DELETE duro**: contradice "no eliminar movimientos
    históricos" del CLAUDE.md. Propuesta: soft-delete (campo `anulado` + motivo) o
    contraasiento tipo 'Ajuste'. Requiere decisión del usuario (cambia el modelo).
12. ~~**`crear_trabajo` devuelve 500** (no 404/400) si `cliente_id`/`papel_id` no
    existen: la FK lo bloquea pero el error es crudo. Validar existencia antes del
    commit y devolver 404 con mensaje claro.~~ **Resuelto 18/07/2026** junto con
    el fix de prioridad 1: `crear_trabajo` valida ambos y devuelve 404 con
    mensaje claro (verificado).
13. **Numeración `OP-`/`0001-` ordenada como string**: correcta hasta 999.999;
    solo documentar (uso monousuario, sin riesgo real hoy).
14. **`notas_iniciales` no existe en los schemas de Trabajo** (`schemas.py` —
    `TrabajoBase`/`TrabajoCreate`/`TrabajoResponse`): la columna está en el
    modelo, pero como el schema no la incluye, la conversión vieja la enviaba y
    Pydantic la descartaba en silencio — **nunca se guardó** hasta el fix de
    prioridad 1 (los trabajos convertidos antes del 18/07/2026 la tienen en
    NULL). El endpoint nuevo la persiste ("Viene del presupuesto 0001-XXXXXX"),
    pero `TrabajoResponse` no la expone, así que el frontend no puede mostrarla.
    Decidir: agregarla a `TrabajoResponse` (y opcionalmente a Create/Update para
    el alta manual) o dejarla como campo interno. Hallazgo lateral de la
    verificación del fix de prioridad 1.
15. **Comentario obsoleto en `app.js`** (~línea 1550): `// REEMPLAZAR
    convertirATrabajo en app.js` quedó de una edición vieja sobre la función ya
    reemplazada. Borrarlo en la próxima pasada de limpieza (va con los menores
    3 y 4).

---

## Seguridad (anotado, sin acción inmediata — app de uso local)

- Credenciales hardcodeadas en el código fuente (auth.py y main.py).
- Sesión en `localStorage` sin token: toda la API queda abierta sin autenticación real.
- CORS incluye origen `"null"`.
- `/api/backup` descarga la base de datos completa sin auth.

Si algún día la app se expone fuera de la red local, este bloque pasa a ser
**crítico** y hay que resolverlo antes (tokens de sesión, auth en endpoints, CORS estricto).

---

## Verificación
- [ ] Selector de papel solo muestra artículos en Pliegos; backend rechaza papel con otra unidad.
- [ ] Artículo nuevo por compra nace con asiento de historial.
- [ ] Cancelar trabajo con orden impresa ofrece devolución y genera asiento (una sola vez).
- [ ] Menores 1-8 y 15 aplicados; 9-11, 13 y 14 según decisión (12 ya resuelto el 18/07/2026).
- [ ] Nada de lo eliminado (login duplicado, drawer legacy, dashboard viejo) rompe otra pantalla (grep de referencias antes de borrar).
