const API_URL = 'http://localhost:8000/api';
let clienteActualFicha = null; // Guardamos qué cliente está abierto

// ==========================================
// 1. INICIALIZACIÓN Y LOGIN
// ==========================================
// ==========================================
// 1. INICIALIZACIÓN Y LOGIN (Persistente)
// ==========================================

// Ni bien carga la página, revisamos si ya hay una sesión guardada
// Ni bien carga la página, revisamos sesión y pestaña
document.addEventListener('DOMContentLoaded', () => {
    const estaLogueado = localStorage.getItem('viamonte_auth');
    if (estaLogueado === 'true') {
        document.getElementById('login-screen').classList.add('hidden');
        iniciarApp();
        
        // Recuperamos la última pestaña en la que estábamos
        const lastTab = localStorage.getItem('viamonte_last_tab') || 'tab-dashboard';
        const tabBoton = document.querySelector(`[onclick*="${lastTab}"]`);
        switchTab(lastTab, tabBoton);
    }
});

// Evento del formulario de Login
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario: user, contrasenia: pass })
        });
        
        if (response.ok) {
            // Guardamos el token en el navegador
            localStorage.setItem('viamonte_auth', 'true');
            
            document.getElementById('login-error').style.display = 'none';
            document.getElementById('login-screen').classList.add('hidden');
            iniciarApp();
        } else {
            document.getElementById('login-error').style.display = 'block';
        }
    } catch (error) {
        console.error("Error crítico:", error);
    }
});

// Función para salir
function cerrarSesion() {
    // Borramos el token y recargamos la página
    localStorage.removeItem('viamonte_auth');
    window.location.reload();
}

