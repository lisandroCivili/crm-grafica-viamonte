// Trabajos: alta, edicion, tablero Kanban y ordenes de produccion.

// Las etapas del tablero y en qué columna cae cada una. Los nombres son los
// mismos que valida el backend (models.ESTADOS_TRABAJO); "Cancelado" no está
// porque no tiene columna propia. Sale de acá tanto el armado del tablero como
// el menú de "Mover a", para que no haya dos listas que puedan desincronizarse.
const COLUMNAS_KANBAN = {
    "Aprobado": "col-pendiente",
    "En Diseño": "col-diseno",
    "En Producción": "col-produccion",
    "Entregado": "col-entregado"
};

// ==========================================
// EDICIÓN DE TRABAJOS (Historial automático)
// ==========================================
// Recibe SOLO el id: antes se le pasaban la descripción y los importes
// serializados en el atributo onclick, y cualquier apóstrofo en la descripción
// rompía el HTML. Todos los datos salen del backend, que ya es la fuente de verdad.
async function abrirModalEditarTrabajo(id) {
    document.getElementById('fe_trabajo_id').value = id;
    document.getElementById('fe_razon').value = '';

    await cargarSelectoresPapel();
    const trabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const t = trabajos.find(x => x.id === id) || {};

    const set = (campo, valor) => { document.getElementById(campo).value = valor ?? ''; };
    set('fe_descripcion', t.descripcion_producto);
    set('fe_cantidad', t.cantidad);
    set('fe_precio', t.precio_venta);
    set('fe_papel_id', t.papel_id);
    set('fe_cantidad_pliegos', t.cantidad_pliegos);
    set('fe_papel_tipo', t.papel_tipo);
    set('fe_medida_terminado', t.medida_terminado);
    set('fe_medida_pliego', t.medida_pliego);
    set('fe_corte_pliego', t.corte_pliego);
    set('fe_tintas', t.tintas);
    set('fe_troquelado', t.troquelado);
    set('fe_barniz', t.barniz);
    set('fe_otros', t.otros);

    // Con la orden impresa, el papel y los pliegos quedan congelados: ya
    // descontaron stock. El backend igual lo rechaza; acá lo mostramos claro.
    const bloqueado = !!t.orden_impresa;
    document.getElementById('fe_papel_id').disabled = bloqueado;
    document.getElementById('fe_cantidad_pliegos').disabled = bloqueado;
    document.getElementById('fe_aviso_impresa').style.display = bloqueado ? 'block' : 'none';

    // Va después del bloqueo por orden impresa: si la orden ya salió, el selector
    // queda deshabilitado y la función no toca nada.
    sincronizarPliegosConPapel('fe_papel_id', 'fe_cantidad_pliegos');

    toggleDrawer('drawer-editar-trabajo');
}

async function guardarEdicionTrabajo(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const id = document.getElementById('fe_trabajo_id').value;
    const razon = document.getElementById('fe_razon').value;
    const nuevoPrecio = parseFloat(document.getElementById('fe_precio').value);
    const nuevaCantidad = parseInt(document.getElementById('fe_cantidad').value);
    const nuevaDesc = document.getElementById('fe_descripcion').value;

    const opt = (campo) => {
        const el = document.getElementById(campo);
        const v = el ? el.value.trim() : "";
        return v === "" ? null : v;
    };

    try {
        const data = {
            descripcion_producto: nuevaDesc,
            cantidad: nuevaCantidad,
            papel_tipo: opt('fe_papel_tipo'),
            medida_terminado: opt('fe_medida_terminado'),
            medida_pliego: opt('fe_medida_pliego'),
            corte_pliego: opt('fe_corte_pliego'),
            tintas: opt('fe_tintas'),
            troquelado: opt('fe_troquelado'),
            barniz: opt('fe_barniz'),
            otros: opt('fe_otros')
        };
        // El precio sólo lo manda quien lo ve. Para los demás el campo está
        // oculto y vacío: mandarlo igual le borraría el precio al trabajo cada
        // vez que el taller corrige unas tintas. El backend además lo descarta
        // por su cuenta, porque esto no se puede confiar al navegador.
        if (puedeVerPlata()) data.precio_venta = nuevoPrecio;

        // Papel y pliegos sólo se mandan si no están congelados por la orden impresa.
        if (!document.getElementById('fe_papel_id').disabled) {
            data.papel_id = opt('fe_papel_id');
            data.cantidad_pliegos = opt('fe_cantidad_pliegos');
        }

        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "No se pudo guardar el cambio."));
        }

        // Nota: antes se registraba un Movimiento con monto:0 como log del cambio.
        // Se eliminó para no ensuciar el historial financiero (los movimientos son solo plata real).

        toggleDrawer('drawer-editar-trabajo');
        abrirFicha(clienteActualFicha);
        cargarTrabajos();

    } catch (error) {
        Swal.fire('No se pudo guardar', error.message, 'error');
    } finally {
        restore();
    }
}

