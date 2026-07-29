# Manual de uso — CRM Gráfica Viamonte

Guía para el uso diario del sistema. Cada sección explica primero **cómo se
usa** (para cualquiera que cargue datos en el día a día) y, donde corresponde,
un recuadro **¿Por qué funciona así?** con la regla de negocio de fondo (útil
sobre todo para quien mira los números de caja y ganancia).

Al final hay una sección de **preguntas frecuentes** con los mensajes de error
más comunes y qué hacer ante cada uno.

---

## 1. Acceso al sistema

Al abrir el sistema aparece una pantalla de login. **Cada persona tiene su
propio usuario y su propia contraseña**: no se comparten. La sesión dura una
jornada de trabajo; al día siguiente hay que volver a entrar.

Una vez adentro, el menú lateral izquierdo tiene una sección por módulo. **No
todos ven lo mismo**: cada usuario tiene un puesto asignado y sólo le aparecen
las pestañas de su puesto.

| Puesto | Qué ve |
|---|---|
| **Administración** | Todo. |
| **Encargado de taller** | Trabajos, Clientes, Stock y Asistencia. No ve los precios de los trabajos ni el saldo de los clientes. |
| **Mostrador** | Trabajos, Clientes, Stock y Gastos. Tampoco ve precios ni saldos. |

Dar de alta un trabajo y borrar cosas (clientes, trabajos, gastos, artículos de
stock) queda siempre para Administración.

Al pie del menú hay dos acciones:

- **Descargar Respaldo** (sólo Administración): descarga un archivo con una
  copia completa de la base de datos a la fecha. Conviene bajarlo una vez por
  semana y guardarlo en otro lugar (pendrive, nube): es el único resguardo
  propio si algo se rompe del lado del servidor.
- **Cerrar Sesión**: vuelve a la pantalla de login.

> **¿Por qué cada uno tiene su usuario y no ve todo?**
> El sistema dejó de estar en una sola computadora: ahora se entra por
> internet, desde el taller o desde donde sea. Con varias personas usando lo
> mismo, dos cosas cambian. Una es que los precios y la cuenta corriente de los
> clientes son información del negocio y no hacen falta para producir. La otra
> es que, teniendo cada uno su usuario, **el sistema puede registrar quién hizo
> cada cosa** (ver la sección 11, Auditoría) — con un usuario compartido eso
> sería imposible.

> **Si alguien deja de trabajar en el taller**, se le da de baja el usuario y
> queda afuera en el acto, incluso si tenía la sesión abierta. Lo que hizo
> mientras trabajaba sigue registrado a su nombre.

---

## 2. Clientes

### Cómo se usa

- **Agregar Cliente**: nombre completo (obligatorio), empresa/local
  (opcional), DNI o CUIT (obligatorio) y teléfono (obligatorio). El DNI/CUIT
  no puede repetirse: si ya existe un cliente con ese número, el sistema
  avisa y no permite crear el duplicado.
- El campo **Aviso recompra (días)** es opcional: sirve para detectar
  clientes que compran con una frecuencia regular (por ejemplo, cada 45
  días) y no volvieron a pedir.
- Al hacer clic sobre un cliente en el listado se abre su **ficha**, con tres
  pestañas:
  - **Trabajos**: todos los trabajos de ese cliente.
  - **Movimientos**: pagos registrados y botón para descargar el detalle en
    PDF.
  - **Notas**: notas rápidas sobre el cliente (no atadas a un trabajo en
    particular, aunque también se pueden dejar notas dentro de un trabajo).
- En la parte superior de la ficha se ve el **Saldo de Cuenta Corriente**.

### Saldo en verde: plata a favor del cliente

Normalmente el saldo se muestra en rojo cuando el cliente debe plata. Si en
cambio aparece en **verde con una aclaración**, significa que el cliente tiene
**plata a favor** (pagó de más, o señó un trabajo que después se canceló). Esa
plata no se devuelve ni se pierde: queda disponible para aplicarse al próximo
trabajo (ver sección 4, "Aplicar saldo a favor").

