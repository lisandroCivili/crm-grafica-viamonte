// Pagos, movimientos y notas de la ficha del cliente.

// ==========================================
// FORMULARIO DE PAGOS AVANZADO
// ==========================================
async function abrirDrawerPago() {
    if (!clienteActualFicha) return;
    try {
        const respT = await fetch(`${API_URL}/trabajos/`);
        const trabajos = await respT.json();
        const trabajosCliente = trabajos.filter(t => t.cliente_id === clienteActualFicha);
        
        const select = document.getElementById('fp_trabajo_id');
        // El pago debe imputarse a un trabajo (obligatorio): sin "a cuenta general".
        select.innerHTML = '<option value="">Seleccioná un trabajo...</option>';

        trabajosCliente.forEach(t => {
            const shortId = t.id.substring(0,6).toUpperCase();
            select.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)} (Total: $${fmtMoney(t.precio_venta)})</option>`;
        });
    } catch(e) { console.error(e); }

    // El bloque de cheque arranca oculto; se muestra si el método es Cheque.
    document.getElementById('fp_metodo').value = 'Efectivo';
    onMetodoPagoChange();

    toggleDrawer('drawer-nuevo-pago');
}

// Muestra los datos del cheque sólo cuando el método de pago elegido es Cheque.
function onMetodoPagoChange() {
    const esCheque = document.getElementById('fp_metodo').value === 'Cheque';
    document.getElementById('fp-bloque-cheque').style.display = esCheque ? 'block' : 'none';
}

async function guardarPago(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const monto = parseFloat(document.getElementById('fp_monto').value);
    const metodo = document.getElementById('fp_metodo').value;
    const trabajo_id = document.getElementById('fp_trabajo_id').value;

    // Un pago tiene que ser un número mayor a 0.
    if (isNaN(monto) || monto <= 0) {
        Swal.fire('Monto inválido', 'El pago tiene que ser un número mayor a 0.', 'warning');
        restore();
        return;
    }

    // Un pago sin trabajo salda la deuda pero nunca aporta ganancia: avisamos,
    // sin bloquear (hay cobros a cuenta que no van contra un trabajo puntual).
    // Mismo criterio que el alta de cheques recibidos.
    if (!trabajo_id) {
        const conf = await Swal.fire({
            title: 'Pago sin trabajo asignado',
            html: 'Este pago saldará la deuda del cliente, pero <b>no se imputará a ningún trabajo</b>, ' +
                  'así que no aportará ganancia al dashboard.<br><br>Podés asignarle el trabajo más adelante.',
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: 'Guardar igual',
            cancelButtonText: 'Volver y asignarlo',
            confirmButtonColor: '#D5006D'
        });
        if (!conf.isConfirmed) { restore(); return; }
    }

    const shortId = trabajo_id ? trabajo_id.substring(0,6).toUpperCase() : null;

    try {
        let resp;
        if (metodo === 'Cheque') {
            // El pago con cheque no es plata todavía: se registra como cheque
            // recibido (imputado al trabajo) y cuenta al cobrarse.
            const banco = document.getElementById('fp_ch_banco').value.trim();
            const numero = document.getElementById('fp_ch_numero').value.trim();
            const fechaCobro = document.getElementById('fp_ch_cobro').value;
            if (!banco || !numero || !fechaCobro) {
                Swal.fire('Faltan datos del cheque', 'Completá banco, número y fecha de cobro.', 'warning');
                restore();
                return;
            }
            resp = await fetch(`${API_URL}/cheques/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clasificacion: "Recibido",
                    cliente_id: clienteActualFicha,
                    // El select vacío da "", que no es un id válido: va null.
                    trabajo_id: trabajo_id || null,
                    banco: banco,
                    numero: numero,
                    monto: monto,
                    fecha_emision: new Date().toISOString().split('T')[0],
                    fecha_cobro: fechaCobro,
                    estado: "En Cartera"
                })
            });
            if (!resp.ok) throw new Error("Fallo al guardar cheque");
        } else {
            resp = await fetch(`${API_URL}/movimientos/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cliente_id: clienteActualFicha,
                    trabajo_id: trabajo_id || null,
                    monto: monto,
                    tipo: "Pago",
                    metodo: metodo,
                    descripcion: shortId
                        ? `Pago asociado a trabajo #${shortId}`
                        : "Pago a cuenta (sin trabajo imputado)"
                })
            });
            if (!resp.ok) throw new Error("Fallo al guardar movimiento");
        }

        document.getElementById('form-pago').reset();
        toggleDrawer('drawer-nuevo-pago');
        abrirFicha(clienteActualFicha);
        cargarClientes();
        if (typeof cargarCheques === "function") cargarCheques();

    } catch (error) {
        console.error("Error procesando el pago:", error);
        Swal.fire('Error', 'No se pudo registrar el pago.', 'error');
    } finally {
        restore();
    }
}