async function eliminarTrabajo(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️ Borrar';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este trabajo?',
        text: "Esta acción no se puede deshacer. Si ya tiene pagos o gastos asociados, usá el estado \"Cancelado\" en su lugar.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#555',
        confirmButtonText: 'Sí, borrarlo',
        cancelButtonText: 'Cancelar'
    });

    if (!confirmacion.isConfirmed) return;

    if (button) {
        button.disabled = true;
        button.innerText = 'Borrando...';
    }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            abrirFicha(clienteActualFicha);
            cargarTrabajos();
            Swal.fire('¡Eliminado!', 'El trabajo fue borrado del sistema.', 'success');
        } else {
            const err = await resp.json();
            Swal.fire('No se pudo eliminar', detalleError(err, 'Error desconocido'), 'error');
        }
    } catch (e) {
        console.error("Error al eliminar trabajo:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

async function guardarTrabajo(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const cliente_id = document.getElementById('ft_cliente_id').value;
    const desc = document.getElementById('ft_descripcion').value.trim();
    const notas = document.getElementById('ft_notas') ? document.getElementById('ft_notas').value.trim() : "";

    // Helper local: devuelve el valor del input o null si está vacío (así no
    // mandamos strings vacíos como si fueran datos de la boleta).
    const opt = (campo) => {
        const el = document.getElementById(campo);
        const v = el ? el.value.trim() : "";
        return v === "" ? null : v;
    };

    try {
        const data = {
            cliente_id: cliente_id,
            descripcion_producto: desc,
            precio_venta: parseFloat(document.getElementById('ft_precio').value),
            notas_iniciales: notas || null,
            fecha_creacion: fechaHoyLocal(),
            estado: "Aprobado",
            // Datos de la orden de producción (todos opcionales)
            papel_id: opt('ft_papel_id'),
            cantidad_pliegos: opt('ft_cantidad_pliegos'),
            papel_tipo: opt('ft_papel_tipo'),
            medida_terminado: opt('ft_medida_terminado'),
            medida_pliego: opt('ft_medida_pliego'),
            corte_pliego: opt('ft_corte_pliego'),
            tintas: opt('ft_tintas'),
            troquelado: opt('ft_troquelado'),
            barniz: opt('ft_barniz')
        };

        const resp = await fetch(`${API_URL}/trabajos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (!resp.ok) {
            // Sin este chequeo, el body de error no trae `id` y la línea de abajo
            // reventaba con TypeError, dejando el drawer abierto y sin mensaje.
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar el trabajo', detalleError(error), 'error');
            return;
        }
        const nuevoTrabajo = await resp.json();
        const shortId = nuevoTrabajo.id.substring(0,6).toUpperCase();

        // (Se eliminó el Movimiento monto:0 de "Ingreso de trabajo": no es plata real.)

        if (notas) {
            await fetch(`${API_URL}/notas/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cliente_id: cliente_id,
                    trabajo_id: nuevoTrabajo.id,
                    texto: `Nota inicial (Trabajo #${shortId}): ${notas}`
                })
            });
        }

        document.getElementById('form-trabajo').reset();
        // reset() limpia los valores pero no el estado deshabilitado: si el trabajo
        // que se acaba de guardar tenía papel, el campo de pliegos quedaría activo
        // y vacío para el siguiente.
        sincronizarPliegosConPapel('ft_papel_id', 'ft_cantidad_pliegos');
        toggleDrawer('drawer-nuevo-trabajo');
        cargarTrabajos();

        if (clienteActualFicha === cliente_id && document.getElementById('drawer-cliente').classList.contains('open')) {
            abrirFicha(clienteActualFicha);
        }
    } catch (error) {
        console.error("Error al guardar trabajo:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar el trabajo.', 'error');
    } finally {
        restore();
    }
}

// Kanban y Drag & Drop
async function cargarSelectorClientes() {
    const clientes = await (await fetch(`${API_URL}/clientes/`)).json();
    const selector = document.getElementById('ft_cliente_id');
    if(!selector) return;
    selector.innerHTML = '<option value="">Seleccione un cliente...</option>';
    clientes.forEach(c => selector.innerHTML += `<option value="${c.id}">${esc(c.nombre_completo)}</option>`);
    cargarSelectoresPapel();
}

// Puebla los selects de papel (alta y edición de trabajo) con los artículos de
// stock. El papel es opcional: la primera opción es vacía. Sólo listamos
// artículos en Pliegos: el backend rechaza cualquier otra unidad (no tiene
// sentido descontarle "3 pliegos" a un bidón de tinta en litros). El presupuesto
// tiene su propio poblado por tarjeta de ítem (ver cargarSelectorPapelItem).
async function cargarSelectoresPapel() {
    const stock = await (await fetch(`${API_URL}/stock/`)).json();
    const papeles = stock.filter(a => a.unidad === 'Pliegos');
    const opciones = '<option value="">Sin papel del stock</option>' +
        papeles.map(a => `<option value="${a.id}">${esc(a.nombre)} (${a.cantidad} ${a.unidad})</option>`).join('');
    ['ft_papel_id', 'fe_papel_id', 'fop_papel_id'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) {
            const actual = sel.value;
            sel.innerHTML = opciones;
            sel.value = actual; // conservamos la selección si ya había una
            // Repintar el select puede dejarlo sin selección (si ese papel se
            // agotó o se borró del stock, la opción ya no existe). El campo de
            // pliegos tiene que seguir a ese cambio, que no dispara onchange.
            sincronizarPliegosConPapel(id, id.replace('_papel_id', '_cantidad_pliegos'));
        }
    });
}

// Los pliegos sólo tienen sentido con un papel del stock elegido: sin papel no hay
// de dónde descontarlos, y el backend rechaza el par incompleto con un 400. En vez
// de que el operador se entere recién al guardar, el campo se deshabilita y se
// limpia mientras no haya papel. Hay que llamarla al abrir cada formulario (para
// fijar el estado inicial) además de en el onchange del selector.
function sincronizarPliegosConPapel(idSelect, idPliegos) {
    const sel = document.getElementById(idSelect);
    const input = document.getElementById(idPliegos);
    if (!sel || !input) return;

    // Con la orden ya impresa los dos campos quedan congelados desde afuera
    // (descontaron stock): no hay que reactivar el de pliegos.
    if (sel.disabled) return;

    const hayPapel = !!sel.value;
    input.disabled = !hayPapel;
    if (!hayPapel) input.value = '';
}