> **¿Por qué funciona así?**
> El saldo de un cliente es siempre lo mismo en toda la aplicación (ficha,
> listado de clientes y dashboard de morosos): lo facturado por sus trabajos
> no cancelados, menos lo que pagó (efectivo/transferencia + cheques
> recibidos que no fueron rechazados). Si ese número da negativo, es porque
> pagó más de lo que debe — es plata real, no un error de carga.

### Eliminar un cliente

Solo se puede eliminar un cliente que **no tenga** trabajos, pagos,
presupuestos, notas ni cheques asociados. Si tiene cualquiera de esas cosas,
el sistema lo bloquea: primero hay que resolver esos vínculos (por ejemplo,
cancelar el trabajo en vez de querer borrar al cliente).

---

## 3. Presupuestos

### Cómo se usa

- **+ Nuevo Presupuesto** abre el formulario. Se elige el cliente (o se deja
  sin asignar, como borrador) y el **estado**: Borrador, Enviado, Aprobado o
  Rechazado.
- Un presupuesto puede tener **uno o varios productos** (ítems): por ejemplo,
  bolsas + cajas + papel antigrasa en el mismo comprobante. Cada ítem tiene
  su propia descripción, cantidad, precio unitario y, opcionalmente, el papel
  que consume y sus costos internos (para calcular la ganancia).
- El total del presupuesto es la suma de sus ítems.
- **Convertir a Trabajo**: transforma el presupuesto en trabajos reales del
  taller. Se crea **un trabajo por cada ítem** del presupuesto (si el
  presupuesto tiene 3 productos, se crean 3 trabajos, cada uno con su propio
  seguimiento en el tablero de Trabajos).
  - Requiere que el presupuesto tenga un **cliente asignado**.
  - Una vez convertido, el presupuesto queda bloqueado: **no se puede editar
    ni eliminar**.
  - Un presupuesto no se puede convertir dos veces.
- También se puede **asociar un presupuesto de un solo ítem a un trabajo ya
  existente** que no tenga presupuesto (por ejemplo, un trabajo cargado
  rápido a mano). Recién con esa asociación el trabajo empieza a aportar
  ganancia calculable al dashboard.
- El botón de PDF genera el presupuesto para entregarle al cliente.

> **¿Por qué funciona así?**
> Convertir un presupuesto en trabajo es una sola operación de una sola vez:
> si algo fallara a mitad de camino, no queda ni un trabajo huérfano ni un
> presupuesto marcado a medias. Por eso el sistema no permite convertir un
> presupuesto ya convertido, ni editar/borrar uno que ya generó trabajos —
> esos trabajos son la fuente de verdad a partir de ese momento.

---

## 4. Trabajos (Tablero de Producción)

El tablero (Kanban) tiene las columnas **Aprobado → En Diseño → En
Producción → Entregado**. Los trabajos **Cancelados** salen del tablero por
defecto (hay un check "Mostrar trabajos cancelados" para volver a verlos,
atenuados, con un botón para reactivarlos).

### Qué se ve en el tablero (y qué no)

La columna **Entregado** muestra sólo los trabajos entregados en los **últimos
15 días**. Pasado ese plazo la tarjeta sale sola del tablero: nada se borra ni
se modifica, simplemente deja de ocupar lugar en la pantalla de trabajo. Sin
ese corte, después de unos meses de uso la columna tendría cientos de tarjetas
viejas y el tablero dejaría de servir para ver lo que hay que hacer hoy.

Para encontrar un trabajo entregado hace tiempo (por ejemplo, para reimprimir
un remito), se entra a la **ficha del cliente**, que lista su historial
completo de trabajos sin límite de fecha.

