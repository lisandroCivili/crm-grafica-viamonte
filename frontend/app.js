const API_URL = 'http://localhost:8000/api';
let clienteActualFicha = null; // Guardamos qué cliente está abierto

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
    const u = document.getElementById('login-user').value;
    const p = document.getElementById('login-pass').value;

    try {
        const resp = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario: u, password: p })
        });
        
        if (resp.ok) {
            // Guardamos la llavecita simple en el navegador
            localStorage.setItem('viamonte_sesion', 'activa');
            document.getElementById('login-overlay').style.display = 'none';
            iniciarApp(); // Cargamos la base de datos recién ahora
        } else {
            Swal.fire('Error', 'Usuario o contraseña incorrectos', 'error');
        }
    } catch(e) {
        console.error("Error en login", e);
    }
}

function cerrarSesion() {
    localStorage.removeItem('viamonte_sesion');
    // Recargar la página es la forma más limpia de resetear todo y volver a mostrar el login
    location.reload(); 
}
async function descargarRespaldo() {
    try {
        // Mostramos un cartelito de carga
        Swal.fire({
            title: 'Generando respaldo...',
            text: 'Empaquetando la base de datos',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        const resp = await fetch(`${API_URL}/backup`);
        if (!resp.ok) throw new Error("Error al descargar");

        // Convertimos la respuesta en un archivo (Blob)
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        
        // Creamos un link invisible y lo "clickeamos" para forzar la descarga
        const a = document.createElement('a');
        a.href = url;
        
        const hoy = new Date();
        const fechaStr = `${hoy.getDate().toString().padStart(2, '0')}-${(hoy.getMonth() + 1).toString().padStart(2, '0')}-${hoy.getFullYear()}`;
        a.download = `respaldo_viamonte_${fechaStr}.db`;
        
        document.body.appendChild(a);
        a.click();
        
        // Limpieza
        a.remove();
        window.URL.revokeObjectURL(url);

        Swal.fire('¡Respaldo Exitoso!', 'El archivo de tu base de datos se guardó en la carpeta de Descargas.', 'success');
    } catch (error) {
        console.error("Error en backup:", error);
        Swal.fire('Error', 'No se pudo generar el respaldo', 'error');
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

// ==========================================
// MÓDULO DE GASTOS
// ==========================================

// REEMPLAZAR abrirDrawerGasto
async function abrirDrawerGasto() {
    document.getElementById('form-gasto').reset();
    document.getElementById('fg_fecha').value = new Date().toISOString().split('T')[0];
    
    try {
        const respT = await fetch(`${API_URL}/trabajos/`);
        if (respT.ok) {
            const trabajos = await respT.json();
            const selectT = document.getElementById('fg_trabajo_id');
            selectT.innerHTML = '<option value="">Ninguno (Gasto general del taller)</option>';
            
            // Filtramos para mostrar solo los que están en proceso (Aprobados, en Diseño, etc.)
            const activos = trabajos.filter(t => t.estado !== 'Entregado' && t.estado !== 'Cancelado').reverse();
            activos.forEach(t => {
                const shortId = t.id.substring(0,6).toUpperCase();
                selectT.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${t.descripcion_producto}</option>`;
            });
        }
    } catch(e) { console.error(e); }

    toggleDrawer('drawer-nuevo-gasto');
}

// REEMPLAZAR cargarGastos
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
            sumaTotal += g.monto; // Vamos sumando la plata

            let colorCat = 'var(--ink)';
            if(g.categoria === 'Insumos') colorCat = 'var(--blue)';
            else if(g.categoria === 'Servicios') colorCat = 'var(--amber)';
            else if(g.categoria === 'Sueldos') colorCat = 'var(--magenta)';

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
                            💳 ${g.metodo_pago} | 🧾 ${g.comprobante}
                        </span>
                    </td>
                    <td class="tnum" style="color:var(--red); font-weight:bold;">$ ${g.monto.toLocaleString('es-AR')}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarGasto('${g.id}')">🗑️ Borrar</button>
                    </td>
                </tr>
            `;
        });

        // 4. ACTUALIZAR EL TOTAL EN PANTALLA
        document.getElementById('lbl-total-gastos').innerText = `$ ${sumaTotal.toLocaleString('es-AR')}`;

    } catch (e) {
        console.error("Error cargando gastos:", e);
    }
}

async function guardarGasto(e) {
    e.preventDefault();
    // REEMPLAZAR EL PAYLOAD EN guardarGasto
    const tr_id = document.getElementById('fg_trabajo_id').value;
    const payload = {
        categoria: document.getElementById('fg_categoria').value,
        concepto: document.getElementById('fg_concepto').value,
        monto: parseFloat(document.getElementById('fg_monto').value),
        fecha: document.getElementById('fg_fecha').value,
        metodo_pago: document.getElementById('fg_metodo').value,
        comprobante: document.getElementById('fg_comprobante').value,
        trabajo_id: tr_id ? tr_id : null   // <-- Se manda si eligió algo
    };

    try {
        const resp = await fetch(`${API_URL}/gastos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            toggleDrawer('drawer-nuevo-gasto');
            cargarGastos();
            Swal.fire({ title: '¡Salida registrada!', icon: 'success', timer: 1500, showConfirmButton: false });
        }
    } catch (error) {
        console.error("Error al guardar gasto:", error);
    }
}

async function eliminarGasto(id) {
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

    try {
        await fetch(`${API_URL}/gastos/${id}`, { method: 'DELETE' });
        cargarGastos();
        Swal.fire('¡Eliminado!', 'El gasto fue borrado del sistema.', 'success');
    } catch (e) {
        console.error("Error al eliminar gasto:", e);
    }
}

// ==========================================
// MÓDULO DE STOCK E INVENTARIO
// ==========================================

function abrirDrawerStock() {
    document.getElementById('form-stock').reset();
    toggleDrawer('drawer-nuevo-stock');
}

async function guardarArticuloStock(e) {
    e.preventDefault();
    const payload = {
        nombre: document.getElementById('fs_nombre').value,
        categoria: document.getElementById('fs_categoria').value,
        proveedor: document.getElementById('fs_proveedor').value || null,
        cantidad: parseFloat(document.getElementById('fs_cantidad').value),
        unidad: document.getElementById('fs_unidad').value,
        stock_minimo: parseFloat(document.getElementById('fs_minimo').value),
        costo_unitario: parseFloat(document.getElementById('fs_costo').value),
        ultima_actualizacion: new Date().toISOString().split('T')[0]
    };

    try {
        const resp = await fetch(`${API_URL}/stock/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (resp.ok) {
            toggleDrawer('drawer-nuevo-stock');
            cargarStock();
            Swal.fire({ title: 'Guardado', icon: 'success', timer: 1000, showConfirmButton: false });
        }
    } catch (error) { console.error("Error guardando stock:", error); }
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
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">Inventario vacío.</td></tr>';
            document.getElementById('lbl-valor-inventario').innerText = '$ 0';
            document.getElementById('lbl-alertas-stock').innerText = '0';
            return;
        }

        stock.forEach(s => {
            // Cálculos para la cabecera
            capitalTotal += (s.cantidad * s.costo_unitario);
            const enAlerta = s.cantidad <= s.stock_minimo;
            if (enAlerta) alertasTotales++;

            // REEMPLAZAR DECLARACIÓN DE badgeEstado EN cargarStock()
            let badgeEstado = enAlerta 
                ? `<span style="background:var(--red); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">¡COMPRAR!</span>`
                : `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">Suficiente</span>`;
            
            // Le agregamos un botón de historial
            badgeEstado += `<br><button class="btn secondary" style="font-size:10px; padding:2px 4px; margin-top:5px;" onclick="verHistorialStock('${s.id}', '${s.nombre}')">Ver Historial</button>`;

            // EL SISTEMA HÍBRIDO DE CANTIDAD: Botones y tipeo manual
            const controlCantidad = `
                <div style="display:flex; align-items:center; justify-content:center; gap:5px;">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, -1, '${s.unidad}')">-</button>
                    <input type="number" id="stk-input-${s.id}" value="${s.cantidad}" style="width:70px; text-align:center; padding:5px; border:1px solid var(--line); border-radius:4px;" onchange="ajustarStockRapido('${s.id}', ${s.cantidad}, 'manual', '${s.unidad}')">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, 1, '${s.unidad}')">+</button>
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
                    <td class="tnum" style="text-align:center;">$ ${s.costo_unitario.toLocaleString('es-AR')}</td>
                    <td style="text-align:center;">${controlCantidad}</td>
                    <td style="text-align:center;">${badgeEstado}</td>
                </tr>
            `;
        });

        // Refrescar paneles
        document.getElementById('lbl-valor-inventario').innerText = `$ ${capitalTotal.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
        document.getElementById('lbl-alertas-stock').innerText = alertasTotales;

    } catch (e) { console.error("Error cargando stock:", e); }
}

// REEMPLAZAR ajustarStockRapido
async function ajustarStockRapido(id, cantidadActual, accion, unidad) {
    let nuevaCantidad;
    let motivo = "Ajuste rápido";
    
    if (accion === 'manual') {
        nuevaCantidad = parseFloat(document.getElementById(`stk-input-${id}`).value) || 0;
        if (nuevaCantidad === cantidadActual) return; // No cambió nada
        
        // Si escribe a mano, le exigimos un motivo
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
            cargarStock(); // Volvemos el input al número que estaba
            return; 
        }
        motivo = razon;
    } else {
        nuevaCantidad = cantidadActual + accion;
        motivo = accion > 0 ? "Ajuste manual rápido (+1)" : "Ajuste manual rápido (-1)";
    }

    if (nuevaCantidad < 0) nuevaCantidad = 0;

    try {
        const resp = await fetch(`${API_URL}/stock/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: nuevaCantidad, motivo: motivo })
        });

        if (resp.ok) cargarStock();
    } catch (e) { console.error("Error actualizando cantidad:", e); }
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
        const [respT, respG, respC, respCl] = await Promise.all([
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/gastos/`),
            fetch(`${API_URL}/cheques/`),       // <-- NUEVO
            fetch(`${API_URL}/clientes/`)       // <-- NUEVO
        ]);
        
        let trabajos = await respT.json();
        let gastos = await respG.json();
        let cheques = await respC.json();
        let clientes = await respCl.json();

        // LOGICA DE CHEQUES
        let plataEnCheques = 0;
        let htmlAlertasCheques = '';
        const hoyMs = new Date().getTime();
        const limiteMs = hoyMs + (7 * 24 * 60 * 60 * 1000); // 7 días para adelante

        cheques.forEach(ch => {
            if (ch.estado === 'En Cartera') {
                plataEnCheques += ch.monto;
                
                const fechaCobroDate = new Date(ch.fecha_cobro + 'T00:00:00');
                if (fechaCobroDate.getTime() <= limiteMs) {
                    const cli = clientes.find(c => c.id === ch.cliente_id);
                    const nomCli = cli ? (cli.nombre_completo || cli.nombre || 'Desc.') : 'Desc.';
                    const esVencido = fechaCobroDate.getTime() < hoyMs ? 'color:var(--red);' : '';
                    
                    htmlAlertasCheques += `
                        <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                            <span style="${esVencido}">📅 ${fechaCobroDate.toLocaleDateString('es-AR')} - ${nomCli}</span>
                            <span style="font-weight:bold;">$ ${ch.monto.toLocaleString('es-AR')}</span>
                        </div>
                    `;
                }
            }
        });

        // 2. Leemos la "Máquina del tiempo"
        const filtro = document.getElementById('dash-filtro-tiempo').value;
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

        let totalIngresos = 0;
        let plataEnLaCalle = 0;
        let plataEstancada = 0;
        let htmlMorosos = '';
        
        trabajosFiltrados.forEach(t => {
            if (t.estado !== 'Cancelado') {
                totalIngresos += t.precio_venta;
                
                // Si el trabajo está dando vueltas en el taller, es plata estancada
                if (t.estado === 'Aprobado' || t.estado === 'En Diseño' || t.estado === 'En Producción') {
                    plataEstancada += t.precio_venta;
                }

                // Plata en la calle y Semáforo de Morosos
                if (t.estado === 'Entregado') {
                    plataEnLaCalle += t.precio_venta;
                    
                    const shortId = t.id.substring(0,6).toUpperCase();
                    htmlMorosos += `
                        <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                            <span><b>#${shortId}</b> - ${t.descripcion_producto}</span>
                            <span style="color:var(--red); font-weight:bold;">$ ${t.precio_venta.toLocaleString('es-AR')}</span>
                        </div>
                    `;
                }
            }
        });

        let totalEgresos = 0;
        let gastosPorCat = {};
        gastosFiltrados.forEach(g => {
            totalEgresos += g.monto;
            gastosPorCat[g.categoria] = (gastosPorCat[g.categoria] || 0) + g.monto;
        });

        const gananciaNeta = totalIngresos - totalEgresos;

        // Actualizamos los números en pantalla
        document.getElementById('kpi-ingresos').innerText = `$ ${totalIngresos.toLocaleString('es-AR')}`;
        document.getElementById('kpi-egresos').innerText = `$ ${totalEgresos.toLocaleString('es-AR')}`;
        document.getElementById('kpi-ganancia').innerText = `$ ${gananciaNeta.toLocaleString('es-AR')}`;
        document.getElementById('kpi-calle').innerText = `$ ${plataEnLaCalle.toLocaleString('es-AR')}`;
        // Abajo de donde actualizás kpi-calle, sumá estas dos líneas:
        document.getElementById('alerta-estancada').innerText = `$ ${plataEstancada.toLocaleString('es-AR')}`;
        document.getElementById('lista-morosos').innerHTML = htmlMorosos || '<div style="color:var(--green); font-weight:bold; margin-top:10px;">¡No hay morosos! 🎉 Todos los entregados están pagados.</div>';
        // Abajo, donde actualizabas los demás KPIs, agregá estos dos:
        document.getElementById('kpi-cheques').innerText = `$ ${plataEnCheques.toLocaleString('es-AR')}`;
        document.getElementById('alerta-cheques').innerHTML = htmlAlertasCheques || '<div style="color:var(--muted); margin-top:10px;">No hay cheques por vencer esta semana.</div>';

        // Color dinámico para la ganancia
        document.getElementById('kpi-ganancia').style.color = gananciaNeta >= 0 ? 'var(--magenta)' : 'var(--red)';

        // 4. CÁLCULO DE BLOQUE 2 (GRÁFICOS)
        dibujarGraficoDistribucion(gastosPorCat);
        
        // Para el gráfico de barras armamos el flujo anual (Agrupamos por mes)
        dibujarGraficoFlujo(trabajos, gastos, anioActual);

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

function dibujarGraficoFlujo(trabajos, gastos, anio) {
    const ctx = document.getElementById('chartFlujo').getContext('2d');
    if (miChartFlujo) miChartFlujo.destroy();

    // Arrays para los 12 meses
    const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    let ingresosMes = new Array(12).fill(0);
    let egresosMes = new Array(12).fill(0);

    trabajos.forEach(t => {
        if (t.estado !== 'Cancelado') {
            const f = new Date(t.fecha_creacion + 'T00:00:00');
            if (f.getFullYear() === anio) ingresosMes[f.getMonth()] += t.precio_venta;
        }
    });

    gastos.forEach(g => {
        const f = new Date(g.fecha + 'T00:00:00');
        if (f.getFullYear() === anio) egresosMes[f.getMonth()] += g.monto;
    });

    miChartFlujo = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: meses,
            datasets: [
                {
                    label: 'Ingresos Facturados',
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
            ['Total Ingresos (Facturación)', ingresos],
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

async function abrirDrawerCheque() {
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

    toggleDrawer('drawer-nuevo-cheque');
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
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--muted);">No hay cheques registrados.</td></tr>';
            return;
        }

        cheques.forEach(ch => {
            const cliente = clientes.find(c => c.id === ch.cliente_id);
            const nombreCliente = cliente ? (cliente.nombre_completo || cliente.nombre || 'Desconocido') : 'Desconocido';
            
            // Colores por estado
            let badgeEstado = '';
            if (ch.estado === 'En Cartera') badgeEstado = `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 En Cartera</span>`;
            else if (ch.estado === 'Depositado') badgeEstado = `<span style="background:var(--muted); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔵 Depositado</span>`;
            else if (ch.estado === 'Endosado') badgeEstado = `<span style="background:var(--magenta); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟣 Endosado a: ${ch.destinatario_endoso}</span>`;
            else if (ch.estado === 'Rechazado') badgeEstado = `<span style="background:var(--red); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔴 Rechazado</span>`;

            // Formato de fechas
            const fechaCobro = new Date(ch.fecha_cobro + 'T00:00:00');
            const esUrgente = ch.estado === 'En Cartera' && fechaCobro <= new Date() ? 'color:var(--red); font-weight:bold;' : '';

            tbody.innerHTML += `
                <tr>
                    <td style="${esUrgente}">${fechaCobro.toLocaleDateString('es-AR')}</td>
                    <td><b>${ch.banco}</b><br><span style="font-size:11px; color:var(--muted);">N° ${ch.numero}</span></td>
                    <td>${nombreCliente}</td>
                    <td class="tnum" style="color:var(--ink); font-weight:bold;">$ ${ch.monto.toLocaleString('es-AR')}</td>
                    <td style="text-align:center;">${badgeEstado}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="cambiarEstadoCheque('${ch.id}', '${ch.estado}')">🔄 Estado</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarCheque('${ch.id}')">🗑️</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) { console.error("Error cargando cheques:", e); }
}

async function guardarCheque(e) {
    e.preventDefault();
    const payload = {
        cliente_id: document.getElementById('fch_cliente').value,
        banco: document.getElementById('fch_banco').value,
        numero: document.getElementById('fch_numero').value,
        monto: parseFloat(document.getElementById('fch_monto').value),
        fecha_emision: document.getElementById('fch_emision').value,
        fecha_cobro: document.getElementById('fch_cobro').value,
        estado: "En Cartera"
    };

    try {
        const resp = await fetch(`${API_URL}/cheques/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (resp.ok) {
            toggleDrawer('drawer-nuevo-cheque');
            cargarCheques();
            if (typeof cargarDashboard === "function") cargarDashboard(); // Refresca dashboard
            Swal.fire({ title: 'Cheque registrado', icon: 'success', timer: 1500, showConfirmButton: false });
        }
    } catch (error) { console.error(error); }
}

async function cambiarEstadoCheque(id, estadoActual) {
    const { value: nuevoEstado } = await Swal.fire({
        title: 'Actualizar Estado',
        input: 'select',
        inputOptions: {
            'En Cartera': '🟢 En Cartera',
            'Depositado': '🔵 Depositado / Cobrado',
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

    try {
        await fetch(`${API_URL}/cheques/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado, destinatario_endoso: destinatario })
        });
        cargarCheques();
        if (typeof cargarDashboard === "function") cargarDashboard();
    } catch (e) { console.error(e); }
}

async function eliminarCheque(id) {
    const conf = await Swal.fire({
        title: '¿Eliminar cheque?', icon: 'warning', showCancelButton: true,
        confirmButtonColor: '#d33', confirmButtonText: 'Sí, borrar'
    });
    if (conf.isConfirmed) {
        await fetch(`${API_URL}/cheques/${id}`, { method: 'DELETE' });
        cargarCheques();
        if (typeof cargarDashboard === "function") cargarDashboard();
    }
}