function permitirSoltar(ev) { ev.preventDefault(); }
function arrastrarTarjeta(ev, id) { ev.dataTransfer.setData("text", id); }

// Refresca el Kanban y, si está abierta, la ficha del cliente. Es también el
// "rollback": al re-renderizar desde el backend, cualquier tarjeta que se haya
// movido a una columna que el backend rechazó vuelve a su lugar real.
function refrescarTablero() {
    cargarTrabajos();
    const drawerCliente = document.getElementById('drawer-cliente');
    if (clienteActualFicha && drawerCliente.classList.contains('open')) {
        abrirFicha(clienteActualFicha);
    }
}

async function soltarTarjeta(ev, nuevoEstado) {
    ev.preventDefault();
    return moverTrabajo(ev.dataTransfer.getData("text"), nuevoEstado);
}

// Lleva un trabajo a otra etapa. Está separado del drop porque el arrastre no
// funciona con el dedo: en el celular se llega acá desde el botón "Mover a" de
// la tarjeta. Las reglas de a dónde puede ir un trabajo viven todas acá, así
// que el menú y el arrastre se comportan igual.
async function moverTrabajo(id, nuevoEstado, forzar = false) {
    // No movemos el DOM de entrada: con los guards nuevos el backend rechaza
    // seguido. Dejamos que refrescarTablero() posicione la tarjeta según la
    // respuesta real, así nunca queda en una columna donde el backend no la puso.

    // Pasar a En Diseño va por su propio flujo: hay que registrar la seña.
    if (nuevoEstado === "En Diseño") {
        return iniciarDisenoDesdeKanban(id);
    }

    // Pasar a Producción arranca pidiendo los datos de la boleta: es el momento
    // en que se conocen, y sin ellos la orden sale impresa vacía.
    if (nuevoEstado === "En Producción") {
        return abrirDatosProduccion(id);
    }

    try {
        const url = `${API_URL}/trabajos/${id}${forzar ? '?forzar=true' : ''}`;
        const resp = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            // 400 típico al marcar Entregado: queda mercadería sin entregar.
            // El propio mensaje del backend ya trae la pregunta armada.
            if (resp.status === 400 && nuevoEstado === "Entregado" && !forzar) {
                const r = await Swal.fire({
                    title: 'Queda mercadería sin entregar',
                    text: detalleError(err, ''),
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Marcarlo Entregado igual',
                    cancelButtonText: 'Cancelar'
                });
                if (r.isConfirmed) return moverTrabajo(id, nuevoEstado, true);
                refrescarTablero();
                return;
            }
            throw new Error(detalleError(err, "El backend rechazó el cambio de estado."));
        }
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo mover el trabajo', error.message, 'error');
        refrescarTablero();
    }
}

// Elegir a qué etapa mandar el trabajo desde un menú, en vez de arrastrarlo.
// Es la única forma de mover una tarjeta en el celular: el drag & drop del
// navegador no responde al dedo. En la PC el botón no se muestra.
async function abrirMenuMover(id) {
    const t = trabajosPorId.get(id);
    if (!t) return;

    // Todas las etapas menos en la que ya está: ofrecerla sería un movimiento
    // que no hace nada.
    const destinos = Object.keys(COLUMNAS_KANBAN).filter(estado => estado !== t.estado);

    const { value: destino } = await Swal.fire({
        title: 'Mover el trabajo a...',
        input: 'radio',
        inputOptions: Object.fromEntries(destinos.map(estado => [estado, estado])),
        inputValidator: valor => !valor && 'Elegí una etapa',
        showCancelButton: true,
        confirmButtonText: 'Mover',
        cancelButtonText: 'Cancelar'
    });
    if (!destino) return;

    // La misma función que usa el arrastre: iniciar diseño sigue pidiendo la
    // seña y bajar a producción sigue pidiendo los datos de la boleta. Acá no
    // se repite ninguna de esas reglas.
    moverTrabajo(id, destino);
}

