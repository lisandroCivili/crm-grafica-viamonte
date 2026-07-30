// Clientes: ficha de cuenta corriente y ABM del listado.

// ==========================================
// FICHA DINÁMICA (El núcleo contable)
// ==========================================
async function abrirFicha(id) {
    clienteActualFicha = id;
    toggleDrawer('drawer-cliente');
    document.getElementById('ficha-nombre').innerText = "Cargando datos...";
    
    switchFichaTab('trabajos');

    try {
        // La cuenta corriente (movimientos y saldo) es sólo del dueño, así que
        // para los demás puestos ni se pide: serían dos 403. Ojo que sin esos
        // datos NO se puede mostrar cuánto debe cada trabajo — más abajo se
        // omite en vez de calcularlo en cero, que diría "Pagado 100%" sobre
        // trabajos que en realidad deben plata.
        const verPlata = puedeVerPlata();

        const [respC, respT, respM, respN, respS] = await Promise.all([
            fetch(`${API_URL}/clientes/`),
            fetch(`${API_URL}/trabajos/`),
            verPlata ? fetch(`${API_URL}/movimientos/${id}`) : null,
            fetch(`${API_URL}/notas/${id}`),
            verPlata ? fetch(`${API_URL}/movimientos/saldo/${id}`) : null
        ]);

        const clientes = await respC.json();
        const todosTrabajos = await respT.json();
        const movimientos = respM?.ok ? await respM.json() : [];
        const notas = respN.ok ? await respN.json() : [];
        const saldoInfo = respS?.ok ? await respS.json() : null;
        
        const cliente = clientes.find(c => c.id === id);
        const trabajos = todosTrabajos.filter(t => t.cliente_id === id);
        
        if (!cliente) return;

        document.getElementById('ficha-nombre').innerText = cliente.nombre_completo;
        document.getElementById('ficha-cuit').innerText = `DNI/CUIT: ${cliente.dni_cuit} | Tel: ${cliente.telefono}`;

        // El saldo lo calcula el backend (Decimal) para no re-acumular error de float en el browser.
        const saldoReal = saldoInfo ? Number(saldoInfo.saldo) : 0;

        const vistaSaldo = saldoMostrable(saldoReal);
        const lblSaldo = document.getElementById('ficha-saldo');
        lblSaldo.innerText = vistaSaldo.monto;
        lblSaldo.style.color = vistaSaldo.color;
        document.getElementById('ficha-saldo-aclaracion').innerText = vistaSaldo.aclaracion;

        const divTrabajos = document.getElementById('lista-trabajos-cliente');
        divTrabajos.innerHTML = trabajos.length === 0 ? '<p style="text-align:center; color:var(--muted);">Sin historial de trabajos.</p>' : '';
        
        trabajos.reverse().forEach(t => {
            const shortId = t.id.substring(0,6).toUpperCase();
            const pagosDeEsteTrabajo = movimientos
                .filter(m => m.tipo === 'Pago' && m.trabajo_id === t.id)
                .reduce((suma, m) => suma + Number(m.monto), 0);

            const saldoTrabajo = Number(t.precio_venta) - pagosDeEsteTrabajo;
            // Sin cuenta corriente no hay nada honesto para decir acá: el precio
            // viene en null y los pagos no se pidieron, así que la cuenta daría
            // "Pagado 100%" sobre cualquier trabajo.
            const textoPago = !verPlata
                ? ''
                : (saldoTrabajo <= 0
                    ? '<span style="color:var(--green); font-weight:600;">Pagado 100%</span>'
                    : `<span style="color:var(--red); font-weight:600;">Debe: $${fmtMoney(saldoTrabajo)}</span> <span style="font-size:11px; color:var(--muted);">(Abonó: $${fmtMoney(pagosDeEsteTrabajo)})</span>`);

            // El trabajo debe plata y el cliente tiene saldo a favor (saldo < 0):
            // se ofrece cubrirlo con ese crédito sin cargar un pago nuevo.
            const puedeAplicarSaldoFavor = verPlata && saldoTrabajo > 0 && saldoReal < 0
                && t.estado !== 'Cancelado';
            const btnSaldoFavor = puedeAplicarSaldoFavor
                ? `<button class="btn secondary" style="margin-top:12px; margin-left:8px; font-size:12px; border-color:var(--green); color:var(--green);" onclick="aplicarSaldoFavor('${t.id}')">💰 Aplicar saldo a favor</button>`
                : '';

            divTrabajos.innerHTML += `
                <div class="accordion-item">
                    <div class="accordion-header" onclick="toggleAccordion(this)">
                        <span>#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</span>
                        <span style="color:var(--magenta)">${verPlata ? `$${fmtMoney(t.precio_venta)} ` : ''}▾</span>
                    </div>
                    <div class="accordion-body">
                        <p style="margin:0 0 8px 0; display:flex; justify-content:space-between;">
                            <span><b>Estado:</b> ${t.estado}</span>
                            <span>${textoPago}</span>
                        </p>
                        <p style="margin:0 0 8px 0;"><b>Fecha de ingreso:</b> ${t.fecha_creacion}</p>
                        <p style="margin:0 0 8px 0;"><b>Fecha de comienzo:</b> ${t.fecha_comienzo || '-'}</p>
                        <p style="margin:0 0 8px 0;"><b>Notas iniciales:</b> ${esc(t.notas_iniciales) || 'Ninguna'}</p>
                        <button class="btn secondary" style="margin-top:12px; font-size:12px;" onclick="abrirModalEditarTrabajo('${t.id}')">✏️ Editar Trabajo</button>
                        ${permisos().borrar ? `<button class="btn secondary" style="margin-top:12px; margin-left:8px; font-size:12px; border-color:var(--red); color:var(--red);" onclick="eliminarTrabajo('${t.id}', this)">🗑️ Borrar</button>` : ''}
                        ${btnSaldoFavor}
                    </div>
                </div>
            `;
        });

        const tbodyMovimientos = document.querySelector('#tabla-movimientos tbody');
        tbodyMovimientos.innerHTML = '';
        movimientos.forEach(m => {
            const colorMonto = m.tipo === 'Pago' ? 'var(--green)' : 'var(--ink)';
            const signo = m.tipo === 'Pago' ? '+' : '';
            tbodyMovimientos.innerHTML += `
                <tr>
                    <td>${new Date(m.fecha).toLocaleDateString('es-AR')}</td>
                    <td>${esc(m.descripcion)} <br><small style="color:var(--muted);">${esc(m.metodo || m.tipo)}</small></td>
                    <td class="tnum" style="color:${colorMonto}; font-weight:600;">${signo}$${fmtMoney(m.monto)}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:11px; padding:4px 6px;" onclick="editarMovimiento('${m.id}')">✏️</button>
                        <button class="btn secondary" style="font-size:11px; padding:4px 6px; border-color:var(--red); color:var(--red);" onclick="eliminarMovimiento('${m.id}')">🗑️</button>
                    </td>
                </tr>
            `;
        });

        const divNotas = document.getElementById('lista-notas-cliente');
        divNotas.innerHTML = '';
        notas.forEach(n => {
            divNotas.innerHTML += `
                <div class="nota-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
                        <div class="nota-fecha">${new Date(n.fecha_creacion).toLocaleString('es-AR')}</div>
                        <div style="flex-shrink:0;">
                            <button class="btn secondary" style="font-size:10px; padding:2px 6px;" onclick="editarNota('${n.id}')">✏️</button>
                            <button class="btn secondary" style="font-size:10px; padding:2px 6px; border-color:var(--red); color:var(--red);" onclick="eliminarNota('${n.id}')">🗑️</button>
                        </div>
                    </div>
                    <div>${n.texto}</div>
                </div>
            `;
        });

    } catch (error) {
        console.error("Error al cargar la ficha:", error);
    }
}

