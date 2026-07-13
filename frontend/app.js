const API_URL = 'http://localhost:8000/api';
let clienteActualFicha = null; // Guardamos qué cliente está abierto

// ==========================================
// 1. INICIALIZACIÓN Y LOGIN
// ==========================================
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
            document.getElementById('login-screen').classList.add('hidden');
            iniciarApp();
        } else {
            document.getElementById('login-error').style.display = 'block';
        }
    } catch (error) {
        console.error("Error crítico:", error);
    }
});

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
    
    // Reseteamos las pestañas a la primera
    switchFichaTab('trabajos');

    try {
        // Hacemos 4 consultas en paralelo al servidor
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

        // --- CABECERA ---
        document.getElementById('ficha-nombre').innerText = cliente.nombre_completo;
        document.getElementById('ficha-cuit').innerText = `DNI/CUIT: ${cliente.dni_cuit} | Tel: ${cliente.telefono}`;

        // --- SALDO REAL DE CUENTA CORRIENTE ---
        // Sumamos lo facturado (trabajos) y restamos lo pagado (movimientos)
        const totalFacturado = trabajos.reduce((suma, t) => suma + t.precio_venta, 0);
        const totalPagado = movimientos.filter(m => m.tipo === 'Pago').reduce((suma, m) => suma + m.monto, 0);
        const saldoReal = totalFacturado - totalPagado;

        const lblSaldo = document.getElementById('ficha-saldo');
        lblSaldo.innerText = `$ ${saldoReal.toLocaleString('es-AR')}`;
        lblSaldo.style.color = saldoReal > 0 ? "var(--red)" : "var(--green)";

        // --- RENDER: PESTAÑA TRABAJOS (Acordeón) ---
        const divTrabajos = document.getElementById('lista-trabajos-cliente');
        divTrabajos.innerHTML = trabajos.length === 0 ? '<p style="text-align:center; color:var(--muted);">Sin historial de trabajos.</p>' : '';
        
        // Ordenamos para que los más nuevos salgan arriba
        trabajos.reverse().forEach(t => {
            divTrabajos.innerHTML += `
                <div class="accordion-item">
                    <div class="accordion-header" onclick="toggleAccordion(this)">
                        <span>${t.cantidad}x ${t.descripcion_producto}</span>
                        <span style="color:var(--magenta)">$${t.precio_venta} ▾</span>
                    </div>
                    <div class="accordion-body">
                        <p style="margin:0 0 8px 0;"><b>Estado actual:</b> ${t.estado}</p>
                        <p style="margin:0 0 8px 0;"><b>Fecha de ingreso:</b> ${t.fecha_creacion}</p>
                        <p style="margin:0 0 8px 0;"><b>Notas iniciales:</b> ${t.notas_iniciales || 'Ninguna'}</p>
                        <button class="btn secondary" style="margin-top:12px; font-size:12px;" onclick="abrirModalEditarTrabajo('${t.id}', '${t.descripcion_producto}', ${t.cantidad}, ${t.precio_venta})">✏️ Editar Trabajo</button>
                    </div>
                </div>
            `;
        });

        // --- RENDER: PESTAÑA MOVIMIENTOS ---
        const tbodyMovimientos = document.querySelector('#tabla-movimientos tbody');
        tbodyMovimientos.innerHTML = '';
        movimientos.forEach(m => {
            const colorMonto = m.tipo === 'Pago' ? 'var(--green)' : 'var(--ink)';
            const signo = m.tipo === 'Pago' ? '+' : '';
            tbodyMovimientos.innerHTML += `
                <tr>
                    <td>${new Date(m.fecha).toLocaleDateString('es-AR')}</td>
                    <td>${m.descripcion} <br><small style="color:var(--muted);">${m.metodo || m.tipo}</small></td>
                    <td class="tnum" style="color:${colorMonto}; font-weight:600;">${signo}$${m.monto}</td>
                </tr>
            `;
        });

        // --- RENDER: PESTAÑA NOTAS ---
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
        // Traemos los trabajos del cliente para llenar el <select>
        const respT = await fetch(`${API_URL}/trabajos/`);
        const trabajos = await respT.json();
        
        // Filtramos solo los trabajos de este cliente
        const trabajosCliente = trabajos.filter(t => t.cliente_id === clienteActualFicha);
        
        const select = document.getElementById('fp_trabajo_id');
        select.innerHTML = '<option value="">Ninguno (Pago general a cuenta)</option>';
        
        trabajosCliente.forEach(t => {
            // Calculamos cuánto debe de este trabajo en particular
            const saldoTrabajo = t.precio_venta - (t.monto_abonado || 0);
            select.innerHTML += `<option value="${t.id}">${t.cantidad}x ${t.descripcion_producto} (Total: $${t.precio_venta})</option>`;
        });
        
    } catch(e) { 
        console.error("Error al cargar trabajos para el pago:", e); 
    }
    
    toggleDrawer('drawer-nuevo-pago');
}