function iniciarApp() {
    cargarClientes();
    cargarDashboard();
    cargarTrabajos();
    cargarSelectorClientes();
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
        const [respC, respT, respM, respN] = await Promise.all([
            fetch(`${API_URL}/clientes/`),
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/movimientos/${id}`),
            fetch(`${API_URL}/notas/${id}`)
        ]);
        
        const clientes = await respC.json();
        const todosTrabajos = await respT.json();
        const movimientos = respM.ok ? await respM.json() : [];
        const notas = respN.ok ? await respN.json() : [];
        
        const cliente = clientes.find(c => c.id === id);
        const trabajos = todosTrabajos.filter(t => t.cliente_id === id);
        
        if (!cliente) return;

        document.getElementById('ficha-nombre').innerText = cliente.nombre_completo;
        document.getElementById('ficha-cuit').innerText = `DNI/CUIT: ${cliente.dni_cuit} | Tel: ${cliente.telefono}`;

        const totalFacturado = trabajos.reduce((suma, t) => suma + t.precio_venta, 0);
        const totalPagado = movimientos.filter(m => m.tipo === 'Pago').reduce((suma, m) => suma + m.monto, 0);
        const saldoReal = totalFacturado - totalPagado;

        const lblSaldo = document.getElementById('ficha-saldo');
        lblSaldo.innerText = `$ ${saldoReal.toLocaleString('es-AR')}`;
        lblSaldo.style.color = saldoReal > 0 ? "var(--red)" : "var(--green)";

        const divTrabajos = document.getElementById('lista-trabajos-cliente');
        divTrabajos.innerHTML = trabajos.length === 0 ? '<p style="text-align:center; color:var(--muted);">Sin historial de trabajos.</p>' : '';
        
        trabajos.reverse().forEach(t => {
            const shortId = t.id.substring(0,6).toUpperCase();
            const pagosDeEsteTrabajo = movimientos
                .filter(m => m.tipo === 'Pago' && m.trabajo_id === t.id)
                .reduce((suma, m) => suma + m.monto, 0);

            const saldoTrabajo = t.precio_venta - pagosDeEsteTrabajo;
            const textoPago = saldoTrabajo <= 0 
                ? '<span style="color:var(--green); font-weight:600;">Pagado 100%</span>' 
                : `<span style="color:var(--red); font-weight:600;">Debe: $${saldoTrabajo.toLocaleString('es-AR')}</span> <span style="font-size:11px; color:var(--muted);">(Abonó: $${pagosDeEsteTrabajo.toLocaleString('es-AR')})</span>`;

            divTrabajos.innerHTML += `
                <div class="accordion-item">
                    <div class="accordion-header" onclick="toggleAccordion(this)">
                        <span>#${shortId} - ${t.cantidad}x ${t.descripcion_producto}</span>
                        <span style="color:var(--magenta)">$${t.precio_venta.toLocaleString('es-AR')} ▾</span>
                    </div>
                    <div class="accordion-body">
                        <p style="margin:0 0 8px 0; display:flex; justify-content:space-between;">
                            <span><b>Estado:</b> ${t.estado}</span>
                            <span>${textoPago}</span>
                        </p>
                        <p style="margin:0 0 8px 0;"><b>Fecha de ingreso:</b> ${t.fecha_creacion}</p>
                        <p style="margin:0 0 8px 0;"><b>Fecha de comienzo:</b> ${t.fecha_comienzo || '-'}</p>
                        <p style="margin:0 0 8px 0;"><b>Notas iniciales:</b> ${t.notas_iniciales || 'Ninguna'}</p>
                        <button class="btn secondary" style="margin-top:12px; font-size:12px;" onclick="abrirModalEditarTrabajo('${t.id}', '${t.descripcion_producto}', ${t.cantidad}, ${t.precio_venta})">✏️ Editar Trabajo</button>
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
                    <td>${m.descripcion} <br><small style="color:var(--muted);">${m.metodo || m.tipo}</small></td>
                    <td class="tnum" style="color:${colorMonto}; font-weight:600;">${signo}$${m.monto.toLocaleString('es-AR')}</td>
                </tr>
            `;
        });

        const divNotas = document.getElementById('lista-notas-cliente');
        divNotas.innerHTML = '';
        notas.forEach(n => {
            divNotas.innerHTML += `
                <div class="nota-card">
                    <div class="nota-fecha">${new Date(n.fecha_creacion).toLocaleString('es-AR')}</div>
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
        select.innerHTML = '<option value="">Ninguno (Pago general a cuenta)</option>';
        
        trabajosCliente.forEach(t => {
            const shortId = t.id.substring(0,6).toUpperCase();
            select.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${t.descripcion_producto} (Total: $${t.precio_venta})</option>`;
        });
    } catch(e) { console.error(e); }
    toggleDrawer('drawer-nuevo-pago');
}

async function guardarPago(e) {
    e.preventDefault();
    const monto = parseFloat(document.getElementById('fp_monto').value);
    const metodo = document.getElementById('fp_metodo').value;
    const trabajo_id = document.getElementById('fp_trabajo_id').value;
    
    let desc_pago = "Pago general a cuenta";
    if (trabajo_id) {
        const shortId = trabajo_id.substring(0,6).toUpperCase();
        desc_pago = `Pago asociado a trabajo #${shortId}`;
    }

    try {
        const respMov = await fetch(`${API_URL}/movimientos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: clienteActualFicha,
                trabajo_id: trabajo_id || null,
                monto: monto,
                tipo: "Pago",
                metodo: metodo,
                descripcion: desc_pago
            })
        });

        if (!respMov.ok) throw new Error("Fallo al guardar movimiento");

        document.getElementById('form-pago').reset();
        toggleDrawer('drawer-nuevo-pago');
        abrirFicha(clienteActualFicha);
        cargarClientes();

    } catch (error) {
        console.error("Error procesando el pago:", error);
    }
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

// ==========================================
// 5. EDICIÓN DE TRABAJOS (Historial automático)
// ==========================================
function abrirModalEditarTrabajo(id, descripcion, cantidad, precio) {
    document.getElementById('fe_trabajo_id').value = id;
    document.getElementById('fe_descripcion').value = descripcion;
    document.getElementById('fe_cantidad').value = cantidad;
    document.getElementById('fe_precio').value = precio;
    document.getElementById('fe_razon').value = '';
    toggleDrawer('drawer-editar-trabajo');
}

async function guardarEdicionTrabajo(e) {
    e.preventDefault();
    const id = document.getElementById('fe_trabajo_id').value;
    const razon = document.getElementById('fe_razon').value;
    const nuevoPrecio = parseFloat(document.getElementById('fe_precio').value);
    const nuevaCantidad = parseInt(document.getElementById('fe_cantidad').value);
    const nuevaDesc = document.getElementById('fe_descripcion').value;

    try {
        await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                descripcion_producto: nuevaDesc,
                cantidad: nuevaCantidad,
                precio_venta: nuevoPrecio
            })
        });

        // Acá estaba el error: faltaba el campo "metodo"
        const respMov = await fetch(`${API_URL}/movimientos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: clienteActualFicha,
                trabajo_id: id,
                monto: 0,
                tipo: "Edición",
                metodo: "Sistema", // SOLUCIÓN AL CRASHEO
                descripcion: `Cambio: ${razon} (${nuevaCantidad}x a $${nuevoPrecio})`
            })
        });

        toggleDrawer('drawer-editar-trabajo');
        abrirFicha(clienteActualFicha);
        cargarTrabajos();

    } catch (error) {
        console.error("Error al editar trabajo:", error);
    }
}

