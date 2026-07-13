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
            // Ocultamos la pantalla de login si todo está bien
            document.getElementById('login-screen').classList.add('hidden');
            // Cargamos los datos iniciales
            iniciarApp();
        } else {
            // Error 401 Unauthorized
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
    cargarTrabajos(); // AHORA SÍ ESTÁ DEFINIDA ABAJO
}

// ==========================================
// 3. UI Y NAVEGACIÓN (Lo que faltaba)
// ==========================================
function switchTab(tabId, element) {
    // Oculta todas las secciones
    document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
    // Le saca el color activo a todos los botones del menú
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    
    // Muestra la sección clickeada
    document.getElementById(tabId).classList.add('active');
    if(element) element.classList.add('active');
}

function toggleDrawer(id) {
    document.getElementById(id).classList.toggle('open');
}

// Función para el HTML estático provisorio
function abrirFichaCliente(nombre) {
    document.getElementById('ficha-nombre').innerText = nombre;
    toggleDrawer('drawer-cliente');
}

// Función para cuando la tabla se llene con la Base de Datos
function abrirFicha(id) {
    document.getElementById('ficha-nombre').innerText = "Cargando datos...";
    // Más adelante acá hacemos un fetch al cliente por su ID
    toggleDrawer('drawer-cliente');
}

// ==========================================
// 4. CONEXIÓN A LA API (FETCH)
// ==========================================
async function cargarClientes(filtro = "") {
    try {
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        const response = await fetch(url);
        const clientes = await response.json();
        renderizarTablaClientes(clientes);
    } catch (error) {
        console.error("Error cargando clientes:", error);
    }
}

async function cargarTrabajos() {
    // Función placeholder para que no explote la inicialización
    // Más adelante acá le pegamos a `${API_URL}/trabajos/`
    console.log("Cargando tablero Kanban...");
}

// Escuchador del buscador avanzado
document.getElementById('clientSearch')?.addEventListener('keyup', (e) => {
    cargarClientes(e.target.value);
});

function renderizarTablaClientes(clientes) {
    const tbody = document.querySelector('#tableClientes tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    clientes.forEach(cliente => {
        tbody.innerHTML += `
            <tr class="client-row">
              <td><b>${cliente.nombre_completo}</b></td>
              <td>${cliente.nombre_empresa || '-'}</td>
              <td class="tnum">${cliente.dni_cuit}</td>
              <td class="tnum">$ 0.00</td>
              <td>
                <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
              </td>
            </tr>
        `;
    });
}

// ==========================================
// 5. HERRAMIENTAS EXTRAS
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

// ==========================================
// CREAR CLIENTE (POST)
// ==========================================
async function guardarCliente(e) {
    e.preventDefault(); // Evita que la página se recargue

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
            cargarClientes(); // Recargamos la tabla
            alert("Cliente guardado joya.");
        } else {
            const error = await response.json();
            alert("Error: " + error.detail);
        }
    } catch (error) {
        console.error("Error al guardar cliente:", error);
    }
}

// ==========================================
// KANBAN DE TRABAJOS (GET y POST)
// ==========================================

// 1. Llenar el <select> de clientes en el formulario de trabajos
async function cargarSelectorClientes() {
    try {
        const response = await fetch(`${API_URL}/clientes/`);
        const clientes = await response.json();
        const selector = document.getElementById('ft_cliente_id');
        selector.innerHTML = '<option value="">Seleccione un cliente...</option>';
        
        clientes.forEach(c => {
            selector.innerHTML += `<option value="${c.id}">${c.nombre_completo} ${c.nombre_empresa ? '('+c.nombre_empresa+')' : ''}</option>`;
        });
    } catch (error) {
        console.error("Error al cargar selector:", error);
    }
}

// Llama a cargar el selector cuando iniciamos la app
const iniciarAppOriginal = iniciarApp;
iniciarApp = function() {
    iniciarAppOriginal();
    cargarSelectorClientes();
};

// 2. Guardar un nuevo trabajo
async function guardarTrabajo(e) {
    e.preventDefault();

    const data = {
        cliente_id: document.getElementById('ft_cliente_id').value,
        descripcion_producto: document.getElementById('ft_descripcion').value,
        cantidad: parseInt(document.getElementById('ft_cantidad').value),
        precio_venta: parseFloat(document.getElementById('ft_precio').value),
        costo_total_materiales: parseFloat(document.getElementById('ft_costo').value),
        forma_pago_heredada: document.getElementById('ft_pago').value,
        fecha_creacion: new Date().toISOString().split('T')[0], // Fecha actual YYYY-MM-DD
        estado: "Pendiente de Pago" // Estado inicial
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
            cargarTrabajos(); // Refresca el Kanban
        } else {
            const error = await response.json();
            alert("Error al guardar trabajo: " + error.detail);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}

// 3. Renderizar el tablero Kanban con datos reales
async function cargarTrabajos() {
    try {
        const response = await fetch(`${API_URL}/trabajos/`);
        const trabajos = await response.json();
        
        // Obtenemos los clientes para cruzar los nombres (ya que el trabajo solo trae el cliente_id)
        const respClientes = await fetch(`${API_URL}/clientes/`);
        const clientes = await respClientes.json();
        
        // Limpiamos los contenedores
        const cols = {
            "Pendiente de Pago": document.getElementById('col-pendiente'),
            "En Diseño": document.getElementById('col-diseno'),
            "En Producción": document.getElementById('col-produccion'),
            "Entregado": document.getElementById('col-entregado')
        };
        
        // Vaciamos el HTML de las tarjetas previas (dejando solo el <h4> del título)
        Object.values(cols).forEach(col => {
            if(col) col.innerHTML = col.firstElementChild.outerHTML; 
        });

        trabajos.forEach(t => {
            const cliente = clientes.find(c => c.id === t.cliente_id);
            const nombreCliente = cliente ? cliente.nombre_completo : 'Desconocido';
            const bordeColor = t.estado === "En Diseño" ? "var(--magenta)" : (t.estado === "En Producción" ? "var(--amber)" : "transparent");
            
            const tarjetaHTML = `
                <div class="kanban-card" style="border-left: 4px solid ${bordeColor}">
                  <div class="client">${nombreCliente}</div>
                  <div class="job">${t.cantidad}x ${t.descripcion_producto}</div>
                  <div class="date">${t.fecha_creacion} - $${t.precio_venta}</div>
                </div>
            `;
            
            // Asignamos a la columna correspondiente
            if (cols[t.estado]) {
                cols[t.estado].innerHTML += tarjetaHTML;
            } else if (cols["Pendiente de Pago"]) {
                // Fallback por si el estado es otro
                cols["Pendiente de Pago"].innerHTML += tarjetaHTML;
            }
        });
    } catch (error) {
        console.error("Error cargando trabajos:", error);
    }
}