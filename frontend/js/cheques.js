// Cheques: alta, cambios de estado e historial.

// ==========================================
// MÓDULO DE CHEQUES
// ==========================================

let idChequeEditando = null;

// Estados en los que el cheque ya impactó la caja: salir de ellos exige motivo.
const ESTADOS_FINALES_CHEQUE = ['Cobrado', 'Endosado', 'Rechazado'];

// El backend rechaza transiciones inválidas y ediciones sobre cheques cobrados:
// sin esto los errores pasarían en silencio y el usuario creería que guardó.
async function mostrarErrorCheque(resp, titulo) {
    let data = {};
    try {
        data = await resp.json();
    } catch (e) { /* respuesta sin cuerpo JSON */ }
    await Swal.fire(titulo, detalleError(data, 'Ocurrió un error inesperado.'), 'warning');
}

async function abrirDrawerCheque() {
    idChequeEditando = null;
    document.getElementById('titulo-drawer-cheque').innerText = 'Ingresar Nuevo Cheque';
    document.getElementById('form-cheque').reset();
    document.getElementById('fch_emision').value = fechaHoyLocal();

    // Cargar clientes en el select
    try {
        const resp = await fetch(`${API_URL}/clientes/`);
        if (resp.ok) {
            const clientes = await resp.json();
            const select = document.getElementById('fch_cliente');
            select.innerHTML = '<option value="">Seleccionar Cliente...</option>';
            clientes.forEach(c => {
                select.innerHTML += `<option value="${c.id}">${c.nombre_completo || c.nombre || 'Sin nombre'}</option>`;
            });
        }
    } catch(e) { console.error(e); }

    // El form arranca como cheque Recibido; ajusta el campo de cliente.
    document.getElementById('fch_clasificacion').value = 'Recibido';
    onClasificacionChequeChange();
    await cargarTrabajosDeChequeCliente();

    toggleDrawer('drawer-nuevo-cheque');
}

// Recibido: el cliente emisor es relevante. Emitido: es un pago a proveedor,
// no hay cliente asociado, así que se ocultan cliente y trabajo.
function onClasificacionChequeChange() {
    const esEmitido = document.getElementById('fch_clasificacion').value === 'Emitido';
    const grupoCliente = document.getElementById('fch_cliente').closest('.form-group');
    if (grupoCliente) grupoCliente.style.display = esEmitido ? 'none' : '';
    const grupoTrabajo = document.getElementById('fch_trabajo_id').closest('.form-group');
    if (grupoTrabajo) grupoTrabajo.style.display = esEmitido ? 'none' : '';
    // El emitido va a un proveedor: ese dato identifica al cheque en la tabla
    // y precarga el gasto que representa la salida de plata.
    const grupoDest = document.getElementById('grupo-fch-destinatario');
    if (grupoDest) grupoDest.style.display = esEmitido ? '' : 'none';
    if (esEmitido) {
        document.getElementById('fch_cliente').value = '';
        document.getElementById('fch_trabajo_id').value = '';
    } else {
        document.getElementById('fch_destinatario').value = '';
    }
}

