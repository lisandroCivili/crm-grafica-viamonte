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
    cargarPresupuestos();
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
// REEMPLAZAR cargarTrabajos
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
        // FILTRO BARRERA: Si está cancelado, ni lo miramos para el Kanban
        if (t.estado === "Cancelado") return;

        const cliente = clientes.find(c => c.id === t.cliente_id);
        const bordeColor = t.estado === "En Diseño" ? "var(--magenta)" : (t.estado === "En Producción" ? "var(--amber)" : "transparent");
        const shortId = t.id.substring(0,6).toUpperCase();
        
        const tarjetaHTML = `
            <div class="kanban-card" id="card-${t.id}" data-cliente="${t.cliente_id}" draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')" style="border-left: 4px solid ${bordeColor}; cursor: grab;">
              <div style="font-size:10px; color:var(--muted); margin-bottom:2px;">#${shortId}</div>
              <div class="client">${cliente ? cliente.nombre_completo : 'Desconocido'}</div>
              <div class="job">${t.cantidad}x ${t.descripcion_producto}</div>
              <div class="date">${t.fecha_creacion} - $${t.precio_venta.toLocaleString('es-AR')}</div>
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

// ==========================================
// MÓDULO DE PRESUPUESTOS AVANZADO
// ==========================================

const LISTA_COSTOS = ["Papel", "Troquel", "Luz", "Diseño", "Chapas", "Impresión", "Barniz / Laminado", "Cordón de bolsas", "Troquelado", "Tinta", "Pegado y armado", "Empaquetado / Flete", "Corte / Encuadernación", "Gastos otros"];

let idPresupuestoVersionDe = null; // Para saber si estamos editando uno viejo

// Reemplazá abrirDrawerPresupuesto
async function abrirDrawerPresupuesto() {
    idPresupuestoVersionDe = null; // Reseteamos por si era nuevo
    document.getElementById('modal-presupuesto').classList.remove('hidden');
    document.getElementById('lbl-pres-id').innerHTML = `Nº 0001-${Math.floor(1000 + Math.random() * 9000)}`;
    
    const cont = document.getElementById('contenedor-costos');
    cont.innerHTML = '';
    LISTA_COSTOS.forEach(c => {
        cont.innerHTML += `<div class="costo-row"><label>${c}</label><input type="number" class="input-costo" data-nombre="${c}" value="0" oninput="calcularModal()" onfocus="if(this.value=='0')this.value=''"></div>`;
    });

    try {
        const resp = await fetch(`${API_URL}/clientes/`);
        const clientes = await resp.json();
        const select = document.getElementById('mp_cliente_id');
        select.innerHTML = '<option value="">Seleccione...</option>';
        clientes.forEach(c => select.innerHTML += `<option value="${c.id}">${c.nombre_completo}</option>`);
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

    document.getElementById('lbl-m-subtotal').innerText = `$ ${subtotal.toLocaleString('es-AR')}`;
    document.getElementById('lbl-m-txt-ganancia').innerText = `${margen}% de ganancia`;
    document.getElementById('lbl-m-ganancia').innerText = `$ ${ganancia.toLocaleString('es-AR')}`;
    document.getElementById('lbl-m-total').innerText = `$ ${total.toLocaleString('es-AR')}`;
    document.getElementById('lbl-m-unidad').innerText = `$ ${unidad.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
}