- **Quitar del tablero** (botón 📦 en la tarjeta): saca una tarjeta antes de
  que se cumplan los 15 días, cuando ya se sabe que ese trabajo está cerrado y
  no se quiere seguir viéndolo. Sólo aparece en los trabajos **Entregados** o
  **Cancelados**: uno en curso no se puede sacar, porque el tablero es
  justamente donde se lo sigue.
- **Ver historial completo de entregados** (check arriba del tablero): trae
  todos los entregados, incluidos los viejos y los que se quitaron a mano.
  Aparecen atenuados y con un botón **📥 Volver al tablero** por si alguno se
  quitó por error.

### Cómo se usa

- **+ Nuevo Trabajo**: elegís el cliente, la descripción del producto, el
  precio de venta, y opcionalmente todos los datos de la boleta física
  (papel, medida, corte de pliego, tintas, troquelado, barniz, notas). Los
  datos de producción se pueden completar más adelante si todavía no se
  sabe.
- **Desde el celular**: el tablero se desliza de costado para pasar de una
  columna a otra, y cada tarjeta tiene un botón **↔️ Mover a...** para elegir la
  etapa de una lista. Es el reemplazo del arrastre, que con el dedo no funciona.
  Pide exactamente lo mismo que arrastrar: pasar a Diseño sigue pidiendo la
  seña, y pasar a Producción sigue pidiendo los datos de la boleta.
- **Pasar a "En Diseño"**: no es un simple arrastre en el tablero. El sistema
  pide usar el botón **Iniciar Diseño**, porque en ese paso hay que registrar
  lo que el cliente abonó como seña (puede ser $0, pero entonces hay que
  escribir el motivo: "sin seña porque..."). Si la seña es con cheque, se
  carga como cheque recibido; si no, como un pago normal.
- **Imprimir Orden de Producción**: genera el PDF de la boleta y, la primera
  vez que se imprime, **descuenta del stock el papel** asociado al trabajo.
  Reimprimir después no vuelve a descontar nada — es la misma orden.
  - Si no alcanza el papel en stock, el sistema avisa cuánto falta y ofrece
    la opción de **forzar** la impresión (para cuando el papel se compra en
    el momento). Forzar deja constancia en el historial de stock.
  - Debajo de "Corte de pliego" la boleta trae un **recuadro vacío** para
    dibujar a mano el esquema de corte, como en el talonario de papel.
- **Pasar a "En Producción"**: al arrastrar la tarjeta a esa columna se abre
  el panel **Datos de producción**, con los campos de la boleta física
  (papel, pliegos, medidas, corte, tintas, troquelado, barniz,
  observaciones). Viene precargado con lo que ya tenga el trabajo — los que
  salen de un presupuesto traen el papel pero no el resto, porque esos datos
  se deciden recién al bajar a máquina. Al confirmar con **Guardar y emitir
  orden** se guardan los datos, se imprime la orden y recién ahí el trabajo
  pasa a Producción. Si se cierra el panel sin guardar, la tarjeta no se
  mueve; si se cancela la impresión, los datos quedan guardados igual pero el
  trabajo se queda donde estaba (pasar a Producción exige la orden impresa).
- **Cancelar un trabajo** (botón ✖ en la tarjeta del Kanban): si la orden ya
  estaba impresa, pregunta si hay que **devolver los pliegos al stock**. Esa
  devolución solo pasa una vez, aunque el trabajo se cancele y reactive
  varias veces.
- **Editar un trabajo** siempre pide una **razón del cambio**, que queda
  registrada.
- Si la orden ya fue impresa, no se puede cambiar el papel ni la cantidad de
  pliegos (ya se descontaron del stock con esos valores).

### Aplicar saldo a favor

Si un cliente tiene plata a favor (ver sección 2) y se le crea un trabajo
nuevo, se puede usar **Aplicar saldo a favor** para cubrir ese trabajo con esa
plata existente, en vez de pedirle que pague de nuevo.