// Pide la seña (monto + método + motivo) y arranca el diseño.
async function iniciarDisenoDesdeKanban(id) {
    const { value: datos } = await Swal.fire({
        title: 'Iniciar diseño',
        html: `
            <input id="swal-monto" type="number" step="0.01" min="0" class="swal2-input" placeholder="Monto abonado ($)">
            <select id="swal-metodo" class="swal2-input">
                <option value="Efectivo">Efectivo</option>
                <option value="Transferencia">Transferencia</option>
                <option value="Cheque">Cheque</option>
            </select>
            <div id="swal-cheque" style="display:none;">
                <input id="swal-ch-banco" type="text" class="swal2-input" placeholder="Banco del cheque">
                <input id="swal-ch-numero" type="text" class="swal2-input" placeholder="N° de cheque">
                <input id="swal-ch-cobro" type="date" class="swal2-input" title="Fecha de cobro del cheque">
            </div>
            <input id="swal-motivo" type="text" class="swal2-input" placeholder="Motivo (si no hay seña)">
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Iniciar diseño',
        cancelButtonText: 'Cancelar',
        didOpen: () => {
            // La seña con cheque pide los datos del cheque (se crea uno recibido).
            const metodoSel = document.getElementById('swal-metodo');
            const bloque = document.getElementById('swal-cheque');
            const toggle = () => { bloque.style.display = metodoSel.value === 'Cheque' ? 'block' : 'none'; };
            metodoSel.addEventListener('change', toggle);
            toggle();
        },
        preConfirm: () => {
            const monto = parseFloat(document.getElementById('swal-monto').value || '0');
            const metodo = document.getElementById('swal-metodo').value;
            const motivo = document.getElementById('swal-motivo').value.trim();
            if (isNaN(monto) || monto < 0) {
                Swal.showValidationMessage('El monto no puede ser negativo.');
                return false;
            }
            if (monto === 0 && !motivo) {
                Swal.showValidationMessage('Si no hay seña, el motivo es obligatorio.');
                return false;
            }
            const datos = { monto, metodo, motivo: motivo || null };
            if (monto > 0 && metodo === 'Cheque') {
                datos.banco = document.getElementById('swal-ch-banco').value.trim();
                datos.numero = document.getElementById('swal-ch-numero').value.trim();
                datos.fecha_cobro = document.getElementById('swal-ch-cobro').value || null;
                if (!datos.banco || !datos.numero || !datos.fecha_cobro) {
                    Swal.showValidationMessage('Para una seña con cheque completá banco, número y fecha de cobro.');
                    return false;
                }
            }
            return datos;
        }
    });

    if (!datos) { refrescarTablero(); return; }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}/iniciar-diseno`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "No se pudo iniciar el diseño."));
        }
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo iniciar el diseño', error.message, 'error');
        refrescarTablero();
    }
}

// ==========================================
// DATOS DE PRODUCCIÓN (al pasar a En Producción)
// ==========================================
// Los trabajos que nacen de un presupuesto nunca pasan por el alta manual: llegan
// con el papel heredado del ítem pero sin medidas, tintas ni terminaciones, y la
// orden salía impresa vacía. Se piden acá, cuando el trabajo baja a máquina y
// esos datos realmente se conocen. Es el gemelo del alta sin el precio.
async function abrirDatosProduccion(id) {
    document.getElementById('fop_trabajo_id').value = id;

    await cargarSelectoresPapel();
    const trabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const t = trabajos.find(x => x.id === id);
    if (!t) { refrescarTablero(); return; }

    // El drawer se abre desde una tarjeta: sin esto no se sabe cuál se está cargando.
    document.getElementById('fop_titulo').textContent =
        `${t.descripcion_producto || 'Trabajo'} · #${id.substring(0, 6).toUpperCase()}`;

    // Se precarga lo que ya venga (del presupuesto o de una carga anterior): el
    // operador completa lo que falta, no vuelve a tipear todo.
    const set = (campo, valor) => { document.getElementById(campo).value = valor ?? ''; };
    set('fop_papel_id', t.papel_id);
    set('fop_cantidad_pliegos', t.cantidad_pliegos);
    set('fop_papel_tipo', t.papel_tipo);
    set('fop_medida_terminado', t.medida_terminado);
    set('fop_medida_pliego', t.medida_pliego);
    set('fop_corte_pliego', t.corte_pliego);
    set('fop_tintas', t.tintas);
    set('fop_troquelado', t.troquelado);
    set('fop_barniz', t.barniz);
    set('fop_otros', t.otros);

    // Mismo congelamiento que el drawer de edición: con la orden ya impresa el
    // papel y los pliegos descontaron stock y el backend rechaza cambiarlos.
    const bloqueado = !!t.orden_impresa;
    document.getElementById('fop_papel_id').disabled = bloqueado;
    document.getElementById('fop_cantidad_pliegos').disabled = bloqueado;
    document.getElementById('fop_aviso_impresa').style.display = bloqueado ? 'block' : 'none';

    // Va después del bloqueo, igual que en la edición: si está congelado no toca nada.
    sincronizarPliegosConPapel('fop_papel_id', 'fop_cantidad_pliegos');

    toggleDrawer('drawer-datos-produccion');
}

// Guarda los datos de la boleta y sigue con la emisión de la orden. El PUT va
// SIN estado a propósito: el backend exige la orden impresa para pasar a
// Producción, así que el cambio de columna es el último paso de la cadena.
async function guardarDatosProduccion(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const id = document.getElementById('fop_trabajo_id').value;

    const opt = (campo) => {
        const el = document.getElementById(campo);
        const v = el ? el.value.trim() : "";
        return v === "" ? null : v;
    };

    let guardado = false;
    try {
        const data = {
            papel_tipo: opt('fop_papel_tipo'),
            medida_terminado: opt('fop_medida_terminado'),
            medida_pliego: opt('fop_medida_pliego'),
            corte_pliego: opt('fop_corte_pliego'),
            tintas: opt('fop_tintas'),
            troquelado: opt('fop_troquelado'),
            barniz: opt('fop_barniz'),
            otros: opt('fop_otros')
        };
        // Papel y pliegos sólo se mandan si no están congelados por la orden impresa.
        if (!document.getElementById('fop_papel_id').disabled) {
            data.papel_id = opt('fop_papel_id');
            data.cantidad_pliegos = opt('fop_cantidad_pliegos');
        }

        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "No se pudieron guardar los datos de producción."));
        }

        guardado = true;
    } catch (error) {
        // El drawer queda abierto para corregir y la tarjeta no se movió.
        Swal.fire('No se pudo guardar', error.message, 'error');
    } finally {
        restore();
    }

    // Fuera del try: un problema en la emisión de la orden es otro error, con su
    // propio mensaje, y no debe reportarse como si no se hubieran guardado los datos.
    if (guardado) {
        toggleDrawer('drawer-datos-produccion');
        await pasarAProduccionDesdeKanban(id);
    }
}

