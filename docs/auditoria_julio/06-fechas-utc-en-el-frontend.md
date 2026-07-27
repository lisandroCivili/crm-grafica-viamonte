# Prioridad 6 — El frontend fecha en UTC lo que el backend ya decidió fechar en local

> Detectado el 27/07/2026, al construir el módulo de Asistencia.
> Gravedad: **Importante**. Corrompe la fecha de gastos, cheques, pagos,
> presupuestos y trabajos cargados después de las 21:00.
> Fixes de una línea, pero repartidos en 5 archivos.
>
> **Resuelto el 27/07/2026.** Se corrigieron los 7 puntos de fecha (incluida la
> B3, cosmética) y se hizo el barrido completo de `error.detail`, que al
> implementarlo resultaron ser **19 y no 3** (ver la corrección al final).

## Contexto técnico

`new Date().toISOString()` devuelve **siempre UTC**, no la hora local. En
Argentina (`America/Buenos_Aires`, UTC-3 fijo, sin horario de verano desde 2009)
eso significa que **desde las 21:00 hora local, el UTC ya es el día siguiente**.

Reproducido en este equipo con Node:

```
Zona del sistema: America/Buenos_Aires — offset UTC-3

Hora local del taller   toISOString() da   Debería ser
2026-07-27 20:59        2026-07-27         2026-07-27    ok
2026-07-27 21:00        2026-07-28         2026-07-27    ← un día adelante
2026-07-27 23:30        2026-07-28         2026-07-27    ← un día adelante
```

La ventana de fallo es de **21:00 a 23:59 todos los días**: 3 horas de cada 24,
un 12,5% de la jornada. En un taller que cierra tarde o donde se carga la
administración al final del día, no es un caso de borde.

### Lo que hace esto un problema de consistencia, no sólo un bug

**El backend ya resolvió este mismo problema, a conciencia y por escrito.**
`models.py:22-33` define `ahora_local()` con este comentario:

```python
def ahora_local():
    """Hora local del taller para los registros que se agrupan por día.

    El dashboard agrupa por fecha local: un pago cargado a las 22:00 fechado en
    UTC caía al día siguiente y, cerca de fin de mes, en el período equivocado.
    Consistente con gastos y cheques, que ya usan date.today().
    """
    return datetime.now()
```

O sea: el bug ya fue diagnosticado y corregido **del lado del servidor**. Pero
esos `default=ahora_local` sólo se aplican cuando el cliente **no manda** el
campo. En los 7 puntos de abajo el frontend manda la fecha explícitamente, y
pisa el default correcto con un valor en UTC. El arreglo del backend queda
anulado justo en los casos que más importan.

---

## Los 7 puntos afectados

Se dividen en dos grupos según si el operador puede darse cuenta o no.

### Grupo A — Invisibles: el usuario no ve el campo y no lo puede corregir

Son los graves. La fecha se arma y se manda sin que aparezca en ningún
formulario.

| # | Ubicación | Campo | Qué queda mal fechado |
|---|-----------|-------|-----------------------|
| A1 | `frontend/js/trabajos.js:168` | `fecha_creacion` | El trabajo entra con fecha de mañana |
| A2 | `frontend/js/presupuestos.js:428` | `fecha_creacion` | El presupuesto entra con fecha de mañana |
| A3 | `frontend/js/pagos.js:93` | `fecha_emision` | El cheque recibido en un pago |
| A4 | `frontend/js/cheques.js:374` | `fecha` del Gasto | El gasto autogenerado al endosar un cheque |

```js
// trabajos.js:168 — dentro del payload de alta, sin input asociado
fecha_creacion: new Date().toISOString().split('T')[0],
```

### Grupo B — Visibles: el campo se precarga en un formulario

El operador *podría* notarlo, pero el input ya viene relleno y nadie revisa una
fecha que el sistema propuso.

| # | Ubicación | Campo |
|---|-----------|-------|
| B1 | `frontend/js/gastos.js:27` | `fg_fecha`, fecha del gasto |
| B2 | `frontend/js/cheques.js:27` | `fch_emision`, fecha de emisión |
| B3 | `frontend/js/presupuestos.js:811` | Sólo el nombre del PDF descargado — **cosmético, no corregir con urgencia** |

---

## Escenario de fallo concreto

El peor caso es el cierre de mes, porque el error se acumula en silencio:

1. Es **31 de julio**, 21:30. Se cargan los últimos gastos del mes.
2. `gastos.js:27` precarga `fg_fecha` con `2026-08-01`.
3. El gasto se guarda con fecha de agosto.
4. `routers/reportes.py` arma el informe mensual filtrando por rango de fechas.
   Ese gasto **no aparece en julio** y **sí aparece en agosto**.
5. La ganancia de julio sale **inflada** (falta un egreso) y la de agosto,
   **hundida** (le sobra uno que no le corresponde).

Nadie se entera, porque el número que se muestra es internamente coherente. Sólo
aparece si alguien cruza el informe contra los comprobantes en papel.

El mismo mecanismo afecta a los trabajos: un trabajo cargado el 31 a la noche
figura como del mes siguiente en las estadísticas de producción.

---

## Solución propuesta

Un helper único en `frontend/js/core.js`, junto a `fmtMoney` y `esc`, y
reemplazar las 6 ocurrencias del Grupo A y B (la B3 es opcional).