// AGREGAR ESTA FUNCIÓN NUEVA
async function duplicarPresupuesto(id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const p = (await respP.json()).find(x => x.id === id);
        if (!p) return;

        await abrirDrawerPresupuesto(); // Prepara el modal limpio
        
        idPresupuestoVersionDe = id; // Clavamos la relación
        document.getElementById('lbl-pres-id').innerHTML = `Nº 0001-... <span style="color:var(--magenta); font-size:12px;">(Versión de #${id.substring(0,6).toUpperCase()})</span>`;
        
        // Rellenamos
        document.getElementById('mp_cliente_id').value = p.cliente_id;
        document.getElementById('mp_descripcion').value = p.descripcion;
        document.getElementById('mp_cantidad').value = p.cantidad;
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

// REEMPLAZAR guardarPresupuestoModerno (Agrega la version)
async function guardarPresupuestoModerno(e) {
    e.preventDefault();
    const inputs = document.querySelectorAll('.input-costo');
    let detalles = {}; let subtotal = 0;
    inputs.forEach(i => {
        const val = parseFloat(i.value) || 0;
        if (val > 0) { detalles[i.getAttribute('data-nombre')] = val; subtotal += val; }
    });

    const margen = parseFloat(document.getElementById('mp_margen').value) || 0;
    const total = subtotal + (subtotal * (margen / 100));

    const payload = {
        cliente_id: document.getElementById('mp_cliente_id').value,
        version_de: idPresupuestoVersionDe, // <-- ACÁ VIAJA LA RELACIÓN
        descripcion: document.getElementById('mp_descripcion').value,
        cantidad: parseInt(document.getElementById('mp_cantidad').value),
        costo_materiales: subtotal,
        detalles_costos: detalles,
        margen_ganancia: margen,
        precio_final: total,
        estado: document.getElementById('mp_estado').value,
        fecha_creacion: new Date().toISOString().split('T')[0]
    };

    try {
        await fetch(`${API_URL}/presupuestos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        cerrarModalPresupuesto();
        cargarPresupuestos();
        Swal.fire({ title: '¡Guardado!', text: 'Presupuesto creado con éxito', icon: 'success', timer: 1500, showConfirmButton: false });
    } catch (e) { console.error(e); }
}

// REEMPLAZAR cargarPresupuestos
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
            const nombreCliente = cliente ? cliente.nombre_completo : 'Desconocido';
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
                : `<button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--green); color:var(--green);" onclick="convertirATrabajo('${p.id}')">A Trabajo</button>`;

            tbody.innerHTML += `
                <tr>
                    <td>${p.fecha_creacion}</td>
                    <td><b>${nombreCliente}</b></td>
                    <td>
                        <span style="font-size:11px; color:var(--muted);">#${shortId}</span><br>
                        ${p.cantidad}x ${p.descripcion} 
                        ${versionBadge}
                    </td>
                    <td class="tnum" style="color:var(--magenta); font-weight:bold;">$ ${p.precio_final.toLocaleString('es-AR')}</td>
                    <td>${estadoBadge}</td>
                    <td style="display:flex; gap:5px; justify-content:center; flex-wrap:wrap;">
                        ${btnConvertir}
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="duplicarPresupuesto('${p.id}')">Duplicar</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--ink);" onclick="generarPDFInterno('${p.id}')">PDF Int</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--blue);" onclick="generarPDFCliente('${p.id}')">PDF Cli</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) { console.error(e); }
}

// REEMPLAZAR convertirATrabajo en app.js
async function convertirATrabajo(presupuesto_id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const presupuestos = await respP.json();
        const p = presupuestos.find(x => x.id === presupuesto_id);

        // LÓGICA DE DUPLICADOS: Si es versión de otro, preguntamos qué hacer
        let cancelarAnterior = false;
        if (p.version_de) {
            const madre = presupuestos.find(x => x.id === p.version_de);
            
            // Si el presupuesto madre ya se había convertido a trabajo, hay conflicto
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

                if (accion.isDismissed) return; // Tocó cancelar/afuera, abortamos todo
                if (accion.isConfirmed) cancelarAnterior = true; // Tocó "Cancelar el anterior"
            }
        } else {
            // Si es un presupuesto normal, hacemos la pregunta estándar
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

        // 1. Creamos el nuevo trabajo
        const dataTrabajo = {
            cliente_id: p.cliente_id,
            descripcion_producto: p.descripcion,
            cantidad: p.cantidad,
            precio_venta: p.precio_final,
            costo_total_materiales: p.costo_materiales,
            notas_iniciales: `Viene de presupuesto autom.`,
            fecha_creacion: new Date().toISOString().split('T')[0],
            estado: "Aprobado"
        };

        const respT = await fetch(`${API_URL}/trabajos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dataTrabajo) });
        const nuevoTrabajo = await respT.json();
        
        // 2. Conectamos el presupuesto al nuevo ID del trabajo
        await fetch(`${API_URL}/presupuestos/${presupuesto_id}/convertir/${nuevoTrabajo.id}`, { method: 'PUT' });

        // 3. Ejecutamos la cancelación del viejo si el usuario lo pidió
        if (cancelarAnterior) {
            const madre = presupuestos.find(x => x.id === p.version_de);
            
            // Cambiamos el estado del trabajo viejo a "Cancelado"
            await fetch(`${API_URL}/trabajos/${madre.trabajo_id}`, { 
                method: 'PUT', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ estado: "Cancelado" }) 
            });

            // Registramos el movimiento para la trazabilidad
            await fetch(`${API_URL}/movimientos/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cliente_id: p.cliente_id,
                    trabajo_id: madre.trabajo_id,
                    monto: 0,
                    tipo: "Sistema",
                    metodo: "Sistema",
                    descripcion: `Trabajo cancelado por corrección (Reemplazado por Pres. #${p.id.substring(0,6).toUpperCase()})`
                })
            });
        }
        
        cargarTrabajos();
        cargarPresupuestos();
        Swal.fire('¡Enviado!', 'El trabajo ya está en el tablero.', 'success');
        
    } catch (e) { console.error(e); }
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