> **¿Por qué funciona así?**
> Esta acción **no crea un pago nuevo**: mueve (re-imputa) los pagos que ya
> existen a favor del cliente hacia este trabajo. Si creara un pago nuevo,
> esa plata se contaría dos veces (una como saldo a favor suelto y otra como
> pago del trabajo), inflando los ingresos. Si el saldo a favor es más grande
> que lo que hace falta cubrir, el sobrante queda como saldo a favor para el
> próximo trabajo; los cheques, al ser un documento físico, solo se pueden
> re-imputar enteros (no se dividen).

### Eliminar un trabajo

Solo se puede eliminar un trabajo que **no tenga** pagos, presupuesto
convertido, gastos ni cheques asociados. Si tiene cualquiera de esos vínculos,
hay que **cancelarlo** en vez de borrarlo (así queda el historial).

---

## 5. Movimientos (pagos de clientes)

Los pagos se registran desde la ficha del cliente, pestaña **Movimientos**,
con el botón **+ Registrar Pago**. Todo pago se asocia a un trabajo puntual
(así el sistema puede calcular cuánto ganó ese trabajo en particular).

Los métodos de pago disponibles son Efectivo, Transferencia y MercadoPago. Si
el cliente paga con **cheque**, ese pago **no se carga acá**: se carga desde
el módulo Cheques (ver sección 8) — el propio formulario de pago, al elegir
"Cheque" como método, pide los datos del cheque y lo deriva a ese módulo.

> **¿Por qué funciona así?**
> Un pago con cheque no es plata real todavía (puede rechazarse): recién
> cuenta como ingreso cuando el cheque se cobra. Si se cargara como un
> movimiento común, el sistema lo daría por cobrado en el momento, cosa que
> todavía no pasó.

Los movimientos son el historial de cuenta corriente de cada cliente: evitá
borrar un pago ya cargado salvo que sea un error de tipeo recién hecho.
Cuando la corrección corresponde a un pago de otro día o ya usado en algún
cálculo, es más prudente avisar para corregirlo con un ajuste antes que
borrarlo directamente.

---

## 6. Gastos

### Cómo se usa

- **+ Registrar Gasto**: categoría, responsable (General, Facundo o Daniel),
  concepto, trabajo asociado (opcional), método de pago, tipo de comprobante,
  monto y fecha.
- Las categorías disponibles son: Insumos y Materiales, Servicios (luz,
  internet, alquiler), Sueldos/Honorarios, Mantenimiento, **Costo
  Presupuestado** y Otros.

### La categoría "Costo Presupuestado"

Esta categoría es especial y **solo aplica** cuando el gasto es un costo que
**ya estaba incluido dentro del margen de un presupuesto** — por ejemplo, el
papel o la tinta de un trabajo puntual que ya se presupuestó con ese costo
adentro. Por eso el sistema **exige** asociarla a un trabajo: sin trabajo, no
hay margen contra el cual descontarla, y queda rechazada.

> **¿Por qué funciona así?**
> La ganancia de un trabajo presupuestado ya sale de restarle el costo al
> precio (está "adentro" del margen). Si ese mismo costo se cargara además
> como un Gasto común, se restaría **dos veces** de la ganancia neta del
> dashboard. Ejemplo: un trabajo de $14.000 con $10.000 de costo y 40% de
> margen deja $4.000 de ganancia al cobrarse. Si esos $10.000 de papel se
> cargan como Gasto común, el dashboard mostraría –$6.000 en vez de $4.000.
> Por eso: el gasto en "Costo Presupuestado" **sí** cuenta como plata que
> salió de la caja (aparece en el total de Egresos), pero **no** vuelve a
> restar de la Ganancia Neta. Cualquier otro gasto (insumos sueltos,
> alquiler, sueldos, o el costo de un trabajo que nunca tuvo presupuesto) sí
> resta normalmente.

### Editar un gasto de un trabajo ya entregado

El selector de trabajo al editar un gasto solo lista trabajos activos, pero
si el gasto ya estaba asociado a un trabajo Entregado, el sistema agrega esa
opción igual (marcada como "(entregado)") para que editar el gasto nunca
borre esa asociación sin querer.