// Abandonar la carga deja el trabajo donde estaba: el tablero se re-renderiza
// desde el backend y la tarjeta vuelve a su columna real.
function cancelarDatosProduccion() {
    toggleDrawer('drawer-datos-produccion');
    refrescarTablero();
}

// Segundo tramo del pase a Producción: imprime la orden si falta (la emisión
// descuenta el papel y numera la boleta) y recién ahí cambia el estado. Sin
// pregunta intermedia: el único llamador es guardarDatosProduccion, y "Guardar
// y emitir orden" ya es la confirmación explícita del operador.
async function pasarAProduccionDesdeKanban(id) {
    const trabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const t = trabajos.find(x => x.id === id);
    if (!t) { refrescarTablero(); return; }

    if (!t.orden_impresa) {
        const impreso = await descargarOrden(id);
        if (!impreso) { refrescarTablero(); return; } // stock insuficiente u otro error
    }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: "En Producción" })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "El backend rechazó el cambio."));
        }
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo pasar a producción', error.message, 'error');
        refrescarTablero();
    }
}

// Descarga el PDF de la orden. Devuelve true si se emitió. Si el papel no
// alcanza, ofrece forzar (se compra el papel en el momento). El backend es
// idempotente: si ya estaba impresa, sólo re-descarga sin volver a descontar.
async function descargarOrden(id, forzar = false) {
    try {
        const url = `${API_URL}/trabajos/${id}/imprimir-orden${forzar ? '?forzar=true' : ''}`;
        const resp = await fetch(url, { method: 'POST' });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            // 400 típico: no alcanza el papel. Ofrecemos emitir igual.
            if (resp.status === 400 && !forzar) {
                const r = await Swal.fire({
                    title: 'Stock de papel insuficiente',
                    // Sin default: el detalle se concatena con la pregunta, y el
                    // texto genérico de detalleError() rompería la frase.
                    text: detalleError(err, '') + ' ¿Emitir la orden igual? (el stock quedará en negativo)',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Emitir igual',
                    cancelButtonText: 'Cancelar'
                });
                if (r.isConfirmed) return descargarOrden(id, true);
                return false;
            }
            throw new Error(detalleError(err, "No se pudo generar la orden."));
        }

        _descargarBlobPdf(await resp.blob(), `orden_${id.substring(0,6).toUpperCase()}.pdf`);
        refrescarTablero();
        cargarSelectoresPapel(); // el stock cambió
        return true;
    } catch (error) {
        Swal.fire('No se pudo imprimir la orden', error.message, 'error');
        return false;
    }
}
// Descarga el blob de una respuesta ya OK como PDF, con el nombre indicado.
// Repetido en descargarOrden, registrarEntrega y reimprimirEntrega: son tres
// descargas de PDF con el mismo ritual de <a> temporal.
function _descargarBlobPdf(blob, nombreArchivo) {
    const enlace = document.createElement('a');
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombreArchivo;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    URL.revokeObjectURL(enlace.href);
}

// Modal de entregas parciales de un trabajo: lista los remitos ya emitidos
// (cada uno con su botón para reimprimir sin generar nada nuevo) y, si queda
// saldo, un formulario para registrar una entrega nueva.
async function abrirModalEntregas(id) {
    const trabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const t = trabajos.find(x => x.id === id);
    if (!t) { refrescarTablero(); return; }

    const entregas = t.entregas || [];
    const pendiente = t.cantidad - (t.cantidad_entregada || 0);

    const filasHtml = entregas.length
        ? entregas.map(e => `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid #eee;">
                <span style="font-size:13px;">${esc(e.numero_remito)} · ${e.cantidad}u · ${new Date(e.fecha).toLocaleDateString('es-AR')}</span>
                <button type="button" class="btn btn-mini" onclick="reimprimirEntrega('${e.entrega_id}')">🖨️ Reimprimir</button>
            </div>
        `).join('')
        : '<p style="font-size:13px; color:var(--muted);">Todavía no se registró ninguna entrega.</p>';

    const formHtml = pendiente > 0
        ? `<hr style="margin:10px 0;">
           <label style="font-size:13px; display:block; margin-bottom:4px;">Saldo pendiente: ${pendiente} de ${t.cantidad}</label>
           <input id="swal-cant-entrega" type="number" min="1" step="1" class="swal2-input" value="${pendiente}" placeholder="Cantidad a entregar">`
        : `<hr style="margin:10px 0;"><p style="font-size:13px; color:var(--green);">✔ Entrega completa (${t.cantidad_entregada}/${t.cantidad}).</p>`;

    const { value: cantidad } = await Swal.fire({
        title: 'Entregas / Remitos',
        html: `<div style="text-align:left; max-height:260px; overflow-y:auto;">${filasHtml}</div>${formHtml}`,
        focusConfirm: false,
        showCancelButton: true,
        showConfirmButton: pendiente > 0,
        confirmButtonText: 'Registrar entrega',
        cancelButtonText: pendiente > 0 ? 'Cancelar' : 'Cerrar',
        preConfirm: () => {
            const valor = parseInt(document.getElementById('swal-cant-entrega').value);
            if (!valor || valor <= 0) {
                Swal.showValidationMessage('Ingresá una cantidad mayor a cero.');
                return false;
            }
            return valor;
        }
    });

    if (cantidad) {
        await registrarEntrega(t.cliente_id, id, cantidad);
    }
}