// ==========================================
// 6. FUNCIONES BASE QUE YA TENÍAMOS (Carga de Tablas)
// ==========================================

async function cargarClientes(filtro = "") {
    try {
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        // Ahora pedimos TODO de una para que la matemática sea exacta
        const [respC, respT, respM] = await Promise.all([
            fetch(url),
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/movimientos/`)
        ]);
        
        const clientes = await respC.json();
        const trabajos = await respT.json();
        const movimientos = await respM.json();
        
        const tbody = document.querySelector('#tableClientes tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        clientes.forEach(cliente => {
            // Lógica unificada: Lo facturado menos lo pagado real
            const trabajosCliente = trabajos.filter(t => t.cliente_id === cliente.id);
            const movsCliente = movimientos.filter(m => m.cliente_id === cliente.id);
            
            const totalFacturado = trabajosCliente.reduce((suma, t) => suma + t.precio_venta, 0);
            const totalPagado = movsCliente.filter(m => m.tipo === 'Pago').reduce((suma, m) => suma + m.monto, 0);
            
            const saldoReal = totalFacturado - totalPagado;
            const colorSaldo = saldoReal > 0 ? "var(--red)" : "var(--green)";

            tbody.innerHTML += `
                <tr class="client-row">
                  <td><b>${cliente.nombre_completo}</b></td>
                  <td>${cliente.nombre_empresa || '-'}</td>
                  <td class="tnum">${cliente.dni_cuit}</td>
                  <td class="tnum" style="color: ${colorSaldo}; font-weight: 600;">$ ${saldoReal.toLocaleString('es-AR')}</td>
                  <td>
                    <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                    <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
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
    const data = {
        nombre_completo: document.getElementById('fc_nombre').value,
        nombre_empresa: document.getElementById('fc_empresa').value || null,
        dni_cuit: document.getElementById('fc_cuit').value,
        telefono: document.getElementById('fc_telefono').value,
        frecuencia_recompra_dias: document.getElementById('fc_recompra').value ? parseInt(document.getElementById('fc_recompra').value) : null
    };
    await fetch(`${API_URL}/clientes/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    document.getElementById('form-cliente').reset();
    toggleDrawer('drawer-nuevo-cliente');
    cargarClientes();
}

// Guardar trabajo nuevo
async function guardarTrabajo(e) {
    e.preventDefault();
    const cliente_id = document.getElementById('ft_cliente_id').value;
    const desc = document.getElementById('ft_descripcion').value;
    const cant = parseInt(document.getElementById('ft_cantidad').value);
    const notas = document.getElementById('ft_notas') ? document.getElementById('ft_notas').value.trim() : "";
    
    const data = {
        cliente_id: cliente_id,
        descripcion_producto: desc,
        cantidad: cant,
        precio_venta: parseFloat(document.getElementById('ft_precio').value),
        costo_total_materiales: parseFloat(document.getElementById('ft_costo').value),
        forma_pago_heredada: document.getElementById('ft_pago').value,
        notas_iniciales: notas || null,
        fecha_creacion: new Date().toISOString().split('T')[0],
        estado: "Aprobado" 
    };

    const resp = await fetch(`${API_URL}/trabajos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const nuevoTrabajo = await resp.json();
    const shortId = nuevoTrabajo.id.substring(0,6).toUpperCase();

    // 1. Guardar movimiento de creación en el historial
    await fetch(`${API_URL}/movimientos/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            cliente_id: cliente_id,
            trabajo_id: nuevoTrabajo.id,
            monto: 0,
            tipo: "Sistema",
            metodo: "Sistema",
            descripcion: `Ingreso de trabajo #${shortId}: ${cant}x ${desc}`
        })
    });

    // 2. Si el usuario escribió una nota, la guardamos en la pestaña de Notas global
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
    toggleDrawer('drawer-nuevo-trabajo');
    cargarTrabajos(); 
    
    // Si justo tenías la ficha del cliente abierta, la recargamos
    if (clienteActualFicha === cliente_id && document.getElementById('drawer-cliente').classList.contains('open')) {
        abrirFicha(clienteActualFicha);
    }
}

// Kanban y Drag & Drop
async function cargarSelectorClientes() {
    const clientes = await (await fetch(`${API_URL}/clientes/`)).json();
    const selector = document.getElementById('ft_cliente_id');
    if(!selector) return;
    selector.innerHTML = '<option value="">Seleccione un cliente...</option>';
    clientes.forEach(c => selector.innerHTML += `<option value="${c.id}">${c.nombre_completo}</option>`);
}

function permitirSoltar(ev) { ev.preventDefault(); }
function arrastrarTarjeta(ev, id) { ev.dataTransfer.setData("text", id); }

async function soltarTarjeta(ev, nuevoEstado) {
    ev.preventDefault();
    const id = ev.dataTransfer.getData("text");
    const tarjeta = document.getElementById(`card-${id}`);
    const columna = ev.target.closest('.kanban-col');
    
    if (columna && tarjeta) {
        columna.appendChild(tarjeta);
    }

    try {
        const resp = await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        if (!resp.ok) throw new Error("Backend rechazó el cambio");

        // Acá disparamos el registro en Movimientos
        const cliente_id = tarjeta.getAttribute('data-cliente');
        const shortId = id.substring(0,6).toUpperCase();
        
        await fetch(`${API_URL}/movimientos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: cliente_id,
                trabajo_id: id,
                monto: 0,
                tipo: "Sistema",
                metodo: "Sistema",
                descripcion: `Estado actualizado a "${nuevoEstado}" (Trabajo #${shortId})`
            })
        });

        cargarTrabajos();
        const drawerCliente = document.getElementById('drawer-cliente');
        if (clienteActualFicha && drawerCliente.classList.contains('open')) {
            abrirFicha(clienteActualFicha);
        }
        
    } catch (error) {
        console.error("Error al actualizar estado:", error);
    }
}
async function cargarTrabajos() {
    const [trabajos, clientes] = await Promise.all([
        (await fetch(`${API_URL}/trabajos/`)).json(),
        (await fetch(`${API_URL}/clientes/`)).json()
    ]);
    
    const cols = {
        "Aprobado": document.getElementById('col-pendiente'),
        "En Diseño": document.getElementById('col-diseno'),
        "En Producción": document.getElementById('col-produccion'),
        "Entregado": document.getElementById('col-entregado')
    };
    Object.values(cols).forEach(col => { if(col) col.innerHTML = col.firstElementChild.outerHTML; });

    trabajos.forEach(t => {
        const cliente = clientes.find(c => c.id === t.cliente_id);
        const bordeColor = t.estado === "En Diseño" ? "var(--magenta)" : (t.estado === "En Producción" ? "var(--amber)" : "transparent");
        const shortId = t.id.substring(0,6).toUpperCase();
        
        // Atento al data-cliente que agregamos acá
        const tarjetaHTML = `
            <div class="kanban-card" id="card-${t.id}" data-cliente="${t.cliente_id}" draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')" style="border-left: 4px solid ${bordeColor}; cursor: grab;">
              <div style="font-size:10px; color:var(--muted); margin-bottom:2px;">#${shortId}</div>
              <div class="client">${cliente ? cliente.nombre_completo : 'Desconocido'}</div>
              <div class="job">${t.cantidad}x ${t.descripcion_producto}</div>
              <div class="date">${t.fecha_creacion} - $${t.precio_venta}</div>
            </div>
        `;
        if (cols[t.estado]) cols[t.estado].innerHTML += tarjetaHTML;
        else if (cols["Aprobado"]) cols["Aprobado"].innerHTML += tarjetaHTML;
    });
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

function generarInformeDiarioPDF() {
    html2pdf().set({ margin: 10, filename: 'Hoja_Ruta.pdf', orientation: 'landscape' }).from(document.querySelector('.kanban-board')).save();
}

function cargarDashboard() {
    const ctx = document.getElementById('chartComparativo');
    if (!ctx) return;
    new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Marzo', 'Abril', 'Mayo', 'Junio'],
        datasets: [
          { label: 'Ingresos', data: [420000, 510000, 480000, 630000], backgroundColor: '#22824F' },
          { label: 'Gastos', data: [280000, 310000, 290000, 350000], backgroundColor: '#C13B3B' }
        ]
      }
    });
}