// Sólo tiene sentido imputar el cheque a un trabajo del cliente que lo emitió,
// así que el selector se filtra por el cliente elegido (igual que el drawer de Pago).
async function cargarTrabajosDeChequeCliente() {
    const select = document.getElementById('fch_trabajo_id');
    if (!select) return;
    const clienteId = document.getElementById('fch_cliente').value;
    select.innerHTML = '<option value="">Sin imputar a un trabajo</option>';
    if (!clienteId) return;

    try {
        const resp = await fetch(`${API_URL}/trabajos/`);
        if (!resp.ok) return;
        const trabajos = await resp.json();
        trabajos.filter(t => t.cliente_id === clienteId).forEach(t => {
            const shortId = t.id.substring(0, 6).toUpperCase();
            select.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)} (Total: $${fmtMoney(t.precio_venta)})</option>`;
        });
    } catch (e) { console.error("Error cargando trabajos del cliente:", e); }
}

async function editarCheque(id) {
    try {
        const resp = await fetch(`${API_URL}/cheques/`);
        const cheques = await resp.json();
        const ch = cheques.find(c => c.id === id);
        if (!ch) return;

        await abrirDrawerCheque(); // Prepara el drawer (llena el select de clientes y resetea)
        idChequeEditando = id;
        document.getElementById('titulo-drawer-cheque').innerText = 'Editar Cheque';

        document.getElementById('fch_clasificacion').value = ch.clasificacion || 'Recibido';
        onClasificacionChequeChange();
        document.getElementById('fch_cliente').value = ch.cliente_id || '';
        // Los trabajos dependen del cliente: hay que llenarlos antes de poder seleccionar.
        await cargarTrabajosDeChequeCliente();
        document.getElementById('fch_trabajo_id').value = ch.trabajo_id || '';
        document.getElementById('fch_destinatario').value = ch.destinatario_endoso || '';
        document.getElementById('fch_banco').value = ch.banco;
        document.getElementById('fch_numero').value = ch.numero;
        document.getElementById('fch_monto').value = ch.monto;
        document.getElementById('fch_emision').value = ch.fecha_emision;
        document.getElementById('fch_cobro').value = ch.fecha_cobro;
    } catch (e) { console.error("Error al abrir edición de cheque:", e); }
}

async function cargarCheques() {
    try {
        const [respC, respCl] = await Promise.all([
            fetch(`${API_URL}/cheques/`),
            fetch(`${API_URL}/clientes/`)
        ]);
        
        if (!respC.ok) return;
        const cheques = await respC.json();
        const clientes = await respCl.json();
        
        const tbody = document.querySelector('#tableCheques tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (cheques.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--muted);">No hay cheques registrados.</td></tr>';
            return;
        }

        cheques.forEach(ch => {
            const esRecibido = (ch.clasificacion || 'Recibido') === 'Recibido';
            const cliente = clientes.find(c => c.id === ch.cliente_id);
            // Recibido: nombre del cliente emisor. Emitido: a quién se le entregó.
            const nombreParte = esRecibido
                ? (cliente ? (cliente.nombre_completo || cliente.nombre || 'Desconocido') : 'Desconocido')
                : (ch.destinatario_endoso || 'Proveedor');

            const badgeTipo = esRecibido
                ? `<span style="background:var(--green); color:white; padding:3px 7px; border-radius:4px; font-size:10px; font-weight:bold;">↓ Recibido</span>`
                : `<span style="background:var(--red); color:white; padding:3px 7px; border-radius:4px; font-size:10px; font-weight:bold;">↑ Emitido</span>`;

            // Colores por estado
            let badgeEstado = '';
            if (ch.estado === 'En Cartera') badgeEstado = `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 En Cartera</span>`;
            else if (ch.estado === 'Depositado') badgeEstado = `<span style="background:var(--blue); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔵 Depositado</span>`;
            else if (ch.estado === 'Cobrado') badgeEstado = `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">✅ Cobrado</span>`;
            else if (ch.estado === 'Endosado') badgeEstado = `<span style="background:var(--magenta); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟣 Endosado a: ${ch.destinatario_endoso}</span>`;
            else if (ch.estado === 'Rechazado') badgeEstado = `<span style="background:var(--red); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔴 Rechazado</span>`;

            // Formato de fechas
            const fechaCobro = new Date(ch.fecha_cobro + 'T00:00:00');
            const esUrgente = ch.estado === 'En Cartera' && fechaCobro <= new Date() ? 'color:var(--red); font-weight:bold;' : '';

            tbody.innerHTML += `
                <tr>
                    <td style="${esUrgente}">${fechaCobro.toLocaleDateString('es-AR')}</td>
                    <td><b>${ch.banco}</b><br><span style="font-size:11px; color:var(--muted);">N° ${ch.numero}</span></td>
                    <td>${nombreParte}</td>
                    <td style="text-align:center;">${badgeTipo}</td>
                    <td class="tnum" style="color:var(--ink); font-weight:bold;">$ ${fmtMoney(ch.monto)}</td>
                    <td style="text-align:center;">${badgeEstado}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarCheque('${ch.id}')">✏️</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="cambiarEstadoCheque('${ch.id}', '${ch.estado}', this)">🔄 Estado</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarCheque('${ch.id}', this)">🗑️</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) { console.error("Error cargando cheques:", e); }
}

async function guardarCheque(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const montoCheque = parseFloat(document.getElementById('fch_monto').value);

    // El cheque tiene que ser un número mayor a 0.
    if (isNaN(montoCheque) || montoCheque <= 0) {
        Swal.fire('Monto inválido', 'El cheque tiene que ser un número mayor a 0.', 'warning');
        restore();
        return;
    }

    const clasificacion = document.getElementById('fch_clasificacion').value;
    const trabajoId = document.getElementById('fch_trabajo_id').value || null;

    // Un cheque recibido sin trabajo salda la deuda pero nunca aporta ganancia:
    // avisamos, sin bloquear (hay cobros que legítimamente no van contra un trabajo).
    if (clasificacion === 'Recibido' && !trabajoId) {
        const conf = await Swal.fire({
            title: 'Cheque sin trabajo asignado',
            html: 'Este cheque saldará la deuda del cliente, pero <b>no se imputará a ningún trabajo</b>, ' +
                  'así que no aportará ganancia al dashboard.<br><br>Podés asignarle el trabajo más adelante.',
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: 'Guardar igual',
            cancelButtonText: 'Volver y asignarlo',
            confirmButtonColor: '#D5006D'
        });
        if (!conf.isConfirmed) { restore(); return; }
    }

    try {
        const payload = {
            clasificacion: clasificacion,
            cliente_id: document.getElementById('fch_cliente').value || null,
            trabajo_id: trabajoId,
            banco: document.getElementById('fch_banco').value,
            numero: document.getElementById('fch_numero').value,
            monto: montoCheque,
            fecha_emision: document.getElementById('fch_emision').value,
            fecha_cobro: document.getElementById('fch_cobro').value
        };

        // Sólo lo mandamos para emitidos: en un recibido la clave viaja vacía y
        // borraría el proveedor de un cheque que ya fue endosado.
        if (clasificacion === 'Emitido') {
            payload.destinatario_endoso = document.getElementById('fch_destinatario').value || null;
        }

        let resp;
        if (idChequeEditando) {
            resp = await fetch(`${API_URL}/cheques/${idChequeEditando}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            resp = await fetch(`${API_URL}/cheques/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, estado: "En Cartera" })
            });
        }

        if (resp.ok) {
            const esAlta = !idChequeEditando;
            const titulo = idChequeEditando ? 'Cheque actualizado' : 'Cheque registrado';
            idChequeEditando = null;
            toggleDrawer('drawer-nuevo-cheque');
            cargarCheques();
            if (typeof cargarDashboard === "function") cargarDashboard();
            Swal.fire({ title: titulo, icon: 'success', timer: 1500, showConfirmButton: false });

            // Emitir un cheque propio es plata que sale: sin el gasto, los egresos
            // del dashboard quedan cortos y la ganancia neta sobrestimada.
            if (esAlta && clasificacion === 'Emitido') {
                const creado = await resp.json();
                await ofrecerGastoPorCheque(creado, creado.destinatario_endoso);
            }
        } else {
            // El backend bloquea editar monto/clasificación de un cheque ya cobrado o endosado.
            await mostrarErrorCheque(resp, 'No se pudo guardar el cheque');
        }
    } catch (error) { console.error(error); }
    finally { restore(); }
}

async function cambiarEstadoCheque(id, estadoActual, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🔄 Estado';

    const { value: nuevoEstado } = await Swal.fire({
        title: 'Actualizar Estado',
        input: 'select',
        inputOptions: {
            'En Cartera': '🟢 En Cartera',
            'Depositado': '🔵 Depositado (en el banco)',
            'Cobrado': '✅ Cobrado (entró la plata)',
            'Endosado': '🟣 Endosado a Proveedor',
            'Rechazado': '🔴 Rechazado'
        },
        inputValue: estadoActual,
        showCancelButton: true,
        confirmButtonColor: '#D5006D',
        confirmButtonText: 'Guardar'
    });

    if (!nuevoEstado || nuevoEstado === estadoActual) return;

    let destinatario = null;
    if (nuevoEstado === 'Endosado') {
        const { value: prov } = await Swal.fire({
            title: '¿A qué proveedor se lo entregaste?',
            input: 'text',
            inputValidator: (value) => { if (!value) return 'Tenés que ingresar un nombre' }
        });
        if (!prov) return;
        destinatario = prov;
    }

    // Revertir un estado final deshace un ingreso ya computado: el backend exige
    // un motivo, que queda asentado en el historial del cheque.
    let motivo = null;
    if (ESTADOS_FINALES_CHEQUE.includes(estadoActual)) {
        const { value: texto } = await Swal.fire({
            title: `Revertir un cheque ${estadoActual}`,
            html: `Este cheque ya impactó la caja. Contá por qué se revierte:`,
            input: 'text',
            inputPlaceholder: 'Ej: se cargó por error',
            showCancelButton: true,
            inputValidator: (value) => { if (!value) return 'El motivo es obligatorio' }
        });
        if (!texto) return;
        motivo = texto;
    }

    if (button) {
        button.disabled = true;
        button.innerText = 'Actualizando...';
    }

    try {
        const resp = await fetch(`${API_URL}/cheques/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado, destinatario_endoso: destinatario, motivo: motivo })
        });

        if (!resp.ok) {
            await mostrarErrorCheque(resp, 'No se pudo cambiar el estado');
            return;
        }

        cargarCheques();
        if (typeof cargarDashboard === "function") cargarDashboard();

        // Endosar es cobrar y pagar a la vez: el ingreso lo computa el cheque,
        // pero el egreso sólo existe si se registra el gasto.
        if (nuevoEstado === 'Endosado') {
            const cheque = await resp.json();
            await ofrecerGastoPorCheque(cheque, destinatario);
        }
    } catch (e) { console.error(e); }
    finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// Propone registrar el egreso que representa entregar un cheque a un proveedor.