// Registra una entrega de un solo trabajo (el caso simple del botón de la
// tarjeta) y descarga su remito. Por debajo pega al mismo endpoint que la
// entrega combinada de varios trabajos (ver clientes.js/confirmarNuevaEntrega),
// con una lista de un solo ítem. Si supera el saldo pendiente, ofrece forzar
// igual que descargarOrden con el stock.
async function registrarEntrega(clienteId, trabajoId, cantidad, forzar = false) {
    try {
        const url = `${API_URL}/entregas${forzar ? '?forzar=true' : ''}`;
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cliente_id: clienteId, items: [{ trabajo_id: trabajoId, cantidad }] })
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            if (resp.status === 400 && !forzar) {
                const r = await Swal.fire({
                    title: 'Supera el saldo pendiente',
                    text: detalleError(err, '') + ' ¿Registrar igual?',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Registrar igual',
                    cancelButtonText: 'Cancelar'
                });
                if (r.isConfirmed) return registrarEntrega(clienteId, trabajoId, cantidad, true);
                return false;
            }
            throw new Error(detalleError(err, "No se pudo registrar la entrega."));
        }

        _descargarBlobPdf(await resp.blob(), `remito_${trabajoId.substring(0,6).toUpperCase()}.pdf`);
        refrescarTablero();
        return true;
    } catch (error) {
        Swal.fire('No se pudo registrar la entrega', error.message, 'error');
        return false;
    }
}

