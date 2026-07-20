# Prioridad 5 — Endurecimiento de Stock + hallazgos menores

> Auditoría julio 2026. Hallazgos **I6**, **I7**, **I8** (Stock, Importantes) y la
> lista completa de **Menores**. Pasada final de endurecimiento, sin urgencia.

> **RESUELTO el 20/07/2026.** I6, I7 e I8 implementados; menores 1-10, 14 y 15
> aplicados; 13 documentado; 11 postergado por decisión del usuario (ver el
> ítem para el estado actual). Requiere correr `migracion_devolucion_papel.py`
> con el backend apagado.

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

**Resuelto 20/07/2026.** Dos helpers nuevos en `routers/trabajos.py`:
`_buscar_papel` (existencia + unidad) y `_validar_pliegos` (entero > 0). Se
aplican en `crear_trabajo`, en `actualizar_trabajo` (que **no validaba nada** del
papel) y, sólo la unidad, en `_descontar_papel` como red de seguridad. El entero
se valida únicamente sobre lo que entra por la API: los trabajos históricos con
cantidades fraccionarias siguen descontando sin romperse. Frontend con el filtro
y `step="1" min="1"` en ambos inputs.

### I7. El alta de un artículo nuevo no registra historial de stock

**Referencia**: `routers/stock.py` — `_procesar_item_compra` (~76-88): el
`HistorialStock` solo se crea en la rama de recompra; el stock inicial de un
artículo nuevo nace sin asiento. Ídem el endpoint legacy `POST /api/stock/`.
Contradice la regla del CLAUDE.md: "nunca modificar cantidades sin registrar motivo".

**Fix**: crear asiento `"Alta inicial: +N (compra)"` en la rama de artículo nuevo
de `_procesar_item_compra`, y `"Alta inicial: +N"` en el POST legacy.

**Resuelto 20/07/2026.** `_procesar_item_compra` se reordenó: las dos ramas
(alta/recompra) sólo cargan atributos, y el asiento se crea **al final**, con el
artículo ya completo. En el alta hace falta un `db.flush()` previo porque el `id`
lo resuelve SQLAlchemy recién al insertar (sin eso el FK del historial queda en
NULL) — y por eso el orden importa: si se flushea antes de cargar
`ultima_actualizacion`, que es NOT NULL, el INSERT falla.
Motivos: `"Alta inicial. Compra: +50.000 Pliegos"`.
Ídem el POST legacy. De paso, en el mismo archivo: guardia contra
`DivisionByZero` en `costo_total / cantidad` (`_calcular_pliegos` devuelve 0 si
el peso no llega a medio pliego) y `articulo.unidad = unidad` en la recompra, que
se calculaba y no se asignaba nunca.

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

**Resuelto 20/07/2026.** Columna `Trabajo.papel_devuelto` (booleano, espejo de
`orden_impresa`) + `migracion_devolucion_papel.py`. Se eligió el flag y no
buscar el asiento porque `HistorialStock` no tiene `trabajo_id`: la alternativa
era parsear el texto del `motivo`. Helper `_devolver_papel` en
`routers/trabajos.py`, disparado por el query param `devolver_papel` del PUT
(mismo criterio que `forzar` en imprimir-orden: es una decisión del operador en
el momento, no un dato del trabajo). El reingreso entra en la misma transacción
que el cambio de estado. Expuesto en `TrabajoResponse` para que la UI no lo
vuelva a ofrecer.

**Hallazgo de fondo**: la UI **no permitía cancelar un trabajo desde ninguna
pantalla** — el único `"Cancelado"` que se escribía era el automático de
`convertirATrabajo`. Por eso dos mensajes de la propia app eran inaplicables
(`eliminarTrabajo` recomendaba "usá Cancelado"; el aviso de recuperación de la
conversión decía "cancelalo a mano desde el Kanban"). Se agregó el botón
**✖ Cancelar** en la tarjeta del Kanban, con la pregunta por la devolución, más
un check **"Mostrar trabajos cancelados"** que los muestra atenuados con botón
**↩️ Reactivar**: sin eso, cancelar era un camino de una sola dirección.

**Limitación conocida**: un trabajo reactivado conserva `papel_devuelto = True` y
`orden_impresa = True`, así que reimprimir la orden **no vuelve a descontar** el
papel. Está anotado en el docstring de `_devolver_papel`; corregirlo exige
repensar el ciclo imprimir/cancelar/reimprimir completo.

