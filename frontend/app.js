// Ruta relativa: el frontend ahora lo sirve el mismo backend (FastAPI monta
// esta carpeta), así que siempre está en el mismo origen que la API.
const API_URL = '/api';
let clienteActualFicha = null; // Guardamos qué cliente está abierto
// Trabajos de la última carga del Kanban, indexados por id. Los onclick de las
// tarjetas pasan el id y leen de acá: interpolar textos en el atributo se rompe
// con un apóstrofo en la descripción.
const trabajosPorId = new Map();

// ==========================================
// HELPER: FORMATO DE DINERO (siempre 2 decimales)
// ==========================================
// El backend es la fuente de verdad de la matemática (Decimal). Acá solo mostramos.
function fmtMoney(valor) {
    const n = Number(valor) || 0;
    return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ==========================================
// HELPER: CÓMO SE MUESTRA UN SALDO DE CUENTA CORRIENTE
// ==========================================
// Un saldo negativo NO es deuda negativa: es plata que el cliente tiene a favor
// (la seña de un trabajo que después se canceló, un pago de más). Mostrarlo como
// "-$ 5.000" en una columna que dice "Saldo" se lee como un error de cálculo, así
// que se muestra el valor absoluto y se nombra qué es. Vive acá porque el saldo se
// pinta en la tabla de clientes y en la ficha, y la regla tiene que ser una sola.
function saldoMostrable(saldo) {
    const n = Number(saldo) || 0;
    return {
        monto: `$ ${fmtMoney(Math.abs(n))}`,
        color: n > 0 ? "var(--red)" : "var(--green)",
        aclaracion: n < 0 ? "Saldo a favor" : "",
    };
}

// ==========================================
// HELPER: ESCAPE DE TEXTO PARA innerHTML
// ==========================================
// Todo el render arma HTML por interpolación. Un cliente "O'Brien" o una
// descripción con < rompían el markup (y los onclick inline). Pasar SIEMPRE
// por acá cualquier texto que venga de la base.
const ESCAPES_HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function esc(valor) {
    return String(valor ?? '').replace(/[&<>"']/g, c => ESCAPES_HTML[c]);
}

// ==========================================
// HELPER: MENSAJE DE ERROR DE LA API
// ==========================================
// El `detail` de FastAPI es un string en los HTTPException nuestros, pero un
// array de objetos en los 422 de validación de Pydantic. Devolvemos algo
// legible en los dos casos.
function detalleError(error, porDefecto = 'Revisá los datos e intentá de nuevo.') {
    const detail = error?.detail;
    if (!detail) return porDefecto;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('\n') || porDefecto;
    }
    return porDefecto;
}

// ==========================================
// HELPER: DISABLE ON SUBMIT
// ==========================================
function disableButtonOnSubmit(e) {
    const button = e.submitter || e.target.querySelector('button[type="submit"]');
    if (button) {
        button.disabled = true;
        button._originalText = button.innerText;
        button.innerText = 'Procesando...';
        return () => {
            button.disabled = false;
            button.innerText = button._originalText || 'Guardar';
        };
    }
    return () => {};
}

// ==========================================
// CONTROL DE ACCESO (SIMPLE)
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    // Si no está la variable de sesión activa en el navegador, mostramos el telón
    if (localStorage.getItem('viamonte_sesion') !== 'activa') {
        document.getElementById('login-overlay').style.display = 'flex';
    } else {
        // Si ya está activa, bajamos el telón y arrancamos la app normal
        document.getElementById('login-overlay').style.display = 'none';
        iniciarApp();
        
        // Recuperamos la última pestaña en la que estábamos
        const lastTab = localStorage.getItem('viamonte_last_tab') || 'tab-dashboard';
        const tabBoton = document.querySelector(`[onclick*="${lastTab}"]`);
        if (tabBoton) switchTab(lastTab, tabBoton);
    }
});

async function hacerLogin(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const u = document.getElementById('login-user').value;
    const p = document.getElementById('login-pass').value;

    try {
        const resp = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario: u, password: p })
        });

        if (resp.ok) {
            localStorage.setItem('viamonte_sesion', 'activa');
            document.getElementById('login-overlay').style.display = 'none';
            iniciarApp();
        } else {
            Swal.fire('Error', 'Usuario o contraseña incorrectos', 'error');
        }
    } catch(e) {
        console.error("Error en login", e);
    } finally {
        restore();
    }
}

