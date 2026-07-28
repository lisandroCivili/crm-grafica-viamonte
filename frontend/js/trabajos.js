// Trabajos: alta, edicion, tablero Kanban y ordenes de produccion.

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
    const id = ev.dataTransfer.getData("text");

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
        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "El backend rechazó el cambio de estado."));
        }
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo mover el trabajo', error.message, 'error');
        refrescarTablero();
    }
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

        const blob = await resp.blob();
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(blob);
        enlace.download = `orden_${id.substring(0,6).toUpperCase()}.pdf`;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        URL.revokeObjectURL(enlace.href);

        refrescarTablero();
        cargarSelectoresPapel(); // el stock cambió
        return true;
    } catch (error) {
        Swal.fire('No se pudo imprimir la orden', error.message, 'error');
        return false;
    }
}
// Descarga el remito (orden de entrega) del trabajo. Mismo patrón que
// descargarOrden: la numeración es idempotente en el backend, reimprimir no
// genera un número nuevo ni repite ningún efecto (a diferencia de la orden,
// el remito no toca stock).
async function descargarRemito(id) {
    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}/orden-entrega`, { method: 'POST' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(detalleError(err, "No se pudo generar el remito."));
        }

        const blob = await resp.blob();
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(blob);
        enlace.download = `remito_${id.substring(0,6).toUpperCase()}.pdf`;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        URL.revokeObjectURL(enlace.href);

        refrescarTablero();
        return true;
    } catch (error) {
        Swal.fire('No se pudo imprimir el remito', error.message, 'error');
        return false;
    }
}
async function cargarTrabajos() {
    // Los presupuestos son sólo del dueño (exponen costo y margen), así que para
    // los demás puestos ni se piden: sería un 403. Sin ellos no se puede saber
    // qué trabajo tiene presupuesto, y el distintivo simplemente no se muestra
    // (es información de rentabilidad, que es justo lo que no les toca ver).
    const [trabajos, clientes, presupuestos] = await Promise.all([
        (await fetch(`${API_URL}/trabajos/`)).json(),
        (await fetch(`${API_URL}/clientes/`)).json(),
        puedeVerPlata() ? (await fetch(`${API_URL}/presupuestos/`)).json() : []
    ]);

    // Trabajos que ya tienen presupuesto asociado: los demás no aportan ganancia
    // y se marcan en el tablero para que el usuario lo sepa. El vínculo vive en
    // cada ítem del presupuesto (un presupuesto puede generar varios trabajos).
    const trabajosConPresupuesto = new Set(
        presupuestos.flatMap(p => (p.items || []).map(it => it.trabajo_id)).filter(Boolean)
    );

    const cols = {
        "Aprobado": document.getElementById('col-pendiente'),
        "En Diseño": document.getElementById('col-diseno'),
        "En Producción": document.getElementById('col-produccion'),
        "Entregado": document.getElementById('col-entregado')
    };
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
        // Un trabajo cancelado no se arrastra ni se reimprime: sólo se reactiva.
        const acciones = cancelado
            ? `<button class="btn no-print" style="margin-top:8px; padding:4px 8px; font-size:11px;" onclick="reactivarTrabajo('${t.id}')">↩️ Reactivar</button>`
            : `<button class="btn no-print" style="margin-top:8px; padding:4px 8px; font-size:11px;" onclick="descargarOrden('${t.id}')">
                ${t.orden_impresa ? '🖨️ Reimprimir orden' : '🖨️ Imprimir orden'}
              </button>
              <button class="btn no-print" style="margin-top:8px; padding:4px 8px; font-size:11px;" onclick="descargarRemito('${t.id}')">
                ${t.remito_impreso ? '🖨️ Reimprimir Remito' : '🖨️ Imprimir Remito'}
              </button>
              <button class="btn no-print" style="margin-top:8px; padding:4px 8px; font-size:11px;" onclick="cancelarTrabajo('${t.id}')">✖ Cancelar</button>`;

        const tarjetaHTML = `
            <div class="kanban-card" id="card-${t.id}" data-cliente="${t.cliente_id}" ${cancelado ? '' : `draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')"`} style="border-left: 4px solid ${bordeColor}; cursor: ${cancelado ? 'default' : 'grab'}; ${cancelado ? 'opacity:.6;' : ''}">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                <span style="font-size:10px; color:var(--muted);">#${shortId}</span>
                ${nroOrden}
              </div>
              ${badgeCancelado}
              ${badgeSinPresu}
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

// PDFs y Extras
function abrirWhatsApp(telefono) {
    const num = telefono.replace(/\D/g, '');
    window.open(`https://wa.me/549${num}?text=¡Hola!`, '_blank');
}

function descargarMovimientosPDF() {
    const elemento = document.getElementById('tabla-movimientos');
    html2pdf().set({ margin: 10, filename: 'Historial_Movimientos.pdf' }).from(elemento).save();
}

async function generarInformeDiarioPDF() {
    const board = document.querySelector('.kanban-board');
    // Ocultamos los botones de acción sólo durante la captura: no van en la hoja de ruta.
    board.classList.add('ocultar-acciones');
    try {
        await html2pdf().set({ margin: 10, filename: 'Hoja_Ruta.pdf', orientation: 'landscape' }).from(board).save();
    } finally {
        board.classList.remove('ocultar-acciones');
    }
}