// Se ofrece (no se crea solo) para no duplicar un gasto ya cargado a mano.
async function ofrecerGastoPorCheque(cheque, destinatario) {
    const nombre = destinatario || cheque.destinatario_endoso || 'Proveedor';
    const conf = await Swal.fire({
        title: '¿Registrar el gasto?',
        html: `Entregaste un cheque de <b>$ ${fmtMoney(cheque.monto)}</b> a <b>${nombre}</b>.<br><br>` +
              'Si no lo registrás como gasto, los egresos del dashboard van a quedar cortos.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, registrar gasto',
        cancelButtonText: 'Ya lo cargué',
        confirmButtonColor: '#D5006D'
    });
    if (!conf.isConfirmed) return;

    try {
        const resp = await fetch(`${API_URL}/gastos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                categoria: 'Insumos',
                concepto: `Pago con cheque ${cheque.banco} N° ${cheque.numero} a ${nombre}`,
                monto: cheque.monto,
                fecha: fechaHoyLocal(),
                metodo_pago: 'Cheque',
                comprobante: `Cheque N° ${cheque.numero}`,
                trabajo_id: cheque.trabajo_id || null
            })
        });

        if (resp.ok) {
            Swal.fire({ title: 'Gasto registrado', icon: 'success', timer: 1500, showConfirmButton: false });
            if (typeof cargarGastos === "function") cargarGastos();
            if (typeof cargarDashboard === "function") cargarDashboard();
        } else {
            await mostrarErrorCheque(resp, 'No se pudo registrar el gasto');
        }
    } catch (e) { console.error("Error creando el gasto del endoso:", e); }
}

async function eliminarCheque(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const conf = await Swal.fire({
        title: '¿Eliminar cheque?', icon: 'warning', showCancelButton: true,
        confirmButtonColor: '#d33', confirmButtonText: 'Sí, borrar'
    });
    if (conf.isConfirmed) {
        if (button) {
            button.disabled = true;
            button.innerText = 'Borrando...';
        }

        try {
            const resp = await fetch(`${API_URL}/cheques/${id}`, { method: 'DELETE' });
            // Un cheque cobrado o endosado ya movió plata: el backend lo rechaza.
            if (!resp.ok) {
                await mostrarErrorCheque(resp, 'No se puede eliminar');
                return;
            }
            cargarCheques();
            if (typeof cargarDashboard === "function") cargarDashboard();
        } finally {
            if (button) {
                button.disabled = false;
                button.innerText = originalText;
            }
        }
    }
}