// Cubre el saldo pendiente de un trabajo con el saldo a favor del cliente. El
// backend re-imputa los pagos existentes (no crea plata): ver routers/trabajos.py.
async function aplicarSaldoFavor(id) {
    const confirma = await Swal.fire({
        title: 'Aplicar saldo a favor',
        text: 'Se usará el saldo a favor del cliente para cubrir este trabajo. ¿Confirmás?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Aplicar',
        cancelButtonText: 'Cancelar'
    });
    if (!confirma.isConfirmed) return;

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}/aplicar-saldo-favor`, { method: 'POST' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(detalleError(data, 'No se pudo aplicar el saldo a favor.'));

        const restante = Number(data.saldo_pendiente_restante);
        await Swal.fire(
            'Saldo aplicado',
            `Se aplicaron $${fmtMoney(data.monto_aplicado)} al trabajo.` +
            (restante > 0
                ? ` Todavía debe $${fmtMoney(restante)}.`
                : ' El trabajo quedó pago.'),
            'success'
        );
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo aplicar el saldo a favor', error.message, 'error');
    }
}

// Arma un remito que puede combinar varios trabajos del mismo cliente (ej: el
// cliente retira parte de dos pedidos distintos en la misma visita). El botón
// "🖨️ Registrar entrega" de la tarjeta del Kanban (trabajos.js) sigue
// sirviendo para el caso simple de un solo trabajo, y pega al mismo endpoint
// por debajo con un solo ítem.
async function abrirNuevaEntrega(clienteId) {
    if (!clienteId) return;

    const todosTrabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const pendientes = todosTrabajos.filter(t =>
        t.cliente_id === clienteId && t.estado !== 'Cancelado' &&
        (t.cantidad - (t.cantidad_entregada || 0)) > 0
    );

    if (pendientes.length === 0) {
        Swal.fire('Nada para entregar', 'Este cliente no tiene trabajos con saldo pendiente de entrega.', 'info');
        return;
    }

    const filasHtml = pendientes.map(t => {
        const pendiente = t.cantidad - (t.cantidad_entregada || 0);
        return `
            <div style="display:flex; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid #eee;">
                <input type="checkbox" class="chk-entrega-trabajo" data-trabajo-id="${t.id}">
                <span style="flex:1; font-size:13px;">${esc(t.descripcion_producto)} <small style="color:var(--muted);">(pendiente: ${pendiente}/${t.cantidad})</small></span>
                <input type="number" class="swal2-input inp-cant-entrega" data-trabajo-id="${t.id}" min="1" step="1" max="${pendiente}" value="${pendiente}" style="width:70px; margin:0; padding:4px;" disabled>
            </div>
        `;
    }).join('');

    const { value: items } = await Swal.fire({
        title: 'Nueva entrega',
        html: `<div style="text-align:left; max-height:320px; overflow-y:auto;">${filasHtml}</div>`,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Emitir remito',
        cancelButtonText: 'Cancelar',
        didOpen: () => {
            // El input de cantidad sólo se habilita para lo que se tilda: un
            // trabajo sin tildar no debería poder mandar cantidad igual.
            document.querySelectorAll('.chk-entrega-trabajo').forEach(chk => {
                chk.addEventListener('change', () => {
                    document.querySelector(`.inp-cant-entrega[data-trabajo-id="${chk.dataset.trabajoId}"]`).disabled = !chk.checked;
                });
            });
        },
        preConfirm: () => {
            const items = [];
            let error = null;
            document.querySelectorAll('.chk-entrega-trabajo:checked').forEach(chk => {
                const trabajoId = chk.dataset.trabajoId;
                const cantidad = parseInt(document.querySelector(`.inp-cant-entrega[data-trabajo-id="${trabajoId}"]`).value);
                if (!cantidad || cantidad <= 0) error = 'Ingresá una cantidad válida para cada trabajo tildado.';
                items.push({ trabajo_id: trabajoId, cantidad });
            });
            if (error) { Swal.showValidationMessage(error); return false; }
            if (items.length === 0) { Swal.showValidationMessage('Tildá al menos un trabajo.'); return false; }
            return items;
        }
    });

    if (items) {
        await confirmarNuevaEntrega(clienteId, items);
    }
}

// Registra el remito combinado armado en abrirNuevaEntrega. Mismo patrón de
// reintento con forzar que registrarEntrega en trabajos.js (el caso simple de
// un solo ítem): mismo endpoint, una lista más larga.
async function confirmarNuevaEntrega(clienteId, items, forzar = false) {
    try {
        const url = `${API_URL}/entregas${forzar ? '?forzar=true' : ''}`;
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cliente_id: clienteId, items })
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
                if (r.isConfirmed) return confirmarNuevaEntrega(clienteId, items, true);
                return;
            }
            throw new Error(detalleError(err, "No se pudo registrar la entrega."));
        }

        _descargarBlobPdf(await resp.blob(), `remito_${clienteId.substring(0,6).toUpperCase()}.pdf`);
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo registrar la entrega', error.message, 'error');
    }
}

// ==========================================
// CARGA DE TABLAS Y LISTADO DE CLIENTES
// ==========================================

async function cargarClientes(filtro = "") {
    try {
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        // El saldo lo calcula el backend (mismo cálculo que la ficha, cheques
        // incluidos). Es sólo del dueño: sumando esa respuesta sale la
        // facturación histórica de la gráfica, así que a los demás puestos ni
        // se les pide (la columna tampoco se les muestra).
        const verPlata = puedeVerPlata();

        const [respC, respS] = await Promise.all([
            fetch(url),
            verPlata ? fetch(`${API_URL}/clientes/saldos`) : null
        ]);

        const clientes = await respC.json();
        const saldos = respS?.ok ? await respS.json() : [];

        const saldoPorCliente = {};
        saldos.forEach(s => saldoPorCliente[s.cliente_id] = Number(s.saldo)); // Decimal llega como string

        const tbody = document.querySelector('#tableClientes tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        clientes.forEach(cliente => {
            const vistaSaldo = saldoMostrable(saldoPorCliente[cliente.id] ?? 0);

            tbody.innerHTML += `
                <tr class="client-row">
                  <td><b>${esc(cliente.nombre_completo)}</b></td>
                  <td>${cliente.nombre_empresa || '-'}</td>
                  <td class="tnum">${cliente.dni_cuit}</td>
                  ${verPlata ? `<td class="tnum" style="color: ${vistaSaldo.color}; font-weight: 600;">
                    ${vistaSaldo.monto}
                    ${vistaSaldo.aclaracion ? `<div style="font-size:11px; font-weight:500;">${vistaSaldo.aclaracion}</div>` : ''}
                  </td>` : ''}
                  <td>
                    <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                    <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
                    <button class="btn secondary" style="font-size:12px; padding:6px; margin-left:4px;" onclick="abrirModalEditarCliente('${cliente.id}')">✏️</button>
                    ${permisos().borrar ? `<button class="btn secondary" style="font-size:12px; padding:6px; margin-left:4px; border-color:var(--red); color:var(--red);" onclick="eliminarCliente('${cliente.id}', this)">🗑️</button>` : ''}
                  </td>
                </tr>
            `;
        });
    } catch (e) { console.error("Error cargando clientes:", e); }
}

document.getElementById('clientSearch')?.addEventListener('keyup', (e) => {
    cargarClientes(e.target.value);
});

// Guardar cliente nuevo
async function guardarCliente(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const data = {
        nombre_completo: document.getElementById('fc_nombre').value,
        nombre_empresa: document.getElementById('fc_empresa').value || null,
        dni_cuit: document.getElementById('fc_cuit').value,
        telefono: document.getElementById('fc_telefono').value,
        frecuencia_recompra_dias: document.getElementById('fc_recompra').value ? parseInt(document.getElementById('fc_recompra').value) : null
    };
    try {
        const resp = await fetch(`${API_URL}/clientes/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (!resp.ok) {
            // Antes se reseteaba el form y se cerraba el drawer aunque el backend
            // hubiera rechazado los datos: el cliente nunca se guardaba y nadie avisaba.
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar', detalleError(error), 'error');
            return;
        }
        document.getElementById('form-cliente').reset();
        toggleDrawer('drawer-nuevo-cliente');
        cargarClientes();
    } catch (error) {
        console.error("Error al guardar cliente:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar el cliente.', 'error');
    } finally {
        restore();
    }
}