async function editarMovimiento(id) {
    try {
        const resp = await fetch(`${API_URL}/movimientos/${clienteActualFicha}`);
        const movimientos = await resp.json();
        const mov = movimientos.find(m => m.id === id);
        if (!mov) return;

        const { value: formValues } = await Swal.fire({
            title: 'Editar movimiento',
            html:
                `<input id="swal-monto" type="number" step="0.01" class="swal2-input" placeholder="Monto" value="${mov.monto}">` +
                `<input id="swal-desc" type="text" class="swal2-input" placeholder="Descripción" value="${esc(mov.descripcion)}">`,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const monto = parseFloat(document.getElementById('swal-monto').value);
                const descripcion = document.getElementById('swal-desc').value.trim();
                if (isNaN(monto) || monto <= 0) {
                    Swal.showValidationMessage('El monto tiene que ser un número mayor a 0');
                    return false;
                }
                if (!descripcion) {
                    Swal.showValidationMessage('La descripción no puede quedar vacía');
                    return false;
                }
                return { monto, descripcion };
            }
        });

        if (!formValues) return;

        const resp2 = await fetch(`${API_URL}/movimientos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formValues)
        });

        if (resp2.ok) {
            abrirFicha(clienteActualFicha);
            cargarClientes();
        } else {
            const err = await resp2.json();
            Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
        }
    } catch (e) { console.error("Error al editar movimiento:", e); }
}

async function eliminarMovimiento(id) {
    const confirmacion = await Swal.fire({
        title: '¿Eliminar este movimiento?',
        text: "Esto va a modificar el saldo de cuenta corriente del cliente.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#555',
        confirmButtonText: 'Sí, borrarlo',
        cancelButtonText: 'Cancelar'
    });

    if (!confirmacion.isConfirmed) return;

    try {
        await fetch(`${API_URL}/movimientos/${id}`, { method: 'DELETE' });
        abrirFicha(clienteActualFicha);
        cargarClientes();
    } catch (e) { console.error("Error al eliminar movimiento:", e); }
}

async function guardarNotaFicha() {
    if (!clienteActualFicha) return;
    const input = document.getElementById('nueva-nota-texto');
    const texto = input.value.trim();
    if (!texto) return;

    await fetch(`${API_URL}/notas/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cliente_id: clienteActualFicha, texto: texto })
    });
    
    input.value = '';
    abrirFicha(clienteActualFicha); // Recargamos para ver la nota
}

async function editarNota(id) {
    try {
        const resp = await fetch(`${API_URL}/notas/${clienteActualFicha}`);
        const notas = await resp.json();
        const nota = notas.find(n => n.id === id);
        if (!nota) return;

        const { value: nuevoTexto } = await Swal.fire({
            title: 'Editar nota',
            input: 'textarea',
            inputValue: nota.texto,
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            cancelButtonText: 'Cancelar',
            inputValidator: (value) => !value.trim() ? 'La nota no puede quedar vacía' : undefined
        });

        if (!nuevoTexto) return;

        await fetch(`${API_URL}/notas/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: nuevoTexto.trim() })
        });

        abrirFicha(clienteActualFicha);
    } catch (e) { console.error("Error al editar nota:", e); }
}

async function eliminarNota(id) {
    const confirmacion = await Swal.fire({
        title: '¿Eliminar esta nota?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#555',
        confirmButtonText: 'Sí, borrarla',
        cancelButtonText: 'Cancelar'
    });

    if (!confirmacion.isConfirmed) return;

    try {
        await fetch(`${API_URL}/notas/${id}`, { method: 'DELETE' });
        abrirFicha(clienteActualFicha);
    } catch (e) { console.error("Error al eliminar nota:", e); }
}