### Menor relacionado: costo de compra por Kg
`armarItemCompraStock` solo manda `costo_total` si > 0 → si se deja en 0, el
`costo_unitario` del artículo queda desactualizado; en recompras el costo se pisa
con el de la última compra (sin promedio ponderado). Decisión defendible —
**documentarla** y, opcionalmente, avisar en la UI cuando una compra se carga sin costo.

**Decisión documentada (20/07/2026)**: el `costo_unitario` de un artículo es
**costo de reposición**, no promedio ponderado. Cada compra lo pisa con el precio
de la última. Es lo correcto para cotizar (un presupuesto se arma con lo que
cuesta reponer el papel hoy, no con lo que costó hace seis meses) y evita
arrastrar un promedio que en contexto inflacionario subestima el costo real.
Consecuencia asumida: el valor contable del stock existente queda sobrestimado
después de un aumento. Si en algún momento se necesita costeo histórico real,
hay que guardar el costo por lote en `HistorialStock`, que hoy no lo registra.

---

## Menores (lista completa)

1. **Login duplicado**: `/api/login` en `main.py` (~82-93, campo `contrasenia`) es
   código muerto — el frontend usa `/api/auth/login` (campo `password`). Eliminar el
   de `main.py` (verificar antes con grep que nada lo llame). Credenciales
   hardcodeadas admin/viamonte2026 en ambos: aceptable para uso local, dejar
   anotado como limitación conocida.
   **Resuelto 20/07/2026**: borrado el endpoint, `class LoginRequest` y los
   imports que quedaron sin uso (`status`, `BaseModel`). Las credenciales de
   `auth.py` quedan como limitación conocida.
2. **`routers/respaldo.py` no está montado** en `main.py` (archivo muerto). Decidir:
   montarlo o borrarlo. Nota: `/api/backup` en main.py funciona y no requiere auth.
   **Resuelto 20/07/2026**: borrado. El archivo estaba entero comentado y
   `/api/backup` ya cumple la función.
3. **`cargarDashboard` definida dos veces** (`app.js` ~1214 y ~2610). La vieja
   referencia `chartComparativo` (no existe en el HTML) y quedó pisada por la
   segunda. Borrar la vieja. *(Confirmado en la verificación del 18/07/2026:
   la vieja tiene datos hardcodeados "Marzo/Abril/Mayo/Junio" y es código
   muerto — la declaración async posterior la pisa.)*
   **Resuelto 20/07/2026**: borrada.
4. **Drawer legacy `#drawer-presupuesto`** (`index.html` ~605-700): sus inputs
   llaman a `calcularTotalPresupuesto()` que **no existe** en app.js →
   `ReferenceError` si alguien lo reactiva. Sin opener actual. Borrar el bloque.
   También borrar el `login-screen` comentado.
   **Resuelto 20/07/2026**: borrados el drawer (121 líneas), el `login-screen`
   comentado y las reglas `#login-screen` / `.login-box` de `style.css`, que
   también estaban muertas (el login activo usa `#login-overlay` con estilos
   inline). `.hidden` se conservó: la usa el modal de presupuesto.
5. **Gráfico "Flujo de Caja Anual" con gastos filtrados** (`app.js` ~2774):
   `dibujarGraficoFlujo` recibe `gastosFiltrados` (filtro del selector de período)
   para un gráfico **anual** → con "Este mes" muestra gastos de un mes contra
   ingresos de todo el año. Pasarle los gastos sin filtrar (o filtrar por año).
   **Resuelto 20/07/2026**: se le pasa `gastos` sin filtrar; la función ya filtra
   por año internamente. El `new Date(m.fecha)` sin `'T00:00:00'` **no** era un
   bug: `m.fecha` trae hora, y un ISO con hora y sin zona JS lo parsea como
   local (los de gastos/cheques son sólo fecha, por eso ahí sí lleva el sufijo).
   Queda comentado en el código para que no se "arregle" por error.