// Abrir el drawer de edición con los datos actuales del cliente
async function abrirModalEditarCliente(id) {
    try {
        const resp = await fetch(`${API_URL}/clientes/`);
        const clientes = await resp.json();
        const cliente = clientes.find(c => c.id === id);
        if (!cliente) return;

        document.getElementById('fec_id').value = cliente.id;
        document.getElementById('fec_nombre').value = cliente.nombre_completo;
        document.getElementById('fec_empresa').value = cliente.nombre_empresa || '';
        document.getElementById('fec_cuit').value = cliente.dni_cuit;
        document.getElementById('fec_telefono').value = cliente.telefono;
        document.getElementById('fec_recompra').value = cliente.frecuencia_recompra_dias || '';

        toggleDrawer('drawer-editar-cliente');
    } catch (e) { console.error("Error al abrir edición de cliente:", e); }
}

async function guardarEdicionCliente(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const id = document.getElementById('fec_id').value;
    const data = {
        nombre_completo: document.getElementById('fec_nombre').value,
        nombre_empresa: document.getElementById('fec_empresa').value || null,
        dni_cuit: document.getElementById('fec_cuit').value,
        telefono: document.getElementById('fec_telefono').value,
        frecuencia_recompra_dias: document.getElementById('fec_recompra').value ? parseInt(document.getElementById('fec_recompra').value) : null
    };
    try {
        const resp = await fetch(`${API_URL}/clientes/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (resp.ok) {
            toggleDrawer('drawer-editar-cliente');
            cargarClientes();
            Swal.fire({ title: 'Cliente actualizado', icon: 'success', timer: 1000, showConfirmButton: false });
        } else {
            const err = await resp.json();
            Swal.fire('No se pudo guardar', detalleError(err, 'Error desconocido'), 'error');
        }
    } finally {
        restore();
    }
}

async function eliminarCliente(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este cliente?',
        text: "Esta acción no se puede deshacer.",
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
        button.innerText = '...';
    }

    try {
        const resp = await fetch(`${API_URL}/clientes/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            cargarClientes();
            Swal.fire('¡Eliminado!', 'El cliente fue borrado del sistema.', 'success');
        } else {
            const err = await resp.json();
            Swal.fire('No se pudo eliminar', detalleError(err, 'Error desconocido'), 'error');
        }
    } catch (e) {
        console.error("Error al eliminar cliente:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// Guardar trabajo nuevo