// 1. PDF PARA EL CLIENTE (Simple y formal)
async function generarPDFCliente(presupuesto_id) {
    const { p, c } = await armarMoldeBasePDF(presupuesto_id);
    const shortId = p.id.substring(0,6).toUpperCase();
    
    const div = document.createElement('div');
    div.style.padding = '40px'; div.style.fontFamily = 'Arial';
    div.innerHTML = `
        <h1 style="color:#D5006D;">Gráfica Viamonte</h1>
        <h3>Cotización Nº #${shortId} | Cliente: ${c.nombre_completo}</h3><hr>
        <table style="width:100%; text-align:left; margin-top:20px;">
            <tr style="background:#f4f4f4;"><th>Cant.</th><th>Descripción</th><th style="text-align:right;">Total</th></tr>
            <tr><td>${p.cantidad}</td><td>${p.descripcion}</td><td style="text-align:right; font-weight:bold; font-size:18px;">$${p.precio_final.toLocaleString('es-AR')}</td></tr>
        </table>
        <p style="text-align:center; margin-top:50px; font-size:12px; color:#666;">Precio válido por 15 días.</p>
    `;
    html2pdf().set({ margin: 10, filename: `Cotizacion_Cliente_${shortId}.pdf` }).from(div).save();
}

// 2. PDF INTERNO (Detalle de todos los costos)
async function generarPDFInterno(presupuesto_id) {
    const { p, c } = await armarMoldeBasePDF(presupuesto_id);
    const shortId = p.id.substring(0,6).toUpperCase();
    
    let filasCostos = '';
    for (const [item, monto] of Object.entries(p.detalles_costos || {})) {
        filasCostos += `<tr><td style="border:1px solid #ddd; padding:8px;">${item}</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$${monto.toLocaleString('es-AR')}</td></tr>`;
    }

    const div = document.createElement('div');
    div.style.padding = '40px'; div.style.fontFamily = 'Arial';
    div.innerHTML = `
        <h2>[INTERNO] Hoja de Costos - #${shortId}</h2>
        <p><b>Cliente:</b> ${c.nombre_completo} | <b>Trabajo:</b> ${p.cantidad}x ${p.descripcion}</p>
        <table style="width:100%; border-collapse:collapse; margin-top:20px;">
            <tr style="background:#eee;"><th style="border:1px solid #ddd; padding:8px; text-align:left;">Ítem de Costo</th><th style="border:1px solid #ddd; padding:8px; text-align:right;">Monto</th></tr>
            ${filasCostos}
            <tr style="background:#ffe6f2;"><td style="border:1px solid #ddd; padding:8px;"><b>SUBTOTAL COSTOS</b></td><td style="border:1px solid #ddd; padding:8px; text-align:right;"><b>$${p.costo_materiales.toLocaleString('es-AR')}</b></td></tr>
            <tr><td style="border:1px solid #ddd; padding:8px;">Ganancia Aplicada (${p.margen_ganancia}%)</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$${(p.precio_final - p.costo_materiales).toLocaleString('es-AR')}</td></tr>
        </table>
        <h3 style="text-align:right; color:#D5006D; margin-top:20px;">PRECIO FINAL COBRADO: $${p.precio_final.toLocaleString('es-AR')}</h3>
    `;
    html2pdf().set({ margin: 10, filename: `Costos_Internos_${shortId}.pdf` }).from(div).save();
}