---

## 7. Stock

### Cómo se usa

- **+ Nuevo Artículo** abre un formulario con **carrito de compra**: se
  pueden cargar varias altas o recompras en una sola operación ("Registrar
  compra"). Cada línea puede ser un artículo nuevo o una recompra de uno
  existente (sumando cantidad al que ya está).
- Unidades disponibles: Unidades, Resmas, Litros, Metros, Centímetros,
  **Kilogramos** (se convierte automáticamente a pliegos), Paquetes y
  Pliegos.
- **Compra de papel por Kg**: se cargan el largo, ancho y gramaje del pliego
  más el peso total comprado, y el sistema calcula solos los pliegos:
  `(Largo × Ancho × Gramaje) ÷ 10.000.000 = peso de 1 pliego`, y de ahí
  cuántos pliegos entran en el peso comprado. El artículo queda cargado
  directamente en **Pliegos**, así la orden de producción puede descontar
  pliegos enteros.
- El **Costo Unit.** que se ve en la tabla es el **costo de reposición**: se
  actualiza con el precio de la última compra, no es un promedio de todas las
  compras históricas. Es el criterio elegido a propósito para cotizar
  presupuestos con lo que cuesta reponer el papel *hoy*.
- Cada cambio de cantidad (alta, compra o ajuste manual) queda **registrado
  en el historial del artículo** con su motivo — nunca se pisa una cantidad
  en silencio.
- Un artículo con cantidad por debajo del **mínimo de alerta** se marca en
  rojo en la tabla.

### Eliminar un artículo

No se puede eliminar un artículo de stock que esté siendo usado como papel
en algún trabajo o en algún presupuesto (aunque sea antiguo).

---

## 8. Cheques

### Cómo se usa

- **+ Ingresar Cheque**: tipo (**Recibido** de un cliente, o **Emitido** para
  pagarle a un proveedor), banco, número, monto y fechas de emisión y de
  cobro.
- Un cheque **Recibido** se puede asociar opcionalmente a un trabajo: si no
  se asocia, el cheque igual salda la deuda del cliente, pero **no suma
  ganancia calculable** al dashboard hasta que se le asigne un trabajo (se
  puede hacer después).
- **Estados y transiciones permitidas**:
  - `En Cartera` → `Depositado`, `Endosado` o `Rechazado`
  - `Depositado` → `Cobrado` o `Rechazado`
  - `Cobrado`, `Endosado` y `Rechazado` son **estados finales**.
- Revertir un estado final (por ejemplo, de `Cobrado` volver a `En Cartera`)
  exige escribir un **motivo**, que queda asentado en el historial del
  cheque (botón para ver el historial completo de cada cheque).
- Un cheque en `Cobrado` o `Endosado` **no admite** cambiarle el monto ni la
  clasificación, y **no se puede eliminar** (si corresponde, se marca
  `Rechazado`).

### Endosar un cheque = ingreso y egreso al mismo tiempo

Cuando un cheque recibido se usa para pagarle a un proveedor (se **endosa**),
esa operación es en simultáneo un cobro (la plata del cliente se realiza) y
un pago (se le está pagando a alguien más con ese mismo cheque). Por eso, al
marcar un cheque como `Endosado`, el sistema **ofrece crear automáticamente
el Gasto** correspondiente a ese pago (con el destinatario, categoría y
descripción precargados).

> **¿Por qué se ofrece el Gasto en vez de crearse solo?**
> Porque el operador es quien sabe si ese pago a proveedor ya se registró de
> otra forma, o corresponde a una categoría específica, así que la carga
> queda como una confirmación, no automática. Si el Gasto no se llegara a
> crear, el sistema seguiría contando el cheque como ingreso, pero los
> egresos del dashboard quedarían subestimados (y la ganancia, sobrestimada).
> Por el lado del cálculo: el cheque endosado se computa como cobrado usando
> la fecha de endoso, exactamente igual que un cheque `Cobrado` usa su fecha
> de cobro.

### Los KPIs de cheques del dashboard

El KPI "Cheques en Cartera" solo suma los cheques **Recibidos** (plata por
cobrar); los cheques **Emitidos** propios se cuentan aparte como "Cheques a
Pagar" (plata que va a salir).

---

## 9. Asistencia

Registro de la jornada de cada empleado: a qué hora entró y a qué hora salió,
día por día. El sistema calcula solo las horas trabajadas y permite sacar el
total de un período.

### Cómo se usa

- Arriba a la derecha está el selector de **Día**. Arranca en la fecha de hoy;
  cambiarlo trae la planilla de ese día.
- La tabla muestra **una fila por empleado activo**, aunque todavía no tenga
  nada cargado. Se completan **Entrada** y **Salida**, y la columna **Horas** se
  actualiza sola.
- La columna **Observaciones** es texto libre para lo que no entra en un
  horario: "franco", "faltó", "se fue al mediodía", "vino a la tarde".
- **💾 Guardar día** guarda la planilla **completa** de una sola vez. No hay que
  guardar empleado por empleado.
- Se puede guardar el mismo día varias veces: cargar la entrada a la mañana y
  volver a la tarde para completar la salida. El segundo guardado **actualiza**
  la fila, no la duplica.
- Para **borrar** una carga equivocada, se vacían los tres campos de esa fila y
  se guarda el día: la fila queda sin registro.
- Abajo está **Total de horas por período**: se eligen dos fechas y "Ver total"
  muestra, por empleado, cuántos días trabajó y el total de horas.

### Alta y baja de empleados

El botón **👥 Empleados** abre el panel lateral de administración:

- Escribir el nombre y **Agregar** da de alta a alguien nuevo. Desde el
  siguiente guardado ya aparece en la planilla del día.
- **✏️** permite corregir un nombre mal escrito.
- **Dar de baja** es lo que corresponde cuando alguien deja de trabajar en el
  taller. Sale de la planilla del día, pero **las horas que ya trabajó no se
  pierden**: siguen apareciendo en los totales de los meses en que estuvo. Si
  vuelve, **Reactivar** lo pone de nuevo en la planilla.
- **🗑️** borra al empleado de verdad, y sólo funciona si **nunca** se le cargó
  un día. Sirve para deshacer un alta equivocada (un nombre repetido, por
  ejemplo), no para dar de baja a alguien que trabajó.

> **¿Por qué funciona así?**
> Dar de baja y borrar son cosas distintas a propósito. Si borrar a un empleado
> se llevara puesto su historial, los totales de horas de los meses anteriores
> cambiarían de golpe y ya no coincidirían con lo que se pagó en su momento. Es
> el mismo criterio que protege a los movimientos de cuenta corriente y al
> historial de stock: lo que ya pasó no se toca.

> **¿Por qué funciona así?**
> Las horas no se cargan a mano, se calculan a partir de la entrada y la salida.
> Así no pueden quedar desfasadas: si se corrige un horario, el total se rehace
> solo. Por eso tampoco se acepta una hora de salida anterior a la de entrada —
> en el taller no hay turno noche, así que eso es siempre un error de tipeo
> (18:00 tecleado como 8:00), y dejarlo pasar metería una jornada falsa en el
> total del mes.

> **¿Por qué funciona así?**
> El total del período cuenta sólo los días con la **jornada completa**. Un día
> con la entrada cargada pero sin la salida no aporta horas, así que tampoco
> suma como día trabajado: si contara, el promedio de horas por día saldría mal.

---

## 10. Dashboard (Panel de Control)

El dashboard resume la caja y la producción del taller. Tiene un selector de
período (Este Mes, Mes Pasado, Este Año, Histórico) que afecta a los KPIs
financieros.

- **Ingresos (Cobrado)**: plata que efectivamente entró en el período (pagos
  que no son cheque, más cheques que se cobraron o se endosaron en ese
  período).
- **Egresos (Gastos)**: toda la plata que salió de la caja en el período,
  sin excepciones.
- **Ganancia Neta**: la ganancia proporcional a lo cobrado de cada trabajo
  presupuestado, menos los gastos que sí restan (ver sección 6, "Costo
  Presupuestado"). Cuando hay gastos de esa categoría en el período, aparece
  una leyenda aclarando cuánto no se descontó porque ya estaba en algún
  margen.
- **Plata en la Calle**: trabajos ya **Entregados** con saldo pendiente de
  cobro (los "morosos" del período, listados debajo).
- **Cheques en Cartera** / **Cheques a Pagar**: ver sección 8.
- **Trabajos Pendientes**: trabajos que siguen en el taller (Aprobado, En
  Diseño o En Producción).
- **No contemplados en ingresos**: trabajos que no tienen ningún presupuesto
  asociado — no aportan ganancia calculable aunque se les cobre, porque no
  hay margen del cual sacar la fracción de ganancia.
- **Plata estancada en Taller**: valor de venta de los trabajos aprobados o
  en producción que todavía no se entregaron.

> **¿Por qué a veces la ganancia neta da negativa un mes sin que sea una
> pérdida real?**
> La ganancia se calcula por lo **cobrado** en el período; los gastos, por su
> **fecha de gasto**. Un mes con una compra grande de material y poca
> cobranza puede mostrar un número negativo aunque el negocio esté sano — es
> el desfase natural de mirar la caja mes a mes, no un error del sistema.

Si el backend no responde, el dashboard muestra los KPIs financieros como
"—" (no como "$0", que se confundiría con "no hubo movimiento") junto con un
aviso de error.

---

## 11. Auditoría

Sólo la ve Administración. Es la respuesta a "¿quién me tocó esto?".

### Cómo se usa

La pestaña muestra una lista de todo lo que se modificó en el sistema, de lo
más reciente a lo más viejo. Cada renglón dice **cuándo**, **quién**, **qué
hizo** y **sobre qué**:

| Fecha | Quién | Acción | Qué | Detalle |
|---|---|---|---|---|
| 28/07 14:32 | marcos | editó | Trabajo OP-000012 (Juan Pérez) | estado: Aprobado -> En Diseño |
| 28/07 11:05 | facundo | eliminó | Gasto Tinta negra — $ 45000 (Insumos) | |
| 28/07 09:14 | lucio | creó | Cliente Ana Gómez | |

Arriba hay cuatro filtros que se combinan entre sí:

- **Qué**: el módulo (Trabajos, Clientes, Gastos, Stock…).
- **Quién**: el nombre de usuario de la persona.
- **Desde / Hasta**: el rango de fechas, ambas incluidas.

Se muestran hasta 200 movimientos por vez. Si la lista llega a ese tope, al pie
aparece un aviso: hay más atrás y conviene acotar las fechas.

### Qué queda registrado

Todo lo que modifica datos: altas, ediciones y borrados de trabajos,
presupuestos, clientes, pagos, cheques, gastos, stock, notas, empleados y la
planilla de asistencia. También **los ingresos al sistema** y los **intentos
fallidos** (alguien tipeando mal la contraseña, o probando).

Lo que **no** deja renglón es mirar. Entrar a una pantalla, abrir una ficha o
descargar un PDF ya emitido no cambia nada, así que no figura.

> **¿Por qué no se puede borrar ni corregir un renglón?**
> Porque entonces no serviría para nada: cualquiera que quisiera tapar algo
> borraría primero la fila que lo delata. Por eso la pantalla no tiene botón de
> editar ni de eliminar, y el sistema tampoco tiene forma de hacerlo por
> ningún otro lado. El registro sólo se lee.

> **¿Y si borro un trabajo? ¿Se pierde su historial?**
> No. El renglón de auditoría sobrevive a lo que registra: aunque el trabajo,
> el cliente o el cheque ya no existan, queda la constancia de que existieron,
> quién los borró y cuándo. En un borrado el renglón guarda además los datos
> que importaban (el monto de un gasto, el banco y número de un cheque), que si
> no se perderían con la ficha.

> **Los renglones no dicen "Marcos" sino "marcos"**, en minúscula: es el nombre
> de usuario con el que entró, no cómo se escribe el nombre de la persona.

---

## 12. Preguntas frecuentes y mensajes de error comunes

**"Este DNI/CUIT ya está registrado."**
Ya existe un cliente con ese número. Buscalo en el listado en vez de crear
uno nuevo.

**"No se puede eliminar: el cliente/trabajo tiene [pagos / presupuestos /
gastos / cheques] asociados."**
El sistema protege el historial: en vez de borrar, cancelá el trabajo o
resolvé primero esos vínculos.

**"Asigná un cliente antes de convertir" / no puedo convertir un
presupuesto.**
Un presupuesto se puede guardar como borrador sin cliente, pero para
convertirlo en trabajo necesita tener un cliente asignado.

**"Este presupuesto ya fue convertido a trabajo."**
No se puede convertir dos veces, ni volver a editarlo o borrarlo. Si hace
falta corregir algo, se genera una nueva versión.

**"Para pasar a En Diseño usá Iniciar Diseño."**
No se puede arrastrar directo esa columna en el tablero: hay que usar el
botón que pide registrar la seña (o el motivo si no hubo seña).

**"Imprimí la orden de producción antes de mandar el trabajo a
producción."**
Falta imprimir la orden del trabajo — eso es lo que descuenta el papel del
stock.

**"No alcanza el papel [artículo]: hay X y la orden necesita Y."**
El stock no cubre lo que pide la orden. Si el papel se va a comprar en el
momento, se puede **forzar** la impresión de todos modos.

**"Los cheques se registran desde el módulo Cheques."**
Intentaste cargar un pago con método "Cheque" en Movimientos. Cargalo desde
el módulo Cheques (o desde el formulario de pago, eligiendo "Cheque" como
método, que deriva ahí solo).

**"El cheque está en estado 'X' (final). Para revertirlo indicá un
motivo."**
Un cheque Cobrado, Endosado o Rechazado no cambia de estado en silencio:
hace falta escribir por qué se revierte.

**"No se puede modificar 'monto'/'clasificación' de un cheque en estado
'Cobrado'/'Endosado'."**
Esos datos quedan congelados una vez que el cheque impactó ingresos. Si el
dato estaba mal, primero hay que revertir el estado con un motivo.

**"El trabajo ya está pago: no hay saldo pendiente que cubrir." / "El
cliente no tiene saldo a favor disponible."**
Mensajes del botón "Aplicar saldo a favor": el trabajo no debe nada, o el
cliente no tiene plata a favor para aplicar.

**Dashboard con los indicadores en "—".**
El backend no respondió. Verificá que el sistema esté corriendo y recargá la
página — no es que no hubo movimiento en el período.

**"Revisá los horarios" / "La hora de salida tiene que ser posterior a la de
entrada."**
En Asistencia hay alguien con la salida cargada antes que la entrada. Suele
ser un error de tipeo (18:00 escrito como 8:00).

**"No se puede eliminar: [nombre] tiene N día(s) de asistencia cargados."**
Estás intentando borrar un empleado que ya trabajó. Usá **Dar de baja** en su
lugar: sale de la planilla pero no se pierde el historial de horas.

**En Asistencia falta un empleado en la planilla.**
Está dado de baja. Abrí **👥 Empleados** y tocá **Reactivar**.

**En Asistencia, la columna Horas muestra "—".**
Falta cargar la entrada o la salida de esa fila. Con la jornada incompleta no
hay horas que calcular, y ese día tampoco suma en el total del período.
