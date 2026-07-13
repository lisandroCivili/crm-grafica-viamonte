// Ruta base de tu backend local en FastAPI
const API_URL = 'http://localhost:8000/api';

// ==========================================
// 1. LÓGICA DE LOGIN
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
        alert("Error en la ejecución. Revisá la consola (F12).");
    }
});

// ==========================================
// 2. INICIALIZACIÓN
// ==========================================
function iniciarApp() {
    cargarClientes();
    cargarDashboard();
    cargarTrabajos();
    cargarSelectorClientes(); // Carga el <select> del formulario de trabajos
}

// ==========================================
// 3. UI Y NAVEGACIÓN
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


// ==========================================
// 4. CLIENTES: CREACIÓN, TABLA Y FICHA DINÁMICA
// ==========================================
async function guardarCliente(e) {
    e.preventDefault();

    const data = {
        nombre_completo: document.getElementById('fc_nombre').value,
        nombre_empresa: document.getElementById('fc_empresa').value || null,
        dni_cuit: document.getElementById('fc_cuit').value,
        telefono: document.getElementById('fc_telefono').value,
        frecuencia_recompra_dias: document.getElementById('fc_recompra').value ? parseInt(document.getElementById('fc_recompra').value) : null
    };

    try {
        const response = await fetch(`${API_URL}/clientes/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            document.getElementById('form-cliente').reset();
            toggleDrawer('drawer-nuevo-cliente');
            cargarClientes();
        } else {
            const error = await response.json();
            alert("Error: " + error.detail);
        }
    } catch (error) {
        console.error("Error al guardar cliente:", error);
    }
}

async function cargarClientes(filtro = "") {
    try {
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        // Hacemos 2 peticiones en paralelo: traemos clientes y TODOS los trabajos para calcular saldos
        const [respClientes, respTrabajos] = await Promise.all([
            fetch(url),
            fetch(`${API_URL}/trabajos/`)
        ]);
        
        const clientes = await respClientes.json();
        const trabajos = await respTrabajos.json();
        
        renderizarTablaClientes(clientes, trabajos);
    } catch (error) {
        console.error("Error cargando clientes:", error);
    }
}

document.getElementById('clientSearch')?.addEventListener('keyup', (e) => {
    cargarClientes(e.target.value);
});

function renderizarTablaClientes(clientes, trabajos) {
    const tbody = document.querySelector('#tableClientes tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    clientes.forEach(cliente => {
        // LÓGICA DE SALDO: Sumamos el precio_venta de los trabajos que el cliente tenga "Pendiente de Pago"
        const trabajosDelCliente = trabajos.filter(t => t.cliente_id === cliente.id);
        const saldoDeudor = trabajosDelCliente
            .filter(t => t.estado === "Pendiente de Pago")
            .reduce((suma, t) => suma + t.precio_venta, 0);

        const colorSaldo = saldoDeudor > 0 ? "var(--red)" : "var(--green)";

        tbody.innerHTML += `
            <tr class="client-row">
              <td><b>${cliente.nombre_completo}</b></td>
              <td>${cliente.nombre_empresa || '-'}</td>
              <td class="tnum">${cliente.dni_cuit}</td>
              <td class="tnum" style="color: ${colorSaldo}; font-weight: 600;">$ ${saldoDeudor.toLocaleString('es-AR')}</td>
              <td>
                <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
              </td>
            </tr>
        `;
    });
}

async function abrirFicha(id) {
    toggleDrawer('drawer-cliente');
    document.getElementById('ficha-nombre').innerText = "Cargando datos...";
    document.getElementById('ficha-cuit').innerText = "";
    
    try {
        const [respClientes, respTrabajos] = await Promise.all([
            fetch(`${API_URL}/clientes/`),
            fetch(`${API_URL}/trabajos/`)
        ]);
        
        const clientes = await respClientes.json();
        const trabajos = await respTrabajos.json();
        const cliente = clientes.find(c => c.id === id);
        
        if (cliente) {
            const trabajosDelCliente = trabajos.filter(t => t.cliente_id === id);
            
            // 1. Calculamos el saldo deudor
            const saldoDeudor = trabajosDelCliente
                .filter(t => t.estado === "Pendiente de Pago")
                .reduce((suma, t) => suma + t.precio_venta, 0);

            // Inyectamos datos fijos
            document.getElementById('ficha-nombre').innerText = cliente.nombre_completo;
            document.getElementById('ficha-cuit').innerText = `DNI/CUIT: ${cliente.dni_cuit} | Tel: ${cliente.telefono}`;
            const lblSaldo = document.getElementById('ficha-saldo');
            lblSaldo.innerText = `$ ${saldoDeudor.toLocaleString('es-AR')}`;
            lblSaldo.style.color = saldoDeudor > 0 ? "var(--red)" : "var(--green)";
            
            // 2. Armamos el histórico dinámico
            const tbodyHistorico = document.querySelector('#drawer-cliente table tbody');
            tbodyHistorico.innerHTML = '';

            if (trabajosDelCliente.length === 0) {
                tbodyHistorico.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--muted);">Sin historial de trabajos.</td></tr>';
            } else {
                // Agrupamos los trabajos por nombre del producto
                const conteoProductos = {};
                trabajosDelCliente.forEach(t => {
                    if(!conteoProductos[t.descripcion_producto]) {
                        conteoProductos[t.descripcion_producto] = { veces: 0, volumen_total: 0 };
                    }
                    conteoProductos[t.descripcion_producto].veces += 1;
                    conteoProductos[t.descripcion_producto].volumen_total += t.cantidad;
                });

                // Lo renderizamos en la tabla
                for (const [producto, stats] of Object.entries(conteoProductos)) {
                    const volumenPromedio = Math.round(stats.volumen_total / stats.veces);
                    const frecuencia = stats.veces > 1 ? "Recurrente" : "Única vez";
                    
                    tbodyHistorico.innerHTML += `
                        <tr>
                            <td><b>${producto}</b></td>
                            <td>${frecuencia} (${stats.veces} pedidos)</td>
                            <td class="tnum">${volumenPromedio} u.</td>
                        </tr>
                    `;
                }
            }
        }
    } catch (error) {
        console.error("Error al cargar la ficha:", error);
        document.getElementById('ficha-nombre').innerText = "Error al cargar";
    }
}


// ==========================================
// 5. TRABAJOS: CREACIÓN Y TABLERO KANBAN
// ==========================================
async function cargarSelectorClientes() {
    try {
        const response = await fetch(`${API_URL}/clientes/`);
        const clientes = await response.json();
        const selector = document.getElementById('ft_cliente_id');
        if(!selector) return;

        selector.innerHTML = '<option value="">Seleccione un cliente...</option>';
        clientes.forEach(c => {
            selector.innerHTML += `<option value="${c.id}">${c.nombre_completo} ${c.nombre_empresa ? '('+c.nombre_empresa+')' : ''}</option>`;
        });
    } catch (error) {
        console.error("Error al cargar selector:", error);
    }
}

async function guardarTrabajo(e) {
    e.preventDefault();

    const data = {
        cliente_id: document.getElementById('ft_cliente_id').value,
        descripcion_producto: document.getElementById('ft_descripcion').value,
        cantidad: parseInt(document.getElementById('ft_cantidad').value),
        precio_venta: parseFloat(document.getElementById('ft_precio').value),
        costo_total_materiales: parseFloat(document.getElementById('ft_costo').value),
        forma_pago_heredada: document.getElementById('ft_pago').value,
        fecha_creacion: new Date().toISOString().split('T')[0],
        estado: "Pendiente de Pago" 
    };

    try {
        const response = await fetch(`${API_URL}/trabajos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            document.getElementById('form-trabajo').reset();
            toggleDrawer('drawer-nuevo-trabajo');
            cargarTrabajos(); 
            cargarClientes(); // Importante: Recargamos clientes para que se actualice el saldo
        } else {
            const error = await response.json();
            alert("Error al guardar trabajo: " + error.detail);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}

function permitirSoltar(ev) {
    ev.preventDefault();
}

function arrastrarTarjeta(ev, id) {
    ev.dataTransfer.setData("text", id);
}

async function soltarTarjeta(ev, nuevoEstado) {
    ev.preventDefault();
    const id = ev.dataTransfer.getData("text");
    const tarjeta = document.getElementById(`card-${id}`);
    const columna = ev.target.closest('.kanban-col');
    
    if (columna && tarjeta) {
        columna.appendChild(tarjeta);
    }

    try {
        await fetch(`${API_URL}/trabajos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        
        cargarTrabajos();
        cargarClientes(); // Recargamos para que el saldo baje si se mueve de "Pendiente de Pago" a "En Diseño"
    } catch (error) {
        console.error("Error al actualizar estado:", error);
    }
}

async function cargarTrabajos() {
    try {
        const response = await fetch(`${API_URL}/trabajos/`);
        const trabajos = await response.json();
        
        const respClientes = await fetch(`${API_URL}/clientes/`);
        const clientes = await respClientes.json();
        
        const cols = {
            "Pendiente de Pago": document.getElementById('col-pendiente'),
            "En Diseño": document.getElementById('col-diseno'),
            "En Producción": document.getElementById('col-produccion'),
            "Entregado": document.getElementById('col-entregado')
        };
        
        Object.values(cols).forEach(col => {
            if(col) col.innerHTML = col.firstElementChild.outerHTML; 
        });

        trabajos.forEach(t => {
            const cliente = clientes.find(c => c.id === t.cliente_id);
            const nombreCliente = cliente ? cliente.nombre_completo : 'Desconocido';
            const bordeColor = t.estado === "En Diseño" ? "var(--magenta)" : (t.estado === "En Producción" ? "var(--amber)" : "transparent");
            
            const tarjetaHTML = `
                <div class="kanban-card" id="card-${t.id}" draggable="true" ondragstart="arrastrarTarjeta(event, '${t.id}')" style="border-left: 4px solid ${bordeColor}; cursor: grab;">
                  <div class="client">${nombreCliente}</div>
                  <div class="job">${t.cantidad}x ${t.descripcion_producto}</div>
                  <div class="date">${t.fecha_creacion} - $${t.precio_venta}</div>
                </div>
            `;
            
            if (cols[t.estado]) {
                cols[t.estado].innerHTML += tarjetaHTML;
            } else if (cols["Pendiente de Pago"]) {
                cols["Pendiente de Pago"].innerHTML += tarjetaHTML;
            }
        });
    } catch (error) {
        console.error("Error cargando trabajos:", error);
    }
}

// ==========================================
// 6. HERRAMIENTAS EXTRAS (PDF, WA, DASHBOARD)
// ==========================================
function abrirWhatsApp(telefono) {
    const numeroLimpio = telefono.replace(/\D/g, '');
    const mensaje = encodeURIComponent("¡Hola! Te escribo de Gráfica Viamonte. ");
    window.open(`https://wa.me/549${numeroLimpio}?text=${mensaje}`, '_blank');
}

function generarInformeDiarioPDF() {
    const elemento = document.querySelector('.kanban-board');
    const opciones = {
        margin:       10,
        filename:     'Hoja_Ruta_Taller.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2 },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'landscape' }
    };
    html2pdf().set(opciones).from(elemento).save();
}

function calcularTotalPresupuesto() {
    let inputs = document.querySelectorAll('.costo-input');
    let subtotal = 0;
    inputs.forEach(input => {
        let val = parseFloat(input.value) || 0;
        subtotal += val;
    });
    
    let porcentaje = parseFloat(document.getElementById('porcentaje-ganancia').value) || 0;
    let ganancia = subtotal * (porcentaje / 100);
    let total = subtotal + ganancia;

    document.getElementById('lbl-subtotal').innerText = "$" + subtotal.toLocaleString('es-AR');
    document.getElementById('lbl-ganancia').innerText = "$" + ganancia.toLocaleString('es-AR');
    document.getElementById('lbl-total').innerText = "$" + total.toLocaleString('es-AR');
}

function cargarDashboard() {
    const ctx = document.getElementById('chartComparativo');
    if (!ctx) return;

    new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Marzo', 'Abril', 'Mayo', 'Junio'],
        datasets: [
          { label: 'Ingresos', data: [420000, 510000, 480000, 630000], backgroundColor: '#22824F', borderRadius: 6 },
          { label: 'Gastos', data: [280000, 310000, 290000, 350000], backgroundColor: '#C13B3B', borderRadius: 6 }
        ]
      },
      options: { responsive: true }
    });
}