// Reimprime un remito ya emitido: sin efectos, no crea nada ni cambia
// numeración. entregaId es el REMITO (puede traer más de un trabajo, si se
// combinaron varios en la misma entrega).
async function reimprimirEntrega(entregaId) {
    try {
        const resp = await fetch(`${API_URL}/entregas/${entregaId}/pdf`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "No se pudo reimprimir el remito."));
        }
        _descargarBlobPdf(await resp.blob(), `remito_${entregaId.substring(0,6).toUpperCase()}.pdf`);
    } catch (error) {
        Swal.fire('No se pudo reimprimir', error.message, 'error');
    }
}
async function cargarTrabajos() {
    // El tablero pide sólo lo que va en el tablero (trabajos vivos + entregados
    // recientes): si no, la columna "Entregado" se llena con todo lo que la
    // gráfica entregó desde el primer día. Qué entra lo decide el backend
    // (models.DIAS_ENTREGADO_EN_TABLERO), acá sólo se pide filtrado o completo.
    const verHistorial = document.getElementById('chk-ver-historial')?.checked;

    // Los presupuestos son sólo del dueño (exponen costo y margen), así que para
    // los demás puestos ni se piden: sería un 403. Sin ellos no se puede saber
    // qué trabajo tiene presupuesto, y el distintivo simplemente no se muestra
    // (es información de rentabilidad, que es justo lo que no les toca ver).
    const [trabajos, clientes, presupuestos] = await Promise.all([
        (await fetch(`${API_URL}/trabajos/${verHistorial ? '' : '?solo_tablero=true'}`)).json(),
        (await fetch(`${API_URL}/clientes/`)).json(),
        puedeVerPlata() ? (await fetch(`${API_URL}/presupuestos/`)).json() : []
    ]);

    // Trabajos que ya tienen presupuesto asociado: los demás no aportan ganancia
    // y se marcan en el tablero para que el usuario lo sepa. El vínculo vive en
    // cada ítem del presupuesto (un presupuesto puede generar varios trabajos).
    const trabajosConPresupuesto = new Set(
        presupuestos.flatMap(p => (p.items || []).map(it => it.trabajo_id)).filter(Boolean)
    );

    const cols = {};
    Object.entries(COLUMNAS_KANBAN).forEach(([estado, idColumna]) => {
        cols[estado] = document.getElementById(idColumna);
    });
    Object.values(cols).forEach(col => { if(col) col.innerHTML = col.firstElementChild.outerHTML; });

    // Los cancelados están ocultos por defecto: el tablero es de trabajo activo.
    // El checkbox los trae de vuelta para poder reactivarlos (antes, un trabajo
    // cancelado desaparecía del frontend sin ninguna forma de recuperarlo).
    const verCancelados = document.getElementById('chk-ver-cancelados')?.checked;

    // Los guardamos por id para que los onclick pasen sólo el id: serializar
    // textos en el atributo se rompe con cualquier apóstrofo en la descripción.
    trabajosPorId.clear();
    trabajos.forEach(t => trabajosPorId.set(t.id, t));

    trabajos.forEach(t => {
        const cancelado = t.estado === "Cancelado";
        if (cancelado && !verCancelados) return;

        // Sólo llega acá si se pidió el historial completo: con el tablero
        // normal el backend ni los manda.
        const archivado = !!t.archivado;

        const cliente = clientes.find(c => c.id === t.cliente_id);
        const bordeColor = t.estado === "En Diseño" ? "var(--magenta)" : (t.estado === "En Producción" ? "var(--amber)" : "transparent");
        const shortId = t.id.substring(0,6).toUpperCase();

        const nroOrden = t.numero_orden
            ? `<span style="font-size:10px; color:var(--green); font-weight:600;">🖨️ ${esc(t.numero_orden)}</span>`
            : '';
        // Distintivo: el trabajo no tiene presupuesto asociado (no suma ganancia).
        // Sin la lista de presupuestos (los puestos que no la piden) no hay forma
        // de saberlo, y marcarlos todos como "sin presupuesto" seria mentir.
        const sinPresupuesto = puedeVerPlata() && !trabajosConPresupuesto.has(t.id);
        const badgeSinPresu = sinPresupuesto
            ? `<div style="margin-top:4px;"><span style="font-size:10px; background:#fff3cd; color:#8a6d00; border:1px solid var(--amber); padding:2px 6px; border-radius:4px;">⚠️ Sin presupuesto</span></div>`
            : '';
        const badgeCancelado = cancelado
            ? `<div style="margin-top:4px;"><span style="font-size:10px; background:#f8d7da; color:#842029; border:1px solid var(--red, #C13B3B); padding:2px 6px; border-radius:4px;">✖ Cancelado</span></div>`
            : '';
        // Se está viendo sólo porque está tildado "ver historial completo": sin
        // el distintivo parecería una tarjeta más del tablero.
        const badgeArchivado = archivado
            ? `<div style="margin-top:4px;"><span style="font-size:10px; background:#e9ecef; color:#495057; border:1px solid var(--muted); padding:2px 6px; border-radius:4px;">📦 Fuera del tablero</span></div>`
            : '';
        // Entrega parcial en curso: hay al menos una entrega registrada pero
        // todavía no se completó la cantidad total del trabajo. Sin este aviso
        // no hay forma de saber, mirando el tablero, que falta terminar de
        // entregar algo que ya se empezó a entregar.
        const cantidadEntregada = t.cantidad_entregada || 0;
        const badgeEntregaParcial = (t.entregas && t.entregas.length && cantidadEntregada < t.cantidad)
            ? `<div style="margin-top:4px;"><span style="font-size:10px; background:#d1ecf1; color:#0c5460; border:1px solid var(--blue, #0c5460); padding:2px 6px; border-radius:4px;">📦 Entregado: ${cantidadEntregada}/${t.cantidad}</span></div>`
            : '';

        // Sacar del tablero es sólo para lo que ya terminó: un trabajo en curso
        // que desaparece de la única pantalla donde se lo sigue es un trabajo
        // perdido (el backend valida lo mismo).
        const terminado = t.estado === "Entregado" || cancelado;
        const botonArchivar = !terminado ? '' : (archivado
            ? `<button class="btn btn-mini no-print" onclick="archivarTrabajo('${t.id}', false)">📥 Volver al tablero</button>`
            : `<button class="btn btn-mini no-print" onclick="archivarTrabajo('${t.id}', true)">📦 Quitar del tablero</button>`);

        // El reemplazo del arrastre en el celular. Va con solo-mobile porque en
        // la PC se mueve arrastrando la tarjeta y sería un botón de más en una
        // tarjeta que ya tiene cuatro. Un cancelado no se mueve: se reactiva.
        const botonMover = (cancelado || archivado) ? '' :
            `<button class="btn btn-mini no-print solo-mobile" onclick="abrirMenuMover('${t.id}')">↔️ Mover a...</button>`;

        // Un trabajo cancelado no se arrastra ni se reimprime: sólo se reactiva.
        const acciones = cancelado
            ? `<button class="btn btn-mini no-print" onclick="reactivarTrabajo('${t.id}')">↩️ Reactivar</button>${botonArchivar}`
            : `${botonMover}
              <button class="btn btn-mini no-print" onclick="descargarOrden('${t.id}')">
                ${t.orden_impresa ? '🖨️ Reimprimir orden' : '🖨️ Imprimir orden'}
              </button>
              <button class="btn btn-mini no-print" onclick="abrirModalEntregas('${t.id}')">
                ${(t.entregas && t.entregas.length) ? '📦 Entregas / Remitos' : '🖨️ Registrar entrega'}
              </button>
              <button class="btn btn-mini no-print" onclick="cancelarTrabajo('${t.id}')">✖ Cancelar</button>${botonArchivar}`;

        // El archivado tampoco se arrastra: ya no está en el tablero, y moverlo
        // de columna sería cambiarle el estado a algo que nadie está mirando.
        const inmovil = cancelado || archivado;

        const tarjetaHTML = `
            <div class="kanban-card" id="card-${t.id}" data-cliente="${t.cliente_id}" ${inmovil ? '' : `draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')"`} style="border-left: 4px solid ${bordeColor}; cursor: ${inmovil ? 'default' : 'grab'}; ${inmovil ? 'opacity:.6;' : ''}">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                <span style="font-size:10px; color:var(--muted);">#${shortId}</span>
                ${nroOrden}
              </div>
              ${badgeCancelado}
              ${badgeArchivado}
              ${badgeSinPresu}
              ${badgeEntregaParcial}
              <div class="client">${cliente ? esc(cliente.nombre_completo) : 'Desconocido'}</div>
              <div class="job">${t.cantidad}x ${esc(t.descripcion_producto)}</div>
              <div class="date">${t.fecha_creacion}${puedeVerPlata() ? ` - $${fmtMoney(t.precio_venta)}` : ''}</div>
              ${acciones}
            </div>
        `;

        // Los cancelados no tienen columna propia: se muestran en la primera.
        const columna = cancelado ? cols["Aprobado"] : (cols[t.estado] || cols["Aprobado"]);
        if (columna) columna.innerHTML += tarjetaHTML;
    });
}

// Cancelar un trabajo. Si la orden ya se imprimió, descontó pliegos del stock:
// preguntamos si devolverlos. El backend es idempotente (flag papel_devuelto),
// así que cancelar dos veces nunca duplica el reingreso.
async function cancelarTrabajo(id) {
    const t = trabajosPorId.get(id);
    if (!t) return;

    const confirmacion = await Swal.fire({
        title: '¿Cancelar el trabajo?',
        text: 'Deja de contar para facturación y sale del tablero. Podés reactivarlo después.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, cancelar',
        cancelButtonText: 'No'
    });
    if (!confirmacion.isConfirmed) return;

    let devolverPapel = false;
    const tienePapelDescontado = t.orden_impresa && t.papel_id && Number(t.cantidad_pliegos) > 0 && !t.papel_devuelto;
    if (tienePapelDescontado) {
        const decision = await Swal.fire({
            title: '¿Devolver el papel al stock?',
            text: `La orden descontó ${t.cantidad_pliegos} pliegos. Si el papel no se usó, podés reingresarlos.`,
            icon: 'question',
            showDenyButton: true,
            showCancelButton: true,
            confirmButtonText: 'Sí, devolver',
            denyButtonText: 'No, ya se usó',
            cancelButtonText: 'Volver'
        });
        if (decision.isDismissed) return; // "Volver": no cancelamos nada.
        devolverPapel = decision.isConfirmed;
    }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}?devolver_papel=${devolverPapel}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: "Cancelado" })
        });
        if (!resp.ok) {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo cancelar', detalleError(error), 'error');
            return;
        }
        cargarTrabajos();
        if (devolverPapel) cargarStock();
        Swal.fire({
            title: 'Trabajo cancelado',
            text: devolverPapel ? `Se devolvieron ${t.cantidad_pliegos} pliegos al stock.` : '',
            icon: 'success',
            timer: 2000,
            showConfirmButton: false
        });
    } catch (error) {
        console.error('Error al cancelar el trabajo:', error);
        Swal.fire('Error de conexión', 'No se pudo cancelar el trabajo.', 'error');
    }
}

// Vuelve un trabajo cancelado a Aprobado. El papel devuelto NO se vuelve a
// descontar: orden_impresa sigue en true y el guard de imprimir-orden no
// redescuenta, así que hay que ajustar el stock a mano si se reimprime.
async function reactivarTrabajo(id) {
    const confirmacion = await Swal.fire({
        title: '¿Reactivar el trabajo?',
        text: 'Vuelve al tablero en estado Aprobado.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, reactivar',
        cancelButtonText: 'No'
    });
    if (!confirmacion.isConfirmed) return;

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: "Aprobado" })
        });
        if (!resp.ok) {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo reactivar', detalleError(error), 'error');
            return;
        }
        cargarTrabajos();
    } catch (error) {
        console.error('Error al reactivar el trabajo:', error);
        Swal.fire('Error de conexión', 'No se pudo reactivar el trabajo.', 'error');
    }
}

// Saca del tablero un trabajo terminado (o lo devuelve, con archivar=false).
// No cambia el estado ni la plata: el trabajo queda igual, sólo deja de ocupar
// lugar en el Kanban. Los entregados salen solos a los 15 días; esto es para el
// que se quiere sacar antes.
async function archivarTrabajo(id, archivar) {
    const confirmacion = await Swal.fire({
        title: archivar ? '¿Quitar del tablero?' : '¿Volver al tablero?',
        text: archivar
            ? 'El trabajo no se borra ni se modifica: sale del Kanban y queda en la ficha del cliente.'
            : 'Vuelve a verse en el tablero, si fue entregado en los últimos 15 días.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: archivar ? 'Sí, quitar' : 'Sí, volver',
        cancelButtonText: 'No'
    });
    if (!confirmacion.isConfirmed) return;

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}/archivar?archivado=${archivar}`, { method: 'POST' });
        if (!resp.ok) {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo hacer', detalleError(error), 'error');
            return;
        }
        cargarTrabajos();
    } catch (error) {
        console.error('Error al archivar el trabajo:', error);
        Swal.fire('Error de conexión', 'No se pudo actualizar el trabajo.', 'error');
    }
}