async function guardarPago(e) {
    e.preventDefault();
    const monto = parseFloat(document.getElementById('fp_monto').value);
    const metodo = document.getElementById('fp_metodo').value;
    const trabajo_id = document.getElementById('fp_trabajo_id').value || null;
    
    try {
        // 1. Guardamos el Movimiento
        const respMov = await fetch(`${API_URL}/movimientos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: clienteActualFicha,
                trabajo_id: trabajo_id,
                monto: monto,
                tipo: "Pago",
                metodo: metodo,
                descripcion: trabajo_id ? "Pago asociado a trabajo" : "Pago general a cuenta"
            })
        });

        if (!respMov.ok) {
            const errorData = await respMov.json();
            console.error("Error del backend (Movimientos):", errorData);
            alert("El servidor rechazó el pago. Revisá la consola (F12).");
            return;
        }

        // 2. Si se asoció a un trabajo, le sumamos el pago a "monto_abonado" en la tabla Trabajos
        if (trabajo_id) {
            const respT = await fetch(`${API_URL}/trabajos/`);
            const trabajos = await respT.json();
            const trabajoActual = trabajos.find(t => t.id === trabajo_id);
            
            if (trabajoActual) {
                const nuevoAbonado = (trabajoActual.monto_abonado || 0) + monto;
                await fetch(`${API_URL}/trabajos/${trabajo_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ monto_abonado: nuevoAbonado })
                });
            }
        }

        // 3. Limpiamos y recargamos
        document.getElementById('form-pago').reset();
        toggleDrawer('drawer-nuevo-pago');
        abrirFicha(clienteActualFicha); // Refrescamos la ficha para ver el movimiento
        cargarClientes(); // Refrescamos el saldo de la tabla principal

    } catch (error) {
        console.error("Error crítico procesando el pago:", error);
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
        // 1. Actualizamos el Trabajo
        await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                descripcion_producto: nuevaDesc,
                cantidad: nuevaCantidad,
                precio_venta: nuevoPrecio
            })
        });

        // 2. Guardamos el Movimiento para que quede en el historial
        const respMov = await fetch(`${API_URL}/movimientos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: clienteActualFicha,
                trabajo_id: id,
                monto: 0,
                tipo: "Edición",
                descripcion: `Cambio: ${razon} (${nuevaCantidad}x ${nuevaDesc} a $${nuevoPrecio})`
            })
        });

        if (!respMov.ok) {
            const errorData = await respMov.json();
            console.error("Fallo al guardar el historial:", errorData);
            alert("El trabajo se editó, pero hubo un error al guardar el historial. Revisá la consola.");
        }

        toggleDrawer('drawer-editar-trabajo');
        abrirFicha(clienteActualFicha); // Refrescamos todo
        cargarTrabajos(); // Refrescamos el kanban

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

        // Traemos clientes y trabajos
        const [respC, respT] = await Promise.all([
            fetch(url),
            fetch(`${API_URL}/trabajos/`)
        ]);
        
        const clientes = await respC.json();
        const trabajos = await respT.json();
        const tbody = document.querySelector('#tableClientes tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        clientes.forEach(cliente => {
            // Calculamos un saldo rápido sumando deudas de trabajos (Precio - Señas)
            const trabajosDelCliente = trabajos.filter(t => t.cliente_id === cliente.id);
            const saldoAproximado = trabajosDelCliente.reduce((suma, t) => suma + (t.precio_venta - t.monto_abonado), 0);
            const colorSaldo = saldoAproximado > 0 ? "var(--red)" : "var(--green)";

            // ACÁ ESTÁ ARREGLADA LA COLUMNA QUE FALTABA
            tbody.innerHTML += `
                <tr class="client-row">
                  <td><b>${cliente.nombre_completo}</b></td>
                  <td>${cliente.nombre_empresa || '-'}</td>
                  <td class="tnum">${cliente.dni_cuit}</td>
                  <td class="tnum" style="color: ${colorSaldo}; font-weight: 600;">$ ${saldoAproximado.toLocaleString('es-AR')}</td>
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
    const data = {
        cliente_id: document.getElementById('ft_cliente_id').value,
        descripcion_producto: document.getElementById('ft_descripcion').value,
        cantidad: parseInt(document.getElementById('ft_cantidad').value),
        precio_venta: parseFloat(document.getElementById('ft_precio').value),
        costo_total_materiales: parseFloat(document.getElementById('ft_costo').value),
        forma_pago_heredada: document.getElementById('ft_pago').value,
        notas_iniciales: document.getElementById('ft_notas') ? document.getElementById('ft_notas').value : null,
        fecha_creacion: new Date().toISOString().split('T')[0],
        estado: "Aprobado" 
    };

    await fetch(`${API_URL}/trabajos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    document.getElementById('form-trabajo').reset();
    toggleDrawer('drawer-nuevo-trabajo');
    cargarTrabajos(); 
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
    if (columna && tarjeta) columna.appendChild(tarjeta);

    await fetch(`${API_URL}/trabajos/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ estado: nuevoEstado })
    });
    cargarTrabajos();
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
        
        const tarjetaHTML = `
            <div class="kanban-card" id="card-${t.id}" draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')" style="border-left: 4px solid ${bordeColor}; cursor: grab;">
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