function cerrarSesion() {
    localStorage.removeItem('viamonte_sesion');
    // Recargar la página es la forma más limpia de resetear todo y volver a mostrar el login
    location.reload(); 
}
async function descargarRespaldo(button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || 'Descargar';
    if (button) {
        button.disabled = true;
        button.innerText = 'Procesando...';
    }

    try {
        Swal.fire({
            title: 'Generando respaldo...',
            text: 'Empaquetando la base de datos',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        const resp = await fetch(`${API_URL}/backup`);
        if (!resp.ok) throw new Error("Error al descargar");

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const hoy = new Date();
        const fechaStr = `${hoy.getDate().toString().padStart(2, '0')}-${(hoy.getMonth() + 1).toString().padStart(2, '0')}-${hoy.getFullYear()}`;
        a.download = `respaldo_viamonte_${fechaStr}.db`;

        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        Swal.fire('¡Respaldo Exitoso!', 'El archivo de tu base de datos se guardó en la carpeta de Descargas.', 'success');
    } catch (error) {
        console.error("Error en backup:", error);
        Swal.fire('Error', 'No se pudo generar el respaldo', 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// ==========================================
// INICIO Y CARGA DE MÓDULOS
// ==========================================
function iniciarApp() {
    cargarClientes();
    cargarDashboard();
    cargarTrabajos();
    cargarSelectorClientes();
    cargarPresupuestos();
    cargarGastos();
    cargarStock();
    cargarCheques();
}

// ==========================================
// 2. UI Y NAVEGACIÓN (Pestañas y Acordeones)
// ==========================================
function switchTab(tabId, element) {
    document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    if(element) element.classList.add('active');
    
    // Guardamos la última pestaña visitada en la memoria
    localStorage.setItem('viamonte_last_tab', tabId);
}

function toggleDrawer(id) {
    document.getElementById(id).classList.toggle('open');
}

// Pestañas internas de la ficha del cliente
function switchFichaTab(tabName) {
    document.querySelectorAll('.tabs-ficha .btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.ficha-content').forEach(c => c.classList.remove('active'));
    
    document.getElementById(`btn-tab-${tabName}`).classList.add('active');
    document.getElementById(`ficha-content-${tabName}`).classList.add('active');
}

// Abrir/Cerrar acordeones de trabajos
function toggleAccordion(element) {
    element.parentElement.classList.toggle('open');
}

// ==========================================
// 3. FICHA DINÁMICA (El núcleo contable)
// ==========================================
async function abrirFicha(id) {
    clienteActualFicha = id;
    toggleDrawer('drawer-cliente');
    document.getElementById('ficha-nombre').innerText = "Cargando datos...";
    
    switchFichaTab('trabajos');

    try {
        const [respC, respT, respM, respN, respS] = await Promise.all([
            fetch(`${API_URL}/clientes/`),
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/movimientos/${id}`),
            fetch(`${API_URL}/notas/${id}`),
            fetch(`${API_URL}/movimientos/saldo/${id}`)
        ]);

        const clientes = await respC.json();
        const todosTrabajos = await respT.json();
        const movimientos = respM.ok ? await respM.json() : [];
        const notas = respN.ok ? await respN.json() : [];
        const saldoInfo = respS.ok ? await respS.json() : null;
        
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
            const textoPago = saldoTrabajo <= 0
                ? '<span style="color:var(--green); font-weight:600;">Pagado 100%</span>'
                : `<span style="color:var(--red); font-weight:600;">Debe: $${fmtMoney(saldoTrabajo)}</span> <span style="font-size:11px; color:var(--muted);">(Abonó: $${fmtMoney(pagosDeEsteTrabajo)})</span>`;

            divTrabajos.innerHTML += `
                <div class="accordion-item">
                    <div class="accordion-header" onclick="toggleAccordion(this)">
                        <span>#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</span>
                        <span style="color:var(--magenta)">$${fmtMoney(t.precio_venta)} ▾</span>
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
                        <button class="btn secondary" style="margin-top:12px; margin-left:8px; font-size:12px; border-color:var(--red); color:var(--red);" onclick="eliminarTrabajo('${t.id}', this)">🗑️ Borrar</button>
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

// ==========================================
// 4. LÓGICA DE PAGOS Y NOTAS
// ==========================================
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

// ==========================================
// 5. EDICIÓN DE TRABAJOS (Historial automático)
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
            precio_venta: nuevoPrecio,
            papel_tipo: opt('fe_papel_tipo'),
            medida_terminado: opt('fe_medida_terminado'),
            medida_pliego: opt('fe_medida_pliego'),
            corte_pliego: opt('fe_corte_pliego'),
            tintas: opt('fe_tintas'),
            troquelado: opt('fe_troquelado'),
            barniz: opt('fe_barniz'),
            otros: opt('fe_otros')
        };
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
            throw new Error(err.detail || "No se pudo guardar el cambio.");
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
            Swal.fire('No se pudo eliminar', err.detail || 'Error desconocido', 'error');
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

// ==========================================
// 6. FUNCIONES BASE QUE YA TENÍAMOS (Carga de Tablas)
// ==========================================

async function cargarClientes(filtro = "") {
    try {
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        // El saldo lo calcula el backend (mismo cálculo que la ficha, cheques incluidos).
        const [respC, respS] = await Promise.all([
            fetch(url),
            fetch(`${API_URL}/clientes/saldos`)
        ]);

        const clientes = await respC.json();
        const saldos = respS.ok ? await respS.json() : [];

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
                  <td class="tnum" style="color: ${vistaSaldo.color}; font-weight: 600;">
                    ${vistaSaldo.monto}
                    ${vistaSaldo.aclaracion ? `<div style="font-size:11px; font-weight:500;">${vistaSaldo.aclaracion}</div>` : ''}
                  </td>
                  <td>
                    <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                    <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
                    <button class="btn secondary" style="font-size:12px; padding:6px; margin-left:4px;" onclick="abrirModalEditarCliente('${cliente.id}')">✏️</button>
                    <button class="btn secondary" style="font-size:12px; padding:6px; margin-left:4px; border-color:var(--red); color:var(--red);" onclick="eliminarCliente('${cliente.id}', this)">🗑️</button>
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
            Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
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
            Swal.fire('No se pudo eliminar', err.detail || 'Error desconocido', 'error');
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
            fecha_creacion: new Date().toISOString().split('T')[0],
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

// Puebla los selects de papel (alta y edición de trabajo, y presupuesto) con
// los artículos de stock. El papel es opcional: la primera opción es vacía.
// Sólo listamos artículos en Pliegos: el backend rechaza cualquier otra unidad
// (no tiene sentido descontarle "3 pliegos" a un bidón de tinta en litros).
async function cargarSelectoresPapel() {
    const stock = await (await fetch(`${API_URL}/stock/`)).json();
    const papeles = stock.filter(a => a.unidad === 'Pliegos');
    const opciones = '<option value="">Sin papel del stock</option>' +
        papeles.map(a => `<option value="${a.id}">${esc(a.nombre)} (${a.cantidad} ${a.unidad})</option>`).join('');
    ['ft_papel_id', 'fe_papel_id', 'mp_papel_id'].forEach(id => {
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

    // Pasar a Producción exige la orden impresa. Si falta, la ofrecemos en el acto.
    if (nuevoEstado === "En Producción") {
        return pasarAProduccionDesdeKanban(id);
    }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "El backend rechazó el cambio de estado.");
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
            throw new Error(err.detail?.[0]?.msg || err.detail || "No se pudo iniciar el diseño.");
        }
        refrescarTablero();
    } catch (error) {
        Swal.fire('No se pudo iniciar el diseño', error.message, 'error');
        refrescarTablero();
    }
}

// Ofrece imprimir la orden si falta, y recién ahí pasa a Producción.
async function pasarAProduccionDesdeKanban(id) {
    const trabajos = await (await fetch(`${API_URL}/trabajos/`)).json();
    const t = trabajos.find(x => x.id === id);
    if (!t) { refrescarTablero(); return; }

    if (!t.orden_impresa) {
        const r = await Swal.fire({
            title: 'Falta imprimir la orden',
            text: 'Para mandar el trabajo a producción hay que emitir la orden. ¿La imprimo ahora?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Imprimir y continuar',
            cancelButtonText: 'Cancelar'
        });
        if (!r.isConfirmed) { refrescarTablero(); return; }

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
            throw new Error(err.detail || "El backend rechazó el cambio.");
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
                    text: (err.detail || '') + ' ¿Emitir la orden igual? (el stock quedará en negativo)',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Emitir igual',
                    cancelButtonText: 'Cancelar'
                });
                if (r.isConfirmed) return descargarOrden(id, true);
                return false;
            }
            throw new Error(err.detail || "No se pudo generar la orden.");
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
async function cargarTrabajos() {
    const [trabajos, clientes, presupuestos] = await Promise.all([
        (await fetch(`${API_URL}/trabajos/`)).json(),
        (await fetch(`${API_URL}/clientes/`)).json(),
        (await fetch(`${API_URL}/presupuestos/`)).json()
    ]);

    // Trabajos que ya tienen presupuesto asociado: los demás no aportan ganancia
    // y se marcan en el tablero para que el usuario lo sepa.
    const trabajosConPresupuesto = new Set(
        presupuestos.filter(p => p.trabajo_id).map(p => p.trabajo_id)
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
        const sinPresupuesto = !trabajosConPresupuesto.has(t.id);
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
              <div class="date">${t.fecha_creacion} - $${fmtMoney(t.precio_venta)}</div>
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
            Swal.fire('No se pudo cancelar', error.detail || 'Revisá los datos e intentá de nuevo.', 'error');
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
            Swal.fire('No se pudo reactivar', error.detail || 'Revisá los datos e intentá de nuevo.', 'error');
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

// ==========================================
// MÓDULO DE PRESUPUESTOS AVANZADO
// ==========================================

const LISTA_COSTOS = ["Papel", "Troquel", "Luz", "Diseño", "Chapas", "Impresión", "Barniz / Laminado", "Cordón de bolsas", "Troquelado", "Tinta", "Pegado y armado", "Empaquetado / Flete", "Corte / Encuadernación", "Gastos otros"];

let idPresupuestoVersionDe = null; // Para saber si estamos duplicando uno viejo
let idPresupuestoEditando = null; // Para saber si estamos editando un presupuesto existente (en vez de crear uno nuevo)

async function abrirDrawerPresupuesto() {
    idPresupuestoVersionDe = null; // Reseteamos por si era nuevo
    idPresupuestoEditando = null;
    document.getElementById('modal-presupuesto').classList.remove('hidden');
    // Por defecto visible (editar lo oculta); acá lo restauramos.
    document.getElementById('mp-asociar-trabajo-row').style.display = '';
    // El número real (numero_secuencia) lo asigna el backend al guardar. Antes
    // acá se inventaba uno al azar que no coincidía con nada y cambiaba cada
    // vez que se abría el modal.
    document.getElementById('lbl-pres-id').innerHTML = `<span style="color:var(--muted); font-size:13px;">Nº (se asigna al guardar)</span>`;
    
    const cont = document.getElementById('contenedor-costos');
    cont.innerHTML = '';
    LISTA_COSTOS.forEach(c => {
        cont.innerHTML += `<div class="costo-row"><label>${c}</label><input type="number" class="input-costo" data-nombre="${c}" value="0" oninput="calcularModal()" onfocus="if(this.value=='0')this.value=''"></div>`;
    });

    // Con await: editarPresupuesto() y duplicar() llaman a esta función y recién
    // después asignan mp_papel_id. Si las opciones no estuvieran cargadas
    // todavía, la asignación no encontraría el <option> y se perdería el papel.
    await cargarSelectoresPapel();

    try {
        const resp = await fetch(`${API_URL}/clientes/`);
        const clientes = await resp.json();
        const select = document.getElementById('mp_cliente_id');
        select.innerHTML = '<option value="">Sin cliente (borrador)</option>';
        clientes.forEach(c => select.innerHTML += `<option value="${c.id}">${esc(c.nombre_completo)}</option>`);
    } catch (e) { console.error(e); }

    // Trabajos que todavía no tienen presupuesto: se pueden asociar a este.
    try {
        const respT = await fetch(`${API_URL}/trabajos/?sin_presupuesto=true`);
        const trabajos = await respT.json();
        const selT = document.getElementById('mp_trabajo_id');
        selT.innerHTML = '<option value="">No asociar</option>';
        trabajos
            .filter(t => t.estado !== 'Cancelado')
            .forEach(t => {
                const shortId = t.id.substring(0, 6).toUpperCase();
                selT.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</option>`;
            });
    } catch (e) { console.error(e); }

    calcularModal();
}

function cerrarModalPresupuesto() {
    document.getElementById('modal-presupuesto').classList.add('hidden');
    document.getElementById('form-presupuesto').reset();
}

function calcularModal() {
    const inputs = document.querySelectorAll('.input-costo');
    let subtotal = 0;
    inputs.forEach(i => subtotal += (parseFloat(i.value) || 0));
    
    const margen = parseFloat(document.getElementById('mp_margen').value) || 0;
    const cantidad = parseInt(document.getElementById('mp_cantidad').value) || 1;
    
    const ganancia = subtotal * (margen / 100);
    const total = subtotal + ganancia;
    const unidad = total / cantidad;

    // Preview en vivo. El valor definitivo lo recalcula y guarda el backend (Decimal).
    document.getElementById('lbl-m-subtotal').innerText = `$ ${fmtMoney(subtotal)}`;
    document.getElementById('lbl-m-txt-ganancia').innerText = `${margen}% de ganancia`;
    document.getElementById('lbl-m-ganancia').innerText = `$ ${fmtMoney(ganancia)}`;
    document.getElementById('lbl-m-total').innerText = `$ ${fmtMoney(total)}`;
    document.getElementById('lbl-m-unidad').innerText = `$ ${fmtMoney(unidad)}`;
}

// AGREGAR ESTA FUNCIÓN NUEVA
async function duplicarPresupuesto(id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const p = (await respP.json()).find(x => x.id === id);
        if (!p) return;

        await abrirDrawerPresupuesto(); // Prepara el modal limpio
        
        idPresupuestoVersionDe = id; // Clavamos la relación
        document.getElementById('lbl-pres-id').innerHTML = `<span style="color:var(--muted); font-size:13px;">Nº (se asigna al guardar)</span> <span style="color:var(--magenta); font-size:12px;">(Versión de #${id.substring(0,6).toUpperCase()})</span>`;
        
        // Rellenamos
        document.getElementById('mp_cliente_id').value = p.cliente_id || '';
        document.getElementById('mp_descripcion').value = p.descripcion;
        document.getElementById('mp_cantidad').value = p.cantidad;
        document.getElementById('mp_material').value = p.material || '';
        document.getElementById('mp_gramaje').value = p.gramaje || '';
        document.getElementById('mp_papel_id').value = p.papel_id || '';
        document.getElementById('mp_cantidad_pliegos').value = p.cantidad_pliegos || '';
        // Después de asignar los dos, no antes: el campo arranca deshabilitado y
        // hay que habilitarlo si el presupuesto ya traía un papel elegido.
        sincronizarPliegosConPapel('mp_papel_id', 'mp_cantidad_pliegos');
        document.getElementById('mp_margen').value = p.margen_ganancia;
        document.getElementById('mp_estado').value = "Borrador";

        // Rellenamos los costos específicos
        document.querySelectorAll('.input-costo').forEach(input => {
            const nombre = input.getAttribute('data-nombre');
            if (p.detalles_costos && p.detalles_costos[nombre]) {
                input.value = p.detalles_costos[nombre];
            }
        });
        calcularModal();
    } catch (e) { console.error(e); }
}

// Abre el modal en modo edición, precargado con los datos del presupuesto elegido
async function editarPresupuesto(id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const p = (await respP.json()).find(x => x.id === id);
        if (!p) return;

        await abrirDrawerPresupuesto(); // Prepara el modal limpio (y resetea las banderas)

        idPresupuestoEditando = id;
        document.getElementById('lbl-pres-id').innerHTML = `Nº ${p.numero_secuencia || ''} <span style="color:var(--magenta); font-size:12px;">(Editando)</span>`;

        // Asociar a un trabajo sólo aplica al crear: al editar se oculta.
        document.getElementById('mp-asociar-trabajo-row').style.display = 'none';

        document.getElementById('mp_cliente_id').value = p.cliente_id || '';
        document.getElementById('mp_descripcion').value = p.descripcion;
        document.getElementById('mp_cantidad').value = p.cantidad;
        document.getElementById('mp_material').value = p.material || '';
        document.getElementById('mp_gramaje').value = p.gramaje || '';
        document.getElementById('mp_papel_id').value = p.papel_id || '';
        document.getElementById('mp_cantidad_pliegos').value = p.cantidad_pliegos || '';
        // Después de asignar los dos, no antes: el campo arranca deshabilitado y
        // hay que habilitarlo si el presupuesto ya traía un papel elegido.
        sincronizarPliegosConPapel('mp_papel_id', 'mp_cantidad_pliegos');
        document.getElementById('mp_margen').value = p.margen_ganancia;
        document.getElementById('mp_estado').value = p.estado;

        document.querySelectorAll('.input-costo').forEach(input => {
            const nombre = input.getAttribute('data-nombre');
            if (p.detalles_costos && p.detalles_costos[nombre]) {
                input.value = p.detalles_costos[nombre];
            }
        });
        calcularModal();
    } catch (e) { console.error(e); }
}

async function guardarPresupuestoModerno(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const inputs = document.querySelectorAll('.input-costo');
    let detalles = {}; let subtotal = 0;
    inputs.forEach(i => {
        const val = parseFloat(i.value) || 0;
        if (val > 0) { detalles[i.getAttribute('data-nombre')] = val; subtotal += val; }
    });

    const margen = parseFloat(document.getElementById('mp_margen').value) || 0;

    // Papel del stock: los dos campos van juntos o no van. Elegir un papel sin
    // decir cuántos pliegos no descuenta nada, y poner pliegos sin papel no
    // tiene a qué aplicarlos.
    const papelId = document.getElementById('mp_papel_id').value || null;
    const pliegos = parseFloat(document.getElementById('mp_cantidad_pliegos').value) || null;
    if (papelId && !pliegos) {
        Swal.fire('Faltan los pliegos', 'Elegiste un papel del stock: indicá cuántos pliegos consume el trabajo para que la orden pueda descontarlos.', 'warning');
        restore();
        return;
    }
    if (pliegos && !papelId) {
        Swal.fire('Falta el papel', 'Cargaste una cantidad de pliegos pero no elegiste de qué papel del stock descontarlos.', 'warning');
        restore();
        return;
    }

    try {
        if (idPresupuestoEditando) {
            // Edición: solo mandamos los campos editables, el backend recalcula costo/precio.
            const payloadEdicion = {
                cliente_id: document.getElementById('mp_cliente_id').value || null,
                descripcion: document.getElementById('mp_descripcion').value,
                cantidad: parseInt(document.getElementById('mp_cantidad').value),
                material: document.getElementById('mp_material').value || null,
                gramaje: document.getElementById('mp_gramaje').value || null,
                detalles_costos: detalles,
                margen_ganancia: margen,
                estado: document.getElementById('mp_estado').value,
                papel_id: papelId,
                cantidad_pliegos: pliegos
            };
            const resp = await fetch(`${API_URL}/presupuestos/${idPresupuestoEditando}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payloadEdicion) });
            if (!resp.ok) {
                const err = await resp.json();
                Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
                return;
            }
            cerrarModalPresupuesto();
            cargarPresupuestos();
            Swal.fire({ title: '¡Actualizado!', text: 'Presupuesto editado con éxito', icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            // OJO: costo_materiales y precio_final los RECALCULA el backend a partir de
            // detalles_costos y margen_ganancia. Se mandan en 0 solo para cumplir el schema.
            const payload = {
                cliente_id: document.getElementById('mp_cliente_id').value || null,
                trabajo_id: document.getElementById('mp_trabajo_id').value || null,
                version_de: idPresupuestoVersionDe,
                descripcion: document.getElementById('mp_descripcion').value,
                cantidad: parseInt(document.getElementById('mp_cantidad').value),
                material: document.getElementById('mp_material').value || null,
                gramaje: document.getElementById('mp_gramaje').value || null,
                costo_materiales: 0,
                detalles_costos: detalles,
                margen_ganancia: margen,
                precio_final: 0,
                estado: document.getElementById('mp_estado').value,
                fecha_creacion: new Date().toISOString().split('T')[0],
                papel_id: papelId,
                cantidad_pliegos: pliegos
            };
            const respNuevo = await fetch(`${API_URL}/presupuestos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (!respNuevo.ok) {
                const err = await respNuevo.json().catch(() => ({}));
                Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
                return;
            }
            cerrarModalPresupuesto();
            cargarPresupuestos();
            if (typeof cargarTrabajos === "function") cargarTrabajos();
            Swal.fire({ title: '¡Guardado!', text: 'Presupuesto creado con éxito', icon: 'success', timer: 1500, showConfirmButton: false });
        }
    } catch (e) { console.error(e); }
    finally { restore(); }
}

async function eliminarPresupuesto(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este presupuesto?',
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
        const resp = await fetch(`${API_URL}/presupuestos/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            cargarPresupuestos();
            Swal.fire('¡Eliminado!', 'El presupuesto fue borrado del sistema.', 'success');
        } else {
            const err = await resp.json();
            Swal.fire('No se pudo eliminar', err.detail || 'Error desconocido', 'error');
        }
    } catch (e) {
        console.error("Error al eliminar presupuesto:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

async function cargarPresupuestos() {
    try {
        const [respP, respC] = await Promise.all([ fetch(`${API_URL}/presupuestos/`), fetch(`${API_URL}/clientes/`) ]);
        if(!respP.ok) return; 
        
        const presupuestos = await respP.json();
        const clientes = await respC.json();
        const tbody = document.querySelector('#tablePresupuestos tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        presupuestos.reverse().forEach(p => {
            const cliente = clientes.find(c => c.id === p.cliente_id);
            const nombreCliente = cliente ? cliente.nombre_completo : 'Sin cliente';
            const shortId = p.id.substring(0,6).toUpperCase(); // ID DEL NUEVO
            
            // Lógica de Vencimiento
            const diasPasados = Math.floor((new Date() - new Date(p.fecha_creacion)) / (1000 * 60 * 60 * 24));
            let estadoBadge = `<span style="background:var(--paper); padding:4px 8px; border-radius:4px; font-size:12px; font-weight:600;">${p.estado}</span>`;
            
            if ((p.estado === 'Borrador' || p.estado === 'Enviado') && diasPasados >= 15) {
                estadoBadge += `<br><span style="background:var(--red); color:white; padding:2px 6px; border-radius:4px; font-size:10px; display:inline-block; margin-top:4px;">⚠️ Vencido</span>`;
            }

            // Lógica de Relación (Versión de...)
            let versionBadge = '';
            if (p.version_de) {
                versionBadge = `<br><span style="font-size:10px; background:var(--magenta-soft); color:var(--magenta); padding:2px 4px; border-radius:4px; display:inline-block; margin-top:4px;">Versión de #${p.version_de.substring(0,6).toUpperCase()}</span>`;
            }

            const btnConvertir = p.convertido_a_trabajo
                ? `<button class="btn secondary" disabled style="font-size:12px; padding:6px; opacity:0.5;">Ya es Trabajo</button>`
                : `<button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--green); color:var(--green);" onclick="convertirATrabajo('${p.id}', this)">A Trabajo</button>`;

            const btnesEdicion = p.convertido_a_trabajo
                ? ''
                : `<button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarPresupuesto('${p.id}')">✏️ Editar</button>
                   <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarPresupuesto('${p.id}', this)">🗑️</button>`;

            tbody.innerHTML += `
                <tr>
                    <td>${p.fecha_creacion}</td>
                    <td><b>${nombreCliente}</b></td>
                    <td>
                        <span style="font-size:11px; color:var(--muted);">#${shortId}</span><br>
                        ${p.cantidad}x ${p.descripcion} 
                        ${versionBadge}
                    </td>
                    <td class="tnum" style="color:var(--magenta); font-weight:bold;">$ ${fmtMoney(p.precio_final)}</td>
                    <td>${estadoBadge}</td>
                    <td style="display:flex; gap:5px; justify-content:center; flex-wrap:wrap;">
                        ${btnConvertir}
                        ${btnesEdicion}
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="duplicarPresupuesto('${p.id}')">Duplicar</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--ink);" onclick="generarPDFInterno('${p.id}')">PDF Int</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--blue);" onclick="generarPDFCliente('${p.id}')">PDF Cli</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) { console.error(e); }
}

async function convertirATrabajo(presupuesto_id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || 'A Trabajo';
    if (button) {
        button.disabled = true;
        button.innerText = 'Procesando...';
    }

    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const presupuestos = await respP.json();
        const p = presupuestos.find(x => x.id === presupuesto_id);
        if (!p) throw new Error("No se encontró el presupuesto.");

        if (!p.cliente_id) {
            Swal.fire('Falta el cliente', 'Asigná un cliente al presupuesto antes de convertirlo a trabajo.', 'warning');
            return;
        }

        let cancelarAnterior = false;
        const madre = p.version_de ? presupuestos.find(x => x.id === p.version_de) : null;

        if (madre && madre.trabajo_id) {
            const accion = await Swal.fire({
                title: 'Presupuesto Duplicado',
                text: 'Este presupuesto es una corrección/versión de otro anterior. ¿Qué hacemos con el trabajo original?',
                icon: 'question',
                showDenyButton: true,
                showCancelButton: true,
                confirmButtonText: 'Cancelar el anterior',
                denyButtonText: 'Mantener ambos',
                cancelButtonText: 'Abortar',
                confirmButtonColor: '#D5006D',
                denyButtonColor: '#555'
            });

            if (accion.isDismissed) return;
            if (accion.isConfirmed) cancelarAnterior = true;
        } else if (!p.version_de) {
            const confirmacion = await Swal.fire({
                title: '¿Pasar a Trabajo?',
                text: "Esto enviará el presupuesto al Kanban de producción.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#D5006D',
                cancelButtonColor: '#555',
                confirmButtonText: 'Sí, enviar a Taller'
            });
            if (!confirmacion.isConfirmed) return;
        }

        // El backend crea el trabajo y marca el presupuesto en una sola transacción.
        const resp = await fetch(`${API_URL}/presupuestos/${presupuesto_id}/convertir`, { method: 'POST' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "No se pudo convertir el presupuesto.");
        }

        // La conversión ya está hecha: si falla la cancelación del trabajo
        // anterior avisamos, pero no la reportamos como fallida. Por eso el
        // fetch va con su propio try: un error de red acá NO significa que la
        // conversión haya fallado, y el catch de abajo diría lo contrario.
        // La versión anterior se descarta, así que su papel vuelve al stock.
        let avisoCancelacion = '';
        if (cancelarAnterior) {
            try {
                const respCancel = await fetch(`${API_URL}/trabajos/${madre.trabajo_id}?devolver_papel=true`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ estado: "Cancelado" })
                });
                if (!respCancel.ok) throw new Error('respuesta no OK');
            } catch (e) {
                console.error('Error al cancelar el trabajo anterior:', e);
                avisoCancelacion = 'El trabajo nuevo se creó, pero no se pudo cancelar el trabajo anterior. Cancelalo con el botón ✖ de su tarjeta en el Kanban.';
            }
            // (Se eliminó el Movimiento monto:0 de "cancelado por corrección": no es plata real.)
        }

        cargarTrabajos();
        cargarPresupuestos();
        if (avisoCancelacion) {
            Swal.fire('Atención', avisoCancelacion, 'warning');
        } else {
            Swal.fire('¡Enviado!', 'El trabajo ya está en el tablero.', 'success');
        }

    } catch (e) {
        console.error(e);
        Swal.fire('No se pudo convertir', e.message, 'error');
    }
    finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// ----------------------------------------------------
// GENERADORES DE PDF (Doble versión)
// ----------------------------------------------------
async function armarMoldeBasePDF(presupuesto_id) {
    const [respP, respC] = await Promise.all([ fetch(`${API_URL}/presupuestos/`), fetch(`${API_URL}/clientes/`) ]);
    const p = (await respP.json()).find(x => x.id === presupuesto_id);
    const c = (await respC.json()).find(x => x.id === p.cliente_id);
    return { p, c };
}

// Helpers de fecha/nombre para los PDF (fecha_creacion viene como 'YYYY-MM-DD';
// se parsea a mano para no depender del huso horario).
function fmtFechaAR(iso) {
    if (!iso) return '';
    const [y, m, d] = String(iso).split('-');
    return `${d}/${m}/${y}`;
}
function fmtFechaArchivo(iso) {
    if (!iso) return new Date().toISOString().split('T')[0].split('-').reverse().join('-');
    const [y, m, d] = String(iso).split('-');
    return `${d}-${m}-${y}`;
}
function sanitizarNombreArchivo(txt) {
    return (txt || 'SinCliente').replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'SinCliente';
}

// 1. PDF PARA EL CLIENTE (formal, formato Gráfica Viamonte)
async function generarPDFCliente(presupuesto_id) {
    const { p, c } = await armarMoldeBasePDF(presupuesto_id);
    const nombreCliente = c ? c.nombre_completo : 'Sin cliente';
    const fecha = fmtFechaAR(p.fecha_creacion);
    const precioUnitario = p.cantidad ? Number(p.precio_final) / p.cantidad : Number(p.precio_final);

    const div = document.createElement('div');
    div.style.padding = '40px';
    div.style.fontFamily = 'Arial, sans-serif';
    div.style.color = '#222';
    div.innerHTML = `
        <div style="text-align:center; border-bottom:3px solid #D5006D; padding-bottom:12px; margin-bottom:10px;">
            <div style="font-size:26px; font-weight:bold; letter-spacing:1px; color:#D5006D;">GRÁFICA VIAMONTE</div>
            <div style="font-size:20px; font-weight:bold; letter-spacing:3px; margin-top:4px;">PRESUPUESTO</div>
        </div>
        <p style="margin:4px 0; font-size:13px;">Fecha de emisión: ${fecha} - S.M. de Tucumán.</p>
        <p style="margin:4px 0 20px; font-size:13px;"><b>Cliente:</b> ${nombreCliente}</p>

        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr style="background:#f4f4f4;">
                    <th style="border:1px solid #ccc; padding:8px; text-align:left;">Producto</th>
                    <th style="border:1px solid #ccc; padding:8px; text-align:center; width:70px;">Cantidad</th>
                    <th style="border:1px solid #ccc; padding:8px; text-align:right; width:110px;">Precio Unitario</th>
                    <th style="border:1px solid #ccc; padding:8px; text-align:right; width:110px;">Precio Total</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="border:1px solid #ccc; padding:8px; word-break:break-word; white-space:pre-wrap;">${p.descripcion}</td>
                    <td style="border:1px solid #ccc; padding:8px; text-align:center;">${p.cantidad}</td>
                    <td style="border:1px solid #ccc; padding:8px; text-align:right;">$ ${fmtMoney(precioUnitario)}</td>
                    <td style="border:1px solid #ccc; padding:8px; text-align:right;">$ ${fmtMoney(p.precio_final)}</td>
                </tr>
            </tbody>
        </table>

        <div style="text-align:right; margin-top:12px; font-size:16px; font-weight:bold; color:#D5006D;">
            TOTAL: $ ${fmtMoney(p.precio_final)}
        </div>

        <div style="margin-top:80px; display:flex; justify-content:space-between; align-items:flex-end;">
            <div style="font-size:12px; color:#666;">Válido por 15 días</div>
            <div style="text-align:center;">
                <div style="border-top:1px solid #333; width:220px; margin-bottom:4px;"></div>
                <div style="font-size:12px; color:#666;">Firma</div>
            </div>
        </div>

        <div style="margin-top:60px; border-top:1px solid #ddd; padding-top:10px; text-align:center; font-size:11px; color:#777;">
            <div>Grafica Viamonte de Soria Daniel Enrique</div>
            <div>igv.srl@hotmail.com | WhatsApp: +54 381 239-4798</div>
        </div>
    `;

    const nombreArchivo = `Presupuesto_${sanitizarNombreArchivo(nombreCliente)}_${fmtFechaArchivo(p.fecha_creacion)}.pdf`;
    html2pdf().set({ margin: 10, filename: nombreArchivo }).from(div).save();
}

// 2. PDF INTERNO (Detalle de todos los costos e ítems del formulario)
async function generarPDFInterno(presupuesto_id) {
    const { p, c } = await armarMoldeBasePDF(presupuesto_id);
    const nombreCliente = c ? c.nombre_completo : 'Sin cliente';
    const shortId = p.id.substring(0,6).toUpperCase();

    let filasCostos = '';
    for (const [item, monto] of Object.entries(p.detalles_costos || {})) {
        filasCostos += `<tr><td style="border:1px solid #ddd; padding:8px;">${item}</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$ ${fmtMoney(monto)}</td></tr>`;
    }
    if (!filasCostos) filasCostos = `<tr><td colspan="2" style="border:1px solid #ddd; padding:8px; color:#999;">Sin costos cargados</td></tr>`;

    const div = document.createElement('div');
    div.style.padding = '40px'; div.style.fontFamily = 'Arial';
    div.innerHTML = `
        <h2 style="margin-bottom:6px;">[INTERNO] Hoja de Costos - #${shortId}</h2>
        <p style="font-size:13px; margin:2px 0;"><b>Cliente:</b> ${nombreCliente}</p>
        <p style="font-size:13px; margin:2px 0;"><b>Producto:</b> ${p.descripcion}</p>
        <p style="font-size:13px; margin:2px 0;"><b>Material:</b> ${p.material || '-'} &nbsp;|&nbsp; <b>Gramaje:</b> ${p.gramaje ? p.gramaje + ' g/m²' : '-'}</p>
        <p style="font-size:13px; margin:2px 0;"><b>Cantidad de pliegos:</b> ${p.cantidad}</p>
        <table style="width:100%; border-collapse:collapse; margin-top:18px; font-size:13px;">
            <tr style="background:#eee;"><th style="border:1px solid #ddd; padding:8px; text-align:left;">Ítem de Costo</th><th style="border:1px solid #ddd; padding:8px; text-align:right;">Monto</th></tr>
            ${filasCostos}
            <tr style="background:#ffe6f2;"><td style="border:1px solid #ddd; padding:8px;"><b>SUBTOTAL COSTOS</b></td><td style="border:1px solid #ddd; padding:8px; text-align:right;"><b>$ ${fmtMoney(p.costo_materiales)}</b></td></tr>
            <tr><td style="border:1px solid #ddd; padding:8px;">Ganancia Aplicada (${p.margen_ganancia}%)</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$ ${fmtMoney(Number(p.precio_final) - Number(p.costo_materiales))}</td></tr>
        </table>
        <h3 style="text-align:right; color:#D5006D; margin-top:20px;">PRECIO FINAL COBRADO: $ ${fmtMoney(p.precio_final)}</h3>
    `;
    html2pdf().set({ margin: 10, filename: `Costos_Internos_${shortId}.pdf` }).from(div).save();
}

// Informe general de trabajos a clientes. Se arma desde los presupuestos
// (el backend cruza el trabajo asociado y calcula cobrado/días de producción).
async function generarInformeTrabajosPDF() {
    try {
        const resp = await fetch(`${API_URL}/presupuestos/informe-trabajos`);
        if (!resp.ok) throw new Error('No se pudo generar el informe.');
        const filas = await resp.json();

        if (!filas.length) {
            Swal.fire('Sin datos', 'Todavía no hay presupuestos para informar.', 'info');
            return;
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'landscape' });

        doc.setFontSize(18);
        doc.setTextColor(213, 0, 109);
        doc.text('Gráfica Viamonte', 14, 16);
        doc.setFontSize(12);
        doc.setTextColor(50, 50, 50);
        doc.text('Informe general de trabajos a clientes', 14, 23);
        doc.setFontSize(9);
        doc.setTextColor(120, 120, 120);
        doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-AR')}`, 14, 29);

        doc.autoTable({
            startY: 34,
            head: [['Nro Trabajo', 'Fecha entrada', 'Cliente', 'Descripción material', 'Gramaje', 'Colores', 'Cantidad', 'Fecha entrega', 'Días prod.', 'Estado', 'Cobrado', 'Observaciones']],
            body: filas.map(f => [
                f.nro_trabajo,
                f.fecha_entrada,
                f.cliente,
                f.descripcion_material,
                f.gramaje,
                f.colores,
                f.cantidad,
                f.fecha_entrega,
                f.dias_produccion,
                f.estado,
                f.cobrado ? 'Sí' : 'No',
                f.observaciones
            ]),
            theme: 'grid',
            headStyles: { fillColor: [40, 40, 40], fontSize: 8, halign: 'center' },
            bodyStyles: { fontSize: 8, textColor: [50, 50, 50] },
            alternateRowStyles: { fillColor: [245, 245, 245] },
            columnStyles: {
                6: { halign: 'center' },
                8: { halign: 'center' },
                10: { halign: 'center' }
            }
        });

        doc.save(`Informe_Trabajos_Clientes_${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (e) {
        console.error(e);
        Swal.fire('No se pudo generar el informe', e.message, 'error');
    }
}

// ==========================================
// MÓDULO DE GASTOS
// ==========================================

let idGastoEditando = null;
// Última lista de trabajos traída para el select del drawer. La guardamos para
// que editarGasto pueda recuperar un trabajo ya entregado sin pedirla de nuevo.
let trabajosParaGasto = [];
// Categoría cuyo costo ya está contemplado en el margen del presupuesto.
// Mismo valor que CATEGORIA_COSTO_PRESUPUESTADO en calculos.py.
const CATEGORIA_COSTO_PRESUPUESTADO = 'Costo Presupuestado';

// Muestra la aclaración de la categoría sólo cuando aplica.
function actualizarAyudaCategoriaGasto() {
    const ayuda = document.getElementById('fg_ayuda_categoria');
    if (!ayuda) return;
    const esCosteado = document.getElementById('fg_categoria').value === CATEGORIA_COSTO_PRESUPUESTADO;
    ayuda.style.display = esCosteado ? 'block' : 'none';
}

async function abrirDrawerGasto() {
    idGastoEditando = null;
    document.getElementById('titulo-drawer-gasto').innerText = 'Registrar Salida de Dinero';
    document.getElementById('form-gasto').reset();
    document.getElementById('fg_fecha').value = new Date().toISOString().split('T')[0];

    try {
        const respT = await fetch(`${API_URL}/trabajos/`);
        if (respT.ok) {
            const trabajos = await respT.json();
            trabajosParaGasto = trabajos;
            const selectT = document.getElementById('fg_trabajo_id');
            selectT.innerHTML = '<option value="">Ninguno (Gasto general del taller)</option>';
            
            // Filtramos para mostrar solo los que están en proceso (Aprobados, en Diseño, etc.)
            const activos = trabajos.filter(t => t.estado !== 'Entregado' && t.estado !== 'Cancelado').reverse();
            activos.forEach(t => {
                const shortId = t.id.substring(0,6).toUpperCase();
                selectT.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</option>`;
            });
        }
    } catch(e) { console.error(e); }

    actualizarAyudaCategoriaGasto();
    toggleDrawer('drawer-nuevo-gasto');
}

// El select sólo lista trabajos activos, así que un gasto de un trabajo ya
// entregado no encontraría su opción y el vínculo se perdería en silencio al
// guardar. Le agregamos la opción que falta para que eso no pase.
function asegurarOpcionTrabajoGasto(trabajoId) {
    const selectT = document.getElementById('fg_trabajo_id');
    if (!trabajoId || selectT.querySelector(`option[value="${trabajoId}"]`)) return;

    const t = trabajosParaGasto.find(x => x.id === trabajoId);
    const shortId = trabajoId.substring(0, 6).toUpperCase();
    const detalle = t ? `${t.cantidad}x ${t.descripcion_producto}` : 'trabajo no encontrado';
    const estado = t ? t.estado.toLowerCase() : 'sin datos';
    selectT.innerHTML += `<option value="${trabajoId}">(${estado}) #${shortId} - ${detalle}</option>`;
}

// Abre el drawer de gasto en modo edición, precargado con los datos del gasto elegido
async function editarGasto(id) {
    try {
        const resp = await fetch(`${API_URL}/gastos/`);
        const gastos = await resp.json();
        const g = gastos.find(x => x.id === id);
        if (!g) return;

        await abrirDrawerGasto(); // Prepara el drawer (llena el select de trabajos y resetea)
        idGastoEditando = id;
        document.getElementById('titulo-drawer-gasto').innerText = 'Editar Gasto';

        document.getElementById('fg_categoria').value = g.categoria;
        document.getElementById('fg_concepto').value = g.concepto;
        asegurarOpcionTrabajoGasto(g.trabajo_id);
        document.getElementById('fg_trabajo_id').value = g.trabajo_id || '';
        document.getElementById('fg_metodo').value = g.metodo_pago;
        document.getElementById('fg_comprobante').value = g.comprobante;
        document.getElementById('fg_responsable').value = g.responsable || 'General';
        document.getElementById('fg_monto').value = g.monto;
        document.getElementById('fg_fecha').value = g.fecha;
        actualizarAyudaCategoriaGasto();
    } catch (e) { console.error("Error al abrir edición de gasto:", e); }
}

async function cargarGastos() {
    try {
        const resp = await fetch(`${API_URL}/gastos/`);
        if (!resp.ok) return;
        
        let gastos = await resp.json();
        
        // 1. LEER LOS FILTROS
        const filtroMes = document.getElementById('filtro-mes-gasto').value;
        const filtroCat = document.getElementById('filtro-cat-gasto').value;

        // 2. APLICAR FILTROS DE TIEMPO Y CATEGORÍA
        const hoy = new Date();
        const mesActual = hoy.getMonth();
        const anioActual = hoy.getFullYear();

        gastos = gastos.filter(g => {
            // El truco de + 'T00:00:00' es para que no se desfase por la zona horaria argentina
            const fechaG = new Date(g.fecha + 'T00:00:00'); 
            
            let pasaMes = true;
            if (filtroMes === 'este_mes') {
                pasaMes = (fechaG.getMonth() === mesActual && fechaG.getFullYear() === anioActual);
            } else if (filtroMes === 'mes_pasado') {
                let mesPasado = mesActual - 1;
                let anioPasado = anioActual;
                if (mesPasado < 0) { mesPasado = 11; anioPasado--; } // Si estamos en Enero, pasa a Diciembre del año anterior
                pasaMes = (fechaG.getMonth() === mesPasado && fechaG.getFullYear() === anioPasado);
            }

            let pasaCat = true;
            if (filtroCat !== 'todas') {
                pasaCat = (g.categoria === filtroCat);
            }

            return pasaMes && pasaCat;
        });

        // 3. RENDERIZAR TABLA Y SUMAR TOTAL
        const tbody = document.querySelector('#tableGastos tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        let sumaTotal = 0;

        if (gastos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No hay gastos registrados para este filtro.</td></tr>';
            document.getElementById('lbl-total-gastos').innerText = '$ 0';
            return;
        }

        gastos.forEach(g => {
            sumaTotal += Number(g.monto); // Vamos sumando la plata

            let colorCat = 'var(--ink)';
            if(g.categoria === 'Insumos') colorCat = 'var(--blue)';
            else if(g.categoria === 'Servicios') colorCat = 'var(--amber)';
            else if(g.categoria === 'Sueldos') colorCat = 'var(--magenta)';
            else if(g.categoria === CATEGORIA_COSTO_PRESUPUESTADO) colorCat = 'var(--green)';

            // Novedad: Etiqueta visual de asociación
            let badgeTrabajo = '';
            if (g.trabajo_id) {
                const shortId = g.trabajo_id.substring(0,6).toUpperCase();
                badgeTrabajo = `<span style="font-size:10px; background:var(--magenta-soft); color:var(--magenta); padding:2px 4px; border-radius:4px; margin-left:6px;">🔗 Trabajo #${shortId}</span>`;
            }

            tbody.innerHTML += `
                <tr>
                    <td>${new Date(g.fecha + 'T00:00:00').toLocaleDateString('es-AR')}</td>
                    <td><span style="background:var(--paper); color:${colorCat}; font-weight:600; padding:4px 8px; border-radius:4px; font-size:12px;">${g.categoria}</span></td>
                    <td>
                        ${g.concepto} ${badgeTrabajo}<br>
                        <span style="font-size:10px; color:var(--muted); display:inline-block; margin-top:4px;">
                            💳 ${g.metodo_pago} | 🧾 ${g.comprobante} | 👤 ${g.responsable || 'General'}
                        </span>
                    </td>
                    <td class="tnum" style="color:var(--red); font-weight:bold;">$ ${fmtMoney(g.monto)}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarGasto('${g.id}')">✏️ Editar</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarGasto('${g.id}', this)">🗑️ Borrar</button>
                    </td>
                </tr>
            `;
        });

        // 4. ACTUALIZAR EL TOTAL EN PANTALLA
        document.getElementById('lbl-total-gastos').innerText = `$ ${fmtMoney(sumaTotal)}`;

    } catch (e) {
        console.error("Error cargando gastos:", e);
    }
}

async function guardarGasto(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const tr_id = document.getElementById('fg_trabajo_id').value;
    const montoGasto = parseFloat(document.getElementById('fg_monto').value);

    // El gasto tiene que ser un número mayor a 0.
    if (isNaN(montoGasto) || montoGasto <= 0) {
        Swal.fire('Monto inválido', 'El gasto tiene que ser un número mayor a 0.', 'warning');
        restore();
        return;
    }

    // Un costo presupuestado no resta de la ganancia: sin trabajo asociado no
    // hay margen contra el cual compensarlo y el gasto desaparecería del cálculo.
    const categoria = document.getElementById('fg_categoria').value;
    if (categoria === CATEGORIA_COSTO_PRESUPUESTADO && !tr_id) {
        Swal.fire(
            'Falta el trabajo',
            'Un gasto de categoría "Costo Presupuestado" tiene que estar asociado a un trabajo, porque su costo ya está contemplado en ese presupuesto. Si es un gasto general del taller, elegí otra categoría.',
            'warning'
        );
        restore();
        return;
    }

    const payload = {
        categoria: categoria,
        concepto: document.getElementById('fg_concepto').value,
        monto: montoGasto,
        fecha: document.getElementById('fg_fecha').value,
        metodo_pago: document.getElementById('fg_metodo').value,
        comprobante: document.getElementById('fg_comprobante').value,
        responsable: document.getElementById('fg_responsable').value,
        trabajo_id: tr_id ? tr_id : null
    };

    try {
        const url = idGastoEditando ? `${API_URL}/gastos/${idGastoEditando}` : `${API_URL}/gastos/`;
        const metodo = idGastoEditando ? 'PUT' : 'POST';
        const resp = await fetch(url, {
            method: metodo,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            const titulo = idGastoEditando ? '¡Gasto actualizado!' : '¡Salida registrada!';
            idGastoEditando = null;
            toggleDrawer('drawer-nuevo-gasto');
            cargarGastos();
            Swal.fire({ title: titulo, icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar', error.detail || 'Revisá los datos e intentá de nuevo.', 'error');
        }
    } catch (error) {
        console.error("Error al guardar gasto:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar el gasto.', 'error');
    } finally {
        restore();
    }
}

const MESES_INFORME = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

// Abre un selector de mes/año y genera el informe imprimible de gastos.
async function abrirInformeGastos() {
    const hoy = new Date();
    const opcionesMes = MESES_INFORME
        .map((m, i) => `<option value="${i}" ${i === hoy.getMonth() ? 'selected' : ''}>${m}</option>`)
        .join('');

    const { value: datos } = await Swal.fire({
        title: 'Informe de Gastos',
        html: `
            <p style="font-size:13px; color:#666; margin-bottom:12px;">Elegí el período a imprimir.</p>
            <select id="inf-mes" class="swal2-input" style="width:auto;">${opcionesMes}</select>
            <input id="inf-anio" type="number" class="swal2-input" style="width:120px;" value="${hoy.getFullYear()}">
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Generar PDF',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#D5006D',
        preConfirm: () => {
            const mes = parseInt(document.getElementById('inf-mes').value, 10);
            const anio = parseInt(document.getElementById('inf-anio').value, 10);
            if (isNaN(anio) || anio < 2000) {
                Swal.showValidationMessage('Ingresá un año válido.');
                return false;
            }
            return { mes, anio };
        }
    });

    if (datos) generarInformeGastos(datos.mes, datos.anio);
}

async function generarInformeGastos(mes, anio) {
    try {
        const resp = await fetch(`${API_URL}/gastos/`);
        if (!resp.ok) throw new Error('No se pudieron traer los gastos.');
        const gastos = await resp.json();

        // Filtramos por mes/año (el + 'T00:00:00' evita el desfase de zona horaria).
        const delPeriodo = gastos.filter(g => {
            const f = new Date(g.fecha + 'T00:00:00');
            return f.getMonth() === mes && f.getFullYear() === anio;
        }).sort((a, b) => new Date(a.fecha) - new Date(b.fecha));

        if (delPeriodo.length === 0) {
            Swal.fire('Sin datos', `No hay gastos registrados en ${MESES_INFORME[mes]} ${anio}.`, 'info');
            return;
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        doc.setFontSize(22);
        doc.setTextColor(213, 0, 109);
        doc.text('Gráfica Viamonte', 14, 20);

        doc.setFontSize(14);
        doc.setTextColor(50, 50, 50);
        doc.text('Informe de Gastos', 14, 29);

        doc.setFontSize(11);
        doc.setTextColor(100, 100, 100);
        doc.text(`Período: ${MESES_INFORME[mes]} ${anio}`, 14, 37);
        doc.text(`Emitido: ${new Date().toLocaleDateString('es-AR')}`, 14, 43);

        let total = 0;
        const filas = delPeriodo.map(g => {
            total += Number(g.monto);
            return [
                new Date(g.fecha + 'T00:00:00').toLocaleDateString('es-AR'),
                g.concepto,
                g.categoria,
                g.responsable || 'General',
                `$ ${fmtMoney(g.monto)}`
            ];
        });

        doc.autoTable({
            startY: 50,
            head: [['Fecha', 'Concepto', 'Categoría', 'Responsable', 'Monto']],
            body: filas,
            foot: [['', '', '', 'TOTAL', `$ ${fmtMoney(total)}`]],
            theme: 'grid',
            headStyles: { fillColor: [40, 40, 40], fontSize: 11 },
            footStyles: { fillColor: [245, 245, 245], textColor: [213, 0, 109], fontStyle: 'bold' },
            bodyStyles: { fontSize: 10, textColor: [50, 50, 50] },
            alternateRowStyles: { fillColor: [248, 248, 248] },
            columnStyles: { 4: { halign: 'right', fontStyle: 'bold' } }
        });

        doc.save(`Informe_Gastos_${MESES_INFORME[mes]}_${anio}.pdf`);
    } catch (e) {
        console.error('Error generando informe de gastos:', e);
        Swal.fire('Error', 'No se pudo generar el informe.', 'error');
    }
}

async function eliminarGasto(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️ Borrar';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este gasto?',
        text: "Va a desaparecer del balance mensual.",
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
        await fetch(`${API_URL}/gastos/${id}`, { method: 'DELETE' });
        cargarGastos();
        Swal.fire('¡Eliminado!', 'El gasto fue borrado del sistema.', 'success');
    } catch (e) {
        console.error("Error al eliminar gasto:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// ==========================================
// MÓDULO DE STOCK E INVENTARIO
// ==========================================

let idStockEditando = null;
let carritoCompras = [];      // ítems pendientes de enviar a POST /stock/compras
let stockCacheCompras = [];   // artículos existentes para el selector de recompra

function abrirDrawerStock() {
    idStockEditando = null;
    carritoCompras = [];
    document.getElementById('titulo-drawer-stock').innerText = 'Registrar Compra';
    document.getElementById('form-stock').reset();
    cargarArticulosExistentes();
    setModoEdicionStock(false);
    onArticuloExistenteChange(); // restaura visibilidad de todos los grupos (llama a onUnidadStockChange)
    renderCarritoStock();
    toggleDrawer('drawer-nuevo-stock');
}

async function cargarArticulosExistentes() {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        stockCacheCompras = await resp.json();
        const sel = document.getElementById('fs_articulo_existente');
        sel.innerHTML = '<option value="">— Artículo nuevo —</option>' +
            stockCacheCompras.map(a => `<option value="${a.id}">${esc(a.nombre)} (${a.cantidad} ${a.unidad})</option>`).join('');
    } catch (e) { console.error("Error cargando artículos existentes:", e); }
}

// Muestra u oculta un bloque del form de stock.
function setVisibleStock(idGrupo, visible) {
    document.getElementById(idGrupo).style.display = visible ? '' : 'none';
}

function setModoEdicionStock(editando) {
    setVisibleStock('grupo-stock-existente', !editando);
    document.getElementById('btn-agregar-carrito').style.display = editando ? 'none' : '';
    document.getElementById('btn-guardar-stock').innerText = editando ? 'Guardar cambios' : 'Registrar compra';
    if (editando) setVisibleStock('carrito-stock', false);
}

function onArticuloExistenteChange() {
    const id = document.getElementById('fs_articulo_existente').value;
    const esRecompra = !!id;
    // El nombre, la categoría y el mínimo pertenecen a la ficha: en recompra no se tocan.
    setVisibleStock('grupo-stock-nombre', !esRecompra);
    setVisibleStock('grupo-stock-datos', !esRecompra);
    setVisibleStock('grupo-stock-minimo', !esRecompra);
    if (esRecompra) {
        const art = stockCacheCompras.find(a => a.id === id);
        if (art) {
            const tieneDimensiones = art.largo_cm && art.ancho_cm && art.gramaje_grs;
            document.getElementById('fs_unidad').value = tieneDimensiones ? 'Kg' : art.unidad;
            document.getElementById('fs_largo').value = art.largo_cm || '';
            document.getElementById('fs_ancho').value = art.ancho_cm || '';
            document.getElementById('fs_gramaje').value = art.gramaje_grs || '';
        }
    }
    onUnidadStockChange();
}

function onUnidadStockChange() {
    const esKg = document.getElementById('fs_unidad').value === 'Kg';
    const editandoConDims = !!idStockEditando && document.getElementById('fs_largo').value !== '';
    setVisibleStock('grupo-stock-kg', esKg || editandoConDims);
    setVisibleStock('grupo-stock-peso', esKg);
    setVisibleStock('grupo-stock-cantidad', !esKg);
    document.getElementById('lbl-fs-costo').innerText = esKg ? 'Costo total del paquete ($)' : 'Costo Unit. ($)';
}

// Arma el ítem de compra a partir del form. Devuelve null (con aviso) si falta algo.
function armarItemCompraStock() {
    const articuloId = document.getElementById('fs_articulo_existente').value || null;
    const unidad = document.getElementById('fs_unidad').value;
    const esKg = unidad === 'Kg';
    const nombre = document.getElementById('fs_nombre').value.trim();

    if (!articuloId && !nombre) {
        Swal.fire({ title: 'Falta el nombre', text: 'Ingresá el nombre del insumo o elegí un artículo existente.', icon: 'warning' });
        return null;
    }

    const item = { articulo_id: articuloId, unidad: unidad };
    if (!articuloId) {
        item.nombre = nombre;
        item.categoria = document.getElementById('fs_categoria').value;
        item.proveedor = document.getElementById('fs_proveedor').value || null;
        item.stock_minimo = parseFloat(document.getElementById('fs_minimo').value) || 0;
    }

    const costo = parseFloat(document.getElementById('fs_costo').value);
    if (esKg) {
        item.largo_cm = parseFloat(document.getElementById('fs_largo').value);
        item.ancho_cm = parseFloat(document.getElementById('fs_ancho').value);
        item.gramaje_grs = parseFloat(document.getElementById('fs_gramaje').value);
        item.peso_total_kg = parseFloat(document.getElementById('fs_peso').value);
        if (!(item.largo_cm > 0) || !(item.ancho_cm > 0) || !(item.gramaje_grs > 0) || !(item.peso_total_kg > 0)) {
            Swal.fire({ title: 'Faltan datos del papel', text: 'Para comprar por Kg completá largo, ancho, gramaje y peso del paquete.', icon: 'warning' });
            return null;
        }
        if (costo > 0) item.costo_total = costo;
    } else {
        item.cantidad = parseFloat(document.getElementById('fs_cantidad').value);
        if (!(item.cantidad > 0)) {
            Swal.fire({ title: 'Cantidad inválida', text: 'La cantidad debe ser mayor a cero.', icon: 'warning' });
            return null;
        }
        if (!isNaN(costo)) item.costo_unitario = costo;
    }

    const art = articuloId ? stockCacheCompras.find(a => a.id === articuloId) : null;
    item._etiqueta = `${art ? art.nombre : nombre} — ${esKg ? item.peso_total_kg + ' Kg' : item.cantidad + ' ' + unidad}`;
    return item;
}

function agregarAlCarritoStock() {
    const item = armarItemCompraStock();
    if (!item) return;
    carritoCompras.push(item);
    renderCarritoStock();
    // Form limpio para cargar el siguiente ítem
    document.getElementById('form-stock').reset();
    onArticuloExistenteChange();
}

function quitarDelCarritoStock(indice) {
    carritoCompras.splice(indice, 1);
    renderCarritoStock();
}

function renderCarritoStock() {
    const lista = document.getElementById('carrito-stock-lista');
    const btn = document.getElementById('btn-guardar-stock');
    if (carritoCompras.length === 0) {
        setVisibleStock('carrito-stock', false);
        btn.innerText = 'Registrar compra';
        return;
    }
    setVisibleStock('carrito-stock', true);
    lista.innerHTML = carritoCompras.map((item, i) => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--line); font-size:13px;">
            <span>${item._etiqueta}</span>
            <button type="button" class="btn secondary" style="font-size:11px; padding:2px 6px;" onclick="quitarDelCarritoStock(${i})">✖</button>
        </div>`).join('');
    btn.innerText = `Registrar compra (${carritoCompras.length})`;
}

async function editarArticuloStock(id) {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        const stock = await resp.json();
        const art = stock.find(s => s.id === id);
        if (!art) return;

        document.getElementById('form-stock').reset();
        idStockEditando = id;
        carritoCompras = [];
        document.getElementById('titulo-drawer-stock').innerText = 'Editar Insumo';

        document.getElementById('fs_nombre').value = art.nombre;
        document.getElementById('fs_categoria').value = art.categoria;
        document.getElementById('fs_proveedor').value = art.proveedor || '';
        document.getElementById('fs_unidad').value = art.unidad;
        document.getElementById('fs_costo').value = art.costo_unitario;
        document.getElementById('fs_cantidad').value = art.cantidad;
        document.getElementById('fs_minimo').value = art.stock_minimo;
        document.getElementById('fs_largo').value = art.largo_cm || '';
        document.getElementById('fs_ancho').value = art.ancho_cm || '';
        document.getElementById('fs_gramaje').value = art.gramaje_grs || '';

        setModoEdicionStock(true);
        setVisibleStock('grupo-stock-nombre', true);
        setVisibleStock('grupo-stock-datos', true);
        setVisibleStock('grupo-stock-minimo', true);
        onUnidadStockChange();
        toggleDrawer('drawer-nuevo-stock');
    } catch (e) { console.error("Error al abrir edición de stock:", e); }
}

async function guardarArticuloStock(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);

    try {
        if (idStockEditando) {
            // Edición: PATCH con los campos descriptivos + cantidad (queda registrada en el historial si cambió).
            const largo = document.getElementById('fs_largo').value;
            const ancho = document.getElementById('fs_ancho').value;
            const gramaje = document.getElementById('fs_gramaje').value;
            const payload = {
                nombre: document.getElementById('fs_nombre').value,
                categoria: document.getElementById('fs_categoria').value,
                proveedor: document.getElementById('fs_proveedor').value || null,
                unidad: document.getElementById('fs_unidad').value,
                stock_minimo: parseFloat(document.getElementById('fs_minimo').value),
                costo_unitario: parseFloat(document.getElementById('fs_costo').value),
                cantidad: parseFloat(document.getElementById('fs_cantidad').value),
                largo_cm: largo ? parseFloat(largo) : null,
                ancho_cm: ancho ? parseFloat(ancho) : null,
                gramaje_grs: gramaje ? parseFloat(gramaje) : null,
                motivo: "Corrección por edición de ficha"
            };
            const resp = await fetch(`${API_URL}/stock/${idStockEditando}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                idStockEditando = null;
                toggleDrawer('drawer-nuevo-stock');
                cargarStock();
                Swal.fire({ title: 'Artículo actualizado', icon: 'success', timer: 1000, showConfirmButton: false });
            }
        } else {
            // Si el form tiene un ítem a medio cargar (o el carrito está vacío), se suma solo.
            const formTieneDatos = document.getElementById('fs_nombre').value.trim() !== '' ||
                document.getElementById('fs_articulo_existente').value !== '';
            if (carritoCompras.length === 0 || formTieneDatos) {
                const item = armarItemCompraStock();
                if (!item) return; // el aviso ya se mostró
                carritoCompras.push(item);
                renderCarritoStock();
            }

            // _etiqueta es solo para la UI del carrito: no se manda al backend.
            const payload = carritoCompras.map(({ _etiqueta, ...item }) => item);
            const resp = await fetch(`${API_URL}/stock/compras`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                carritoCompras = [];
                toggleDrawer('drawer-nuevo-stock');
                cargarStock();
                cargarSelectoresPapel(); // el stock de papel pudo cambiar
                Swal.fire({ title: 'Compra registrada', icon: 'success', timer: 1200, showConfirmButton: false });
            } else {
                const err = await resp.json().catch(() => ({}));
                Swal.fire({ title: 'No se pudo registrar la compra', text: err.detail || 'Error inesperado', icon: 'error' });
            }
        }
    } catch (error) { console.error("Error guardando stock:", error); }
    finally { restore(); }
}

async function eliminarArticuloStock(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este artículo?',
        text: "También se borra su historial de ajustes.",
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
        const resp = await fetch(`${API_URL}/stock/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            cargarStock();
            Swal.fire('¡Eliminado!', 'El artículo fue borrado del inventario.', 'success');
        }
    } catch (e) {
        console.error("Error al eliminar artículo:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

async function cargarStock() {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        if (!resp.ok) return;
        
        const stock = await resp.json();
        const tbody = document.querySelector('#tableStock tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        let capitalTotal = 0;
        let alertasTotales = 0;

        if (stock.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--muted);">Inventario vacío.</td></tr>';
            document.getElementById('lbl-valor-inventario').innerText = '$ 0';
            document.getElementById('lbl-alertas-stock').innerText = '0';
            return;
        }

        stock.forEach(s => {
            // Cálculos para la cabecera
            capitalTotal += (Number(s.cantidad) * Number(s.costo_unitario));
            const enAlerta = Number(s.cantidad) <= Number(s.stock_minimo);
            if (enAlerta) alertasTotales++;

            let badgeEstado = enAlerta
                ? `<span style="background:var(--red); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">¡COMPRAR!</span>`
                : `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">Suficiente</span>`;
            
            // Le agregamos un botón de historial
            badgeEstado += `<br><button class="btn secondary" style="font-size:10px; padding:2px 4px; margin-top:5px;" onclick="verHistorialStock('${s.id}', '${s.nombre}')">Ver Historial</button>`;

            // EL SISTEMA HÍBRIDO DE CANTIDAD: Botones y tipeo manual
            const controlCantidad = `
                <div style="display:flex; align-items:center; justify-content:center; gap:5px;">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, -1, '${s.unidad}', this)">-</button>
                    <input type="number" id="stk-input-${s.id}" value="${s.cantidad}" style="width:70px; text-align:center; padding:5px; border:1px solid var(--line); border-radius:4px;" onchange="ajustarStockRapido('${s.id}', ${s.cantidad}, 'manual', '${s.unidad}', this)">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, 1, '${s.unidad}', this)">+</button>
                    <span style="font-size:11px; color:var(--muted);">${s.unidad}</span>
                </div>
            `;

            tbody.innerHTML += `
                <tr style="${enAlerta ? 'background-color: var(--red-soft);' : ''}">
                    <td><b>${s.nombre}</b></td>
                    <td>
                        <span style="font-size:11px; color:var(--ink); font-weight:600;">${s.categoria}</span><br>
                        <span style="font-size:11px; color:var(--muted);">🏭 ${s.proveedor || 'Sin proveedor'}</span>
                    </td>
                    <td class="tnum" style="text-align:center;">$ ${fmtMoney(s.costo_unitario)}</td>
                    <td style="text-align:center;">${controlCantidad}</td>
                    <td style="text-align:center;">${badgeEstado}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarArticuloStock('${s.id}')">✏️</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarArticuloStock('${s.id}', this)">🗑️</button>
                    </td>
                </tr>
            `;
        });

        // Refrescar paneles
        document.getElementById('lbl-valor-inventario').innerText = `$ ${fmtMoney(capitalTotal)}`;
        document.getElementById('lbl-alertas-stock').innerText = alertasTotales;

    } catch (e) { console.error("Error cargando stock:", e); }
}

async function ajustarStockRapido(id, cantidadActual, accion, unidad, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || (accion === 1 ? '+' : '-');

    let nuevaCantidad;
    let motivo = "Ajuste rápido";

    if (accion === 'manual') {
        nuevaCantidad = parseFloat(document.getElementById(`stk-input-${id}`).value) || 0;
        if (nuevaCantidad === cantidadActual) return;

        const dif = nuevaCantidad - cantidadActual;
        const textoDif = dif > 0 ? `Ingreso de +${dif}` : `Salida de ${dif}`;

        const { value: razon, isDismissed } = await Swal.fire({
            title: 'Justificar movimiento',
            text: `Estás haciendo un ${textoDif} ${unidad}. ¿Cuál es el motivo? (Ej: Compra, Uso en Trabajo #123, Rotura)`,
            input: 'text',
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            inputValidator: (value) => {
                if (!value) return '¡Tenés que escribir un motivo!'
            }
        });

        if (isDismissed) {
            cargarStock();
            return;
        }
        motivo = razon;
    } else {
        nuevaCantidad = cantidadActual + accion;
        motivo = accion > 0 ? "Ajuste manual rápido (+1)" : "Ajuste manual rápido (-1)";
    }

    if (nuevaCantidad < 0) nuevaCantidad = 0;

    if (button) {
        button.disabled = true;
        button.innerText = 'Actualizando...';
    }

    try {
        const resp = await fetch(`${API_URL}/stock/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: nuevaCantidad, motivo: motivo })
        });

        if (resp.ok) cargarStock();
    } catch (e) { console.error("Error actualizando cantidad:", e); }
    finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}


// NUEVA FUNCIÓN: Ver Historial (Pop-up lindo)
async function verHistorialStock(id, nombreArticulo) {
    try {
        const resp = await fetch(`${API_URL}/stock/${id}/historial`);
        const historial = await resp.json();
        
        if (historial.length === 0) {
            Swal.fire('Historial', 'No hay movimientos registrados para este artículo.', 'info');
            return;
        }

        let htmlLista = '<div style="max-height: 300px; overflow-y: auto; text-align: left;">';
        htmlLista += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">';
        htmlLista += '<tr style="border-bottom: 1px solid #ddd; color: #666;"><th>Fecha</th><th>Movimiento</th><th>Motivo</th></tr>';
        
        historial.forEach(h => {
            const fechaLocale = new Date(h.fecha).toLocaleString('es-AR', {dateStyle: 'short', timeStyle: 'short'});
            const colorDif = h.diferencia > 0 ? 'var(--green)' : 'var(--red)';
            const signo = h.diferencia > 0 ? '+' : '';
            
            htmlLista += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 4px;">${fechaLocale}</td>
                    <td style="padding: 8px 4px; color: ${colorDif}; font-weight: bold;">${signo}${h.diferencia}</td>
                    <td style="padding: 8px 4px;">${h.motivo}</td>
                </tr>
            `;
        });
        htmlLista += '</table></div>';

        Swal.fire({
            title: `Historial: ${nombreArticulo}`,
            html: htmlLista,
            width: 600,
            confirmButtonColor: '#D5006D',
            confirmButtonText: 'Cerrar'
        });

    } catch(e) { console.error("Error trayendo historial:", e); }
}

// ==========================================
// MÓDULO DASHBOARD Y ESTADÍSTICAS
// ==========================================

let miChartFlujo = null;
let miChartDistribucion = null;

async function cargarDashboard() {
    try {
        // 1. Traemos toda la info de la base de datos
        const [respT, respG, respC, respCl, respM] = await Promise.all([
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/gastos/`),
            fetch(`${API_URL}/cheques/`),       // <-- NUEVO
            fetch(`${API_URL}/clientes/`),      // <-- NUEVO
            fetch(`${API_URL}/movimientos/`)    // <-- para restar pagos en "morosos"
        ]);

        let trabajos = await respT.json();
        let gastos = await respG.json();
        let cheques = await respC.json();
        let clientes = await respCl.json();
        let movimientos = respM.ok ? await respM.json() : [];

        // LOGICA DE CHEQUES
        let plataEnCheques = 0;
        let plataChequesAPagar = 0;
        let htmlAlertasCheques = '';
        const hoyMs = new Date().getTime();
        const limiteMs = hoyMs + (7 * 24 * 60 * 60 * 1000); // 7 días para adelante

        cheques.forEach(ch => {
            // Sólo los recibidos son plata por cobrar: un cheque propio en cartera
            // es plata que va a SALIR, mostrarlo acá infla la caja esperada.
            const esRecibido = (ch.clasificacion || 'Recibido') === 'Recibido';
            if (ch.estado === 'En Cartera' && esRecibido) {
                plataEnCheques += Number(ch.monto);

                const fechaCobroDate = new Date(ch.fecha_cobro + 'T00:00:00');
                if (fechaCobroDate.getTime() <= limiteMs) {
                    const cli = clientes.find(c => c.id === ch.cliente_id);
                    const nomCli = cli ? (cli.nombre_completo || cli.nombre || 'Desc.') : 'Desc.';
                    const esVencido = fechaCobroDate.getTime() < hoyMs ? 'color:var(--red);' : '';
                    
                    htmlAlertasCheques += `
                        <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                            <span style="${esVencido}">📅 ${fechaCobroDate.toLocaleDateString('es-AR')} - ${esc(nomCli)}</span>
                            <span style="font-weight:bold;">$ ${fmtMoney(ch.monto)}</span>
                        </div>
                    `;
                }
            } else if (ch.estado === 'En Cartera') {
                // Emitido en cartera: cheque propio que todavía no cobraron.
                plataChequesAPagar += Number(ch.monto);
            }
        });

        // 2. Leemos la "Máquina del tiempo"
        const filtro = document.getElementById('dash-filtro-tiempo').value;

        // KPIs financieros: fuente de verdad en el backend (plata realmente
        // cobrada, ganancia proporcional a lo cobrado y conteos de trabajos).
        let kpis = null;
        try {
            const respKpi = await fetch(`${API_URL}/reportes/dashboard?filtro=${encodeURIComponent(filtro)}`);
            if (respKpi.ok) kpis = await respKpi.json();
        } catch (e) { console.error('Error cargando KPIs del dashboard:', e); }

        const hoy = new Date();
        const mesActual = hoy.getMonth();
        const anioActual = hoy.getFullYear();

        // Funciones de ayuda para filtrar por fecha
        const cumpleFiltro = (fechaStr) => {
            if (filtro === 'historico') return true;
            const f = new Date(fechaStr + 'T00:00:00');
            if (filtro === 'este_mes') return f.getMonth() === mesActual && f.getFullYear() === anioActual;
            if (filtro === 'mes_pasado') {
                let m = mesActual - 1; let a = anioActual;
                if (m < 0) { m = 11; a--; }
                return f.getMonth() === m && f.getFullYear() === a;
            }
            if (filtro === 'este_anio') return f.getFullYear() === anioActual;
            return true;
        };

        // Aplicamos el filtro a las listas
        const trabajosFiltrados = trabajos.filter(t => cumpleFiltro(t.fecha_creacion));
        const gastosFiltrados = gastos.filter(g => cumpleFiltro(g.fecha));

        // Plata estancada: trabajos que todavía dan vueltas en el taller. Este sí
        // se calcula acá porque no depende de cobranzas, sólo del estado.
        let plataEstancada = 0;
        trabajosFiltrados.forEach(t => {
            if (t.estado === 'Aprobado' || t.estado === 'En Diseño' || t.estado === 'En Producción') {
                plataEstancada += Number(t.precio_venta);
            }
        });

        let gastosPorCat = {};
        gastosFiltrados.forEach(g => {
            gastosPorCat[g.categoria] = (gastosPorCat[g.categoria] || 0) + Number(g.monto);
        });

        // Los KPIs financieros salen SOLO del backend: ingresos = plata realmente
        // cobrada, ganancia = margen proporcional a lo cobrado − gastos, y morosos
        // que contemplan cheques recibidos. El cálculo local que había acá los
        // ignoraba y mostraba deuda inflada, así que ante un fallo preferimos
        // avisar antes que dibujar números equivocados.
        const avisoError = document.getElementById('dash-error');
        if (!kpis) {
            if (avisoError) avisoError.style.display = 'block';
            ['kpi-ingresos', 'kpi-egresos', 'kpi-ganancia', 'kpi-calle',
             'kpi-trabajos-pendientes', 'kpi-sin-presupuesto'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.innerText = '—';
            });
            document.getElementById('kpi-ganancia').style.color = 'var(--muted)';
            document.getElementById('kpi-ganancia-nota').innerText = '';
            document.getElementById('kpi-ingresos-nota').innerText = '';
            document.getElementById('lista-morosos').innerHTML =
                '<div style="color:var(--muted); margin-top:10px;">No se pudo calcular la deuda de clientes.</div>';
        } else {
            if (avisoError) avisoError.style.display = 'none';

            const ingresosReales = Number(kpis.ingresos);
            const egresosPeriodo = Number(kpis.egresos);
            const gananciaNeta = Number(kpis.ganancia_neta);
            // Parte de los egresos que no restó de la ganancia por estar ya contemplada
            // en el margen de un presupuesto. Explica por qué ganancia ≠ ingresos − egresos.
            const costosPresupuestados = Number(kpis.costos_presupuestados || 0);

            // Parte de lo cobrado que no está imputada a ningún trabajo (un pago a
            // cuenta, un cheque suelto). Es plata real, pero no aporta ganancia: sin
            // trabajo no hay presupuesto del cual sacar el costo. Se muestra para que
            // se pueda imputar después, en vez de quedar escondida en la diferencia
            // entre ingresos y ganancia.
            const sinImputar = Number(kpis.ingresos_sin_imputar || 0);
            document.getElementById('kpi-ingresos-nota').innerText = sinImputar > 0
                ? `Incluye $ ${fmtMoney(sinImputar)} sin imputar a un trabajo`
                : '';

            document.getElementById('kpi-ingresos').innerText = `$ ${fmtMoney(ingresosReales)}`;
            document.getElementById('kpi-egresos').innerText = `$ ${fmtMoney(egresosPeriodo)}`;
            document.getElementById('kpi-ganancia').innerText = `$ ${fmtMoney(gananciaNeta)}`;
            document.getElementById('kpi-ganancia').style.color = gananciaNeta >= 0 ? 'var(--magenta)' : 'var(--red)';
            document.getElementById('kpi-ganancia-nota').innerText = costosPresupuestados > 0
                ? `No descuenta $ ${fmtMoney(costosPresupuestados)} ya contemplados en presupuestos`
                : '';
            document.getElementById('kpi-calle').innerText = `$ ${fmtMoney(Number(kpis.plata_en_la_calle))}`;
            document.getElementById('kpi-trabajos-pendientes').innerText = kpis.trabajos_pendientes;
            document.getElementById('kpi-sin-presupuesto').innerText = kpis.trabajos_sin_presupuesto;

            const htmlMorosos = kpis.morosos.map(m => `
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                    <span><b>#${m.trabajo_id.substring(0,6).toUpperCase()}</b> - ${esc(m.descripcion_producto)}</span>
                    <span style="color:var(--red); font-weight:bold;">$ ${fmtMoney(Number(m.saldo_pendiente))}</span>
                </div>
            `).join('');
            document.getElementById('lista-morosos').innerHTML = htmlMorosos || '<div style="color:var(--green); font-weight:bold; margin-top:10px;">¡No hay morosos! 🎉 Todos los entregados están pagados.</div>';
        }

        // KPIs que no dependen del backend de reportes.
        document.getElementById('alerta-estancada').innerText = `$ ${fmtMoney(plataEstancada)}`;
        document.getElementById('kpi-cheques').innerText = `$ ${fmtMoney(plataEnCheques)}`;
        document.getElementById('kpi-cheques-pagar').innerText = `$ ${fmtMoney(plataChequesAPagar)}`;
        document.getElementById('alerta-cheques').innerHTML = htmlAlertasCheques || '<div style="color:var(--muted); margin-top:10px;">No hay cheques por vencer esta semana.</div>';

        // 4. CÁLCULO DE BLOQUE 2 (GRÁFICOS)
        dibujarGraficoDistribucion(gastosPorCat);

        // Para el gráfico de barras armamos el flujo anual (Agrupamos por mes).
        // Ingresos reales (pagos cobrados + cheques cobrados), mismos criterios
        // que el KPI, para no dejar dos definiciones de "ingreso" conviviendo.
        // Los gastos van SIN filtrar: el gráfico es anual y ya filtra por año.
        // Pasarle gastosFiltrados hacía que con "Este mes" se compararan gastos
        // de un mes contra ingresos de todo el año.
        dibujarGraficoFlujo(movimientos, cheques, gastos, anioActual);

    } catch (e) {
        console.error("Error cargando dashboard:", e);
    }
}

function dibujarGraficoDistribucion(gastosPorCat) {
    const ctx = document.getElementById('chartDistribucion').getContext('2d');
    if (miChartDistribucion) miChartDistribucion.destroy(); // Borra el anterior si existía

    const etiquetas = Object.keys(gastosPorCat);
    const valores = Object.values(gastosPorCat);

    miChartDistribucion = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: etiquetas,
            datasets: [{
                data: valores,
                backgroundColor: ['#D5006D', '#FFC107', '#007BFF', '#28A745', '#6C757D'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 } } }
            }
        }
    });
}

function dibujarGraficoFlujo(movimientos, cheques, gastos, anio) {
    const ctx = document.getElementById('chartFlujo').getContext('2d');
    if (miChartFlujo) miChartFlujo.destroy();

    // Arrays para los 12 meses
    const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    let ingresosMes = new Array(12).fill(0);
    let egresosMes = new Array(12).fill(0);

    // Ingreso real: pagos cobrados (método distinto de Cheque)...
    movimientos.forEach(m => {
        if (m.tipo !== 'Pago' || (m.metodo || '').toLowerCase() === 'cheque') return;
        // Sin 'T00:00:00' a propósito: m.fecha ya trae hora, y un ISO con hora y
        // sin zona lo parsea JS como local (los de gastos/cheques son sólo fecha
        // y sin el sufijo caerían en UTC, por eso ahí sí va).
        const f = new Date(m.fecha);
        if (!isNaN(f) && f.getFullYear() === anio) ingresosMes[f.getMonth()] += Number(m.monto);
    });
    // ...más los cheques recibidos efectivamente cobrados (por su fecha de cobro).
    cheques.forEach(ch => {
        if ((ch.clasificacion || 'Recibido') !== 'Recibido' || ch.estado !== 'Cobrado') return;
        const f = new Date(ch.fecha_cobro + 'T00:00:00');
        if (!isNaN(f) && f.getFullYear() === anio) ingresosMes[f.getMonth()] += Number(ch.monto);
    });

    gastos.forEach(g => {
        const f = new Date(g.fecha + 'T00:00:00');
        if (f.getFullYear() === anio) egresosMes[f.getMonth()] += Number(g.monto);
    });

    miChartFlujo = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: meses,
            datasets: [
                {
                    label: 'Ingresos Cobrados',
                    data: ingresosMes,
                    backgroundColor: '#28A745',
                    borderRadius: 4
                },
                {
                    label: 'Gastos y Egresos',
                    data: egresosMes,
                    backgroundColor: '#DC3545',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, ticks: { callback: function(value) { return '$' + value.toLocaleString('es-AR'); } } }
            },
            plugins: {
                legend: { position: 'top' }
            }
        }
    });
}

async function generarPDFEjecutivo() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Capturamos los datos filtrados directamente desde la pantalla
    const selector = document.getElementById('dash-filtro-tiempo');
    const periodo = selector.options[selector.selectedIndex].text;
    
    const ingresos = document.getElementById('kpi-ingresos').innerText;
    const egresos = document.getElementById('kpi-egresos').innerText;
    const ganancia = document.getElementById('kpi-ganancia').innerText;
    const calle = document.getElementById('kpi-calle').innerText;
    const taller = document.getElementById('alerta-estancada').innerText;

    // --- ENCABEZADO FORMAL ---
    doc.setFontSize(24);
    doc.setTextColor(213, 0, 109); // Color Magenta corporativo
    doc.text("Gráfica Viamonte", 14, 22);
    
    doc.setFontSize(14);
    doc.setTextColor(50, 50, 50);
    doc.text("Reporte Ejecutivo de Resultados", 14, 32);
    
    doc.setFontSize(11);
    doc.setTextColor(100, 100, 100);
    doc.text(`Período analizado: ${periodo}`, 14, 42);
    doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-AR')}`, 14, 48);

    // --- TABLA DE RESULTADOS PRINCIPALES ---
    doc.autoTable({
        startY: 55,
        head: [['Concepto Financiero', 'Monto Registrado']],
        body: [
            ['Total Ingresos (Cobrado)', ingresos],
            ['Total Egresos (Gastos Operativos)', egresos],
            ['Ganancia Neta del Período', ganancia]
        ],
        theme: 'grid',
        headStyles: { fillColor: [40, 40, 40], fontSize: 12 },
        bodyStyles: { fontSize: 12, textColor: [50, 50, 50] },
        alternateRowStyles: { fillColor: [245, 245, 245] },
        columnStyles: {
            0: { fontStyle: 'bold' },
            1: { halign: 'right', fontStyle: 'bold' }
        }
    });

    // --- TABLA DE ESTADO Y ALERTA ---
    doc.autoTable({
        startY: doc.lastAutoTable.finalY + 15,
        head: [['Indicadores de Producción y Riesgo', 'Capital Involucrado']],
        body: [
            ['Capital estancado en taller (En producción)', taller],
            ['Cuentas por cobrar (Trabajos entregados)', calle]
        ],
        theme: 'grid',
        headStyles: { fillColor: [213, 0, 109], fontSize: 11 }, // Cabecera magenta para alertas
        bodyStyles: { fontSize: 11 },
        columnStyles: {
            0: { fontStyle: 'bold' },
            1: { halign: 'right', textColor: [200, 0, 0], fontStyle: 'bold' }
        }
    });

    // --- PIE DE PÁGINA ---
    doc.setFontSize(9);
    doc.setTextColor(150, 150, 150);
    doc.text("Documento generado automáticamente por el sistema de gestión CRM Viamonte.", 14, 280);

    // Descarga del archivo
    doc.save(`Reporte_Directorio_${periodo.replace(/ /g, '_')}.pdf`);
}

// ==========================================
// MÓDULO DE CHEQUES
// ==========================================

let idChequeEditando = null;

// Estados en los que el cheque ya impactó la caja: salir de ellos exige motivo.
const ESTADOS_FINALES_CHEQUE = ['Cobrado', 'Endosado', 'Rechazado'];

// El backend rechaza transiciones inválidas y ediciones sobre cheques cobrados:
// sin esto los errores pasarían en silencio y el usuario creería que guardó.
async function mostrarErrorCheque(resp, titulo) {
    let detalle = 'Ocurrió un error inesperado.';
    try {
        const data = await resp.json();
        if (data && data.detail) detalle = data.detail;
    } catch (e) { /* respuesta sin cuerpo JSON */ }
    await Swal.fire(titulo, detalle, 'warning');
}

async function abrirDrawerCheque() {
    idChequeEditando = null;
    document.getElementById('titulo-drawer-cheque').innerText = 'Ingresar Nuevo Cheque';
    document.getElementById('form-cheque').reset();
    document.getElementById('fch_emision').value = new Date().toISOString().split('T')[0];

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
                fecha: new Date().toISOString().split('T')[0],
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