// PDFs y Extras
function abrirWhatsApp(telefono) {
    const num = telefono.replace(/\D/g, '');
    window.open(`https://wa.me/549${num}?text=¡Hola!`, '_blank');
}

function descargarMovimientosPDF() {
    const elemento = document.getElementById('tabla-movimientos');
    html2pdf().set({ margin: 10, filename: 'Historial_Movimientos.pdf' }).from(elemento).save();
}

// Hoja de Ruta: lo que el taller tiene para hacer HOY (En Diseño + En
// Producción, sin precio ni costo). Antes esto capturaba una foto del Kanban
// completo con html2pdf/html2canvas: salía como imagen, cortaba columnas al
// cambiar de página y mezclaba etapas (Aprobado, Entregado) que un técnico no
// necesita ver en la hoja del día. Ahora el PDF se arma en el backend con
// ReportLab, mismo patrón que generarPDFCliente/generarPDFInterno.
async function generarInformeDiarioPDF() {
    try {
        const resp = await fetch(`${API_URL}/trabajos/informe-diario/pdf`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, 'No se pudo generar la hoja de ruta.'));
        }

        const dispo = resp.headers.get('Content-Disposition') || '';
        const match = dispo.match(/filename="?([^"]+)"?/);
        const nombreArchivo = match ? match[1] : 'Hoja_de_Ruta.pdf';

        const blob = await resp.blob();
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(blob);
        enlace.download = nombreArchivo;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        URL.revokeObjectURL(enlace.href);
    } catch (error) {
        console.error('Error generando la hoja de ruta:', error);
        Swal.fire('No se pudo generar la hoja de ruta', error.message, 'error');
    }
}