```js
// Hoy en formato YYYY-MM-DD, calculado en hora LOCAL.
// No se usa toISOString(), que devuelve UTC: desde las 21:00 en Argentina el
// UTC ya es el día siguiente y todo lo cargado a esa hora quedaba fechado
// mañana. Es el equivalente en el frontend de ahora_local() (models.py).
function fechaHoyLocal() {
    const ahora = new Date();
    const mes = String(ahora.getMonth() + 1).padStart(2, '0');
    const dia = String(ahora.getDate()).padStart(2, '0');
    return `${ahora.getFullYear()}-${mes}-${dia}`;
}
```

**Esta función ya existe y está en uso**, en `frontend/js/asistencia.js:9`. La
corrección consiste en moverla a `core.js` y borrar la copia de `asistencia.js`,
que pasa a usar la compartida. No hay que escribir nada nuevo: sólo relocalizarla
y reemplazar los 6 `new Date().toISOString().split('T')[0]`.

### Por qué no se corrigió en el momento de detectarlo

Se detectó mientras se construía Asistencia, que es código nuevo. Tocar los 5
módulos existentes en esa misma pasada habría mezclado una feature con un
arreglo de fondo en presupuestos, trabajos, cheques y pagos — cuatro áreas que no
tenían por qué moverse. Se dejó documentado para resolverlo en su propia sesión,
con su propia verificación.

---

## Hallazgo secundario del mismo repaso: `error.detail` crudo

Distinto origen, mismo tipo de arreglo. El `detail` de FastAPI es un **string** en
los `HTTPException` propios, pero un **array de objetos** en los 422 de validación
de Pydantic. Ante un 422, mostrarlo crudo da el cartel inútil `[object Object]` en
lugar de decir qué campo está mal.

`core.js:detalleError(error, porDefecto)` ya resuelve exactamente esto y maneja
los dos formatos.

### Corrección: eran 19, no 3

Este documento listaba originalmente 3 ubicaciones (`gastos.js:237`,
`trabajos.js:606` y `:646`). El relevamiento se había hecho buscando
`error.detail`, y se le escaparon todas las que usan la variable `err`. Al
implementar el arreglo aparecieron **19**, en tres formas:

**A. Dentro de un `Swal.fire`** (11) — `gastos.js`, `trabajos.js` ×3,
`presupuestos.js` ×3, `clientes.js` ×2, `pagos.js`, `stock.js`:

```js
// antes
Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
// después
Swal.fire('No se pudo guardar', detalleError(err, 'Error desconocido'), 'error');
```

**B. Dentro de un `throw new Error(...)`** (6) — `trabajos.js` ×4,
`presupuestos.js` ×2. Mismo criterio que ya usaba `clientes.js:145`:

```js
throw new Error(detalleError(err, "No se pudo guardar el cambio."));
```

**C. Tres casos particulares:**

- `trabajos.js:394` hacía `err.detail?.[0]?.msg || err.detail || "..."`, una
  versión a mano e incompleta del helper. Ahora un 422 muestra `campo: mensaje` y
  no sólo el mensaje suelto.
- `trabajos.js:455` concatena el detalle con `' ¿Emitir la orden igual?...'`: se
  le pasa `''` como default para no colar el texto genérico dentro de la frase.
- `cheques.js:mostrarErrorCheque` reimplementaba el mismo fallback; ahora delega
  en `detalleError` conservando el `try/catch` para respuestas sin cuerpo JSON.

La regla que queda: **ningún `.detail` se lee directo en `frontend/js/`**; el único
que sobrevive es el de adentro de `detalleError` en `core.js`.

---

## Hallazgo relacionado, fuera de alcance

`HistorialStock.fecha` y `HistorialCheque.fecha` (`models.py:234` y `:265`)
guardan `datetime.now(timezone.utc)`, y `stock.js:433` los muestra con
`toLocaleString('es-AR')` sin convertir: **el historial de stock exhibe la hora 3
horas adelantada**. Es un problema de visualización y no contamina ningún cálculo.
El docstring de `ahora_local()` ya lo declara como migración aparte, así que no se
tocó acá. Candidato a punto 7 de esta auditoría.

---

## Verificación

### Hecho al implementar (27/07/2026)

- [x] `fechaHoyLocal()` vive en `core.js` y `asistencia.js` usa la compartida (sin duplicado).
- [x] `grep toISOString frontend/js/` da cero (se corrigió también la B3, el nombre del PDF).
- [x] `grep "\.detail" frontend/js/` sólo devuelve el de adentro de `detalleError` en `core.js`.
- [x] `node --check` sobre los 9 archivos tocados.
- [x] `pytest` sigue en verde (el cambio no toca el backend; es una red de seguridad).

### Pendiente de prueba manual en el navegador

Para probarlo sin esperar a las 21:00, la forma liviana es **Chrome DevTools →
⋮ → More tools → Sensors → Location → Manage**, crear una ubicación con Timezone
ID `Asia/Tokyo` (UTC+9) y seleccionarla: mueve el reloj de JS sin tocar la
máquina. Fallback: cambiar la zona horaria de Windows a una con offset positivo.

- [ ] Dar de alta un **gasto**: se guarda con la fecha de hoy, no la de mañana.
- [ ] Dar de alta un **trabajo**: `fecha_creacion` es la de hoy.
- [ ] Dar de alta un **presupuesto**: `fecha_creacion` es la de hoy.
- [ ] Registrar un **pago con cheque**: `fecha_emision` es la de hoy.
- [ ] **Endosar un cheque**: el gasto generado queda con fecha de hoy.
- [ ] **Asistencia** sigue precargando bien la fecha (confirma que el helper movido no se rompió).
- [ ] Un gasto cargado el último día del mes a la noche aparece en el informe de **ese** mes.
- [ ] Forzar un 422 y ver que el cartel dice el campo, no `[object Object]`.