6. **Fallback del dashboard**: si `GET /api/reportes/dashboard` falla,
   `ingresosReales = 0` sin cartel (el comentario dice "caemos a lo local" pero no
   hay fallback local para ingresos). Mostrar aviso de error en vez de KPIs en $0.
   *Agregado 18/07/2026 (fix prioridad 1)*: morosos y "plata en la calle" ahora
   vienen del backend; el loop local de `app.js` quedó solo como fallback y
   **sigue ignorando cheques** — si el backend falla, muestra deuda inflada sin
   avisar. Al resolver este ítem, preferir el aviso de error también para
   morosos en vez de mantener ese cálculo local duplicado.
   **Resuelto 20/07/2026**: si `kpis` viene `null`, los KPIs financieros muestran
   `—` y aparece la franja `#dash-error`. Se eliminó el cálculo local duplicado
   de morosos / plata en la calle (ignoraba cheques) junto con la variable
   `totalIngresos`, que nunca se usaba, y el `pagosPorTrabajo` que la alimentaba.
   `plataEstancada` y los KPIs de cheques siguen calculándose local: no dependen
   de cobranzas.
7. **`innerHTML` sin escapar** en todo el frontend: una descripción con apóstrofo
   rompe los `onclick` inline (ej. `abrirModalEditarTrabajo('${t.descripcion_producto}')`,
   `app.js` ~241); con `<` se rompe la tabla. Fix incremental: helper `esc()` para
   texto interpolado y pasar ids (no textos) a los onclick, leyendo el objeto de
   un Map local en vez de serializar strings en el atributo.
   **Resuelto 20/07/2026 (parcial, por decisión)**: helper `esc()` + `detalleError()`
   creados junto a `fmtMoney`. Aplicados en los puntos que rompían de verdad:
   `<option>` de clientes/papel/trabajos, tarjetas del Kanban, acordeón y tabla
   de movimientos de la ficha, lista de morosos y alertas de cheques.
   `abrirModalEditarTrabajo` pasó a recibir **sólo el id** (ya traía el trabajo
   del backend, los otros tres parámetros eran redundantes). Se agregó el Map
   `trabajosPorId` que usan los botones nuevos del Kanban. **No** es un barrido
   completo: quedan puntos de interpolación en PDFs y vistas menos expuestas.
8. **`fetch` sin `resp.ok`** en `guardarTrabajo`, `guardarCliente`, `guardarGasto`
   (este último silencia el error): ante un 422 el drawer queda abierto sin mensaje.
   Agregar manejo de error con Swal mostrando el `detail`.
   **Resuelto 20/07/2026**: `guardarCliente` y `guardarTrabajo` siguen el patrón de
   `guardarGasto` (que ya estaba bien). En `guardarTrabajo` el chequeo además
   evita el `TypeError` de `nuevoTrabajo.id.substring()` sobre un body de error.
   El helper `detalleError()` cubre el caso del 422, donde `detail` es un array
   de objetos y no un string.
9. **`Movimiento.fecha` en UTC naive** (`datetime.utcnow`): un pago cargado a las
   22:00 de Argentina queda fechado al día siguiente → cerca de fin de mes cae en
   el período equivocado del dashboard. Fix: usar hora local o fecha local al
   registrar (consistente con gastos/cheques que usan `date`). Ojo: no tocar filas históricas.
   **Resuelto 20/07/2026**: helper `models.ahora_local()` usado por
   `Movimiento.fecha` y `Nota.fecha_creacion` (que tenía el mismo problema).
   Sin migración: las filas históricas no se tocan. `HistorialStock` e
   `HistorialCheque` siguen en UTC aware (son cronológicos, no contables);
   unificarlos es una pasada aparte, anotado en el docstring del helper.
10. **`lbl-pres-id` muestra número aleatorio** (`app.js` ~1254: `Nº 0001-` + random)
    que nunca coincide con el `numero_secuencia` real del backend. Mostrar
    "(se asigna al guardar)" o el número real post-guardado.
    **Resuelto 20/07/2026**: muestra "Nº (se asigna al guardar)" al crear y al
    duplicar. Al editar sigue mostrando el `numero_secuencia` real.
11. **Movimientos y gastos con DELETE duro**: contradice "no eliminar movimientos
    históricos" del CLAUDE.md. Propuesta: soft-delete (campo `anulado` + motivo) o
    contraasiento tipo 'Ajuste'. Requiere decisión del usuario (cambia el modelo).
    **POSTERGADO por decisión del usuario (20/07/2026)**: es un cambio de modelo
    con impacto en reportes, dashboard y saldos; merece su propia pasada y no
    mezclarse con el endurecimiento de stock. **Sigue pendiente.**
12. ~~**`crear_trabajo` devuelve 500** (no 404/400) si `cliente_id`/`papel_id` no
    existen: la FK lo bloquea pero el error es crudo. Validar existencia antes del
    commit y devolver 404 con mensaje claro.~~ **Resuelto 18/07/2026** junto con
    el fix de prioridad 1: `crear_trabajo` valida ambos y devuelve 404 con
    mensaje claro (verificado).
13. **Numeración `OP-`/`0001-` ordenada como string**: correcta hasta 999.999;
    solo documentar (uso monousuario, sin riesgo real hoy).
    **Documentado 20/07/2026**: sin acción. El orden lexicográfico de
    `_generar_numero_orden` es correcto hasta 999.999 y el uso es monousuario.
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
    **Resuelto 20/07/2026**: agregada a `TrabajoBase` (entra por `TrabajoCreate`) y
    a `TrabajoUpdate`; queda expuesta en `TrabajoResponse` por herencia. El drawer
    de alta ya la mandaba y ahora se persiste; el acordeón de la ficha del cliente
    ya la renderizaba y ahora muestra contenido real. Los trabajos convertidos
    antes del 18/07/2026 siguen con NULL.
15. **Comentario obsoleto en `app.js`** (~línea 1550): `// REEMPLAZAR
    convertirATrabajo en app.js` quedó de una edición vieja sobre la función ya
    reemplazada. Borrarlo en la próxima pasada de limpieza (va con los menores
    3 y 4).
    **Resuelto 20/07/2026**: borrados los 10 comentarios de este tipo que había en
    `app.js` (`// REEMPLAZAR ...`, `// Reemplazá ...`, `// Abajo, donde ...`) más
    el `// <-- AGREGAR ESTO` de `routers/trabajos.py` y el `// <--- AGREGAR ESTO`
    de `models.py`.

---

## Seguridad (anotado, sin acción inmediata — app de uso local)

- Credenciales hardcodeadas en el código fuente (auth.py; el duplicado de main.py
  se eliminó el 20/07/2026 con el menor 1, pero el de auth.py sigue).
- Sesión en `localStorage` sin token: toda la API queda abierta sin autenticación real.
- CORS incluye origen `"null"`.
- `/api/backup` descarga la base de datos completa sin auth.

Si algún día la app se expone fuera de la red local, este bloque pasa a ser
**crítico** y hay que resolverlo antes (tokens de sesión, auth en endpoints, CORS estricto).

---

## Verificación

**Antes de nada**: correr `python migracion_devolucion_papel.py` con el backend
apagado (deja backup fechado, es idempotente).

Verificado por API el 20/07/2026 (24 checks automatizados sobre base temporal):

- [x] Selector de papel solo muestra artículos en Pliegos; backend rechaza papel con otra unidad.
      También rechaza pliegos fraccionarios y ≤ 0, en POST y en PUT.
- [x] Artículo nuevo por compra nace con asiento de historial, con `articulo_id` no nulo.
      Ídem el `POST /api/stock/` legacy.
- [x] Cancelar trabajo con orden impresa ofrece devolución y genera asiento (una sola vez):
      cancelar → reactivar → cancelar de nuevo **no** duplica el reingreso.
- [x] `notas_iniciales` se guarda y se devuelve en el alta directa de trabajo.
- [x] Menores 1-10, 14 y 15 aplicados; 13 documentado; 11 postergado por decisión
      (12 ya resuelto el 18/07/2026).
- [x] Nada de lo eliminado rompe otra pantalla: grep previo de `api/login`,
      `LoginRequest`, `respaldo`, `chartComparativo`, `calcularTotalPresupuesto`,
      `drawer-presupuesto`, `login-screen`, `login-box`, `abrirModalEditarTrabajo`.
      `node --check frontend/app.js` limpio; `import main` sin errores.

Pendiente de prueba manual en el navegador (no cubierto por los checks de API):

- [ ] Kanban: botón ✖ Cancelar, check "Mostrar trabajos cancelados" y ↩️ Reactivar.
- [ ] Dashboard con el backend caído: KPIs en `—` y franja de error, nunca `$ 0,00`.
- [ ] Un cliente `O'Brien <test>` y una descripción con apóstrofo renderizan bien
      y los botones del Kanban y de la ficha siguen funcionando.
- [ ] Forzar un 422 en alta de cliente y de trabajo: aparece el Swal con el detalle
      y el drawer no se cierra ni se resetea.
