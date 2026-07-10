// Ruta base de tu backend local en FastAPI
const API_URL = 'http://localhost:8000/api';

// --- 1. LÓGICA DE LOGIN ---
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
            document.getElementById('login-error').style.display = 'block';
        }
    } catch (error) {
        console.error("Error conectando al backend. ¿Está corriendo main.py?", error);
        alert("No se pudo conectar con el servidor local.");
    }
});

// --- 2. INICIALIZACIÓN DE LA APP ---
function iniciarApp() {
    cargarClientes();
    cargarDashboard();
    cargarTrabajos();
}

// --- 3. FUNCIONES DE FETCH (CONEXIÓN A FASTAPI) ---

async function cargarClientes(filtro = "") {
    try {
        // Le pegamos al endpoint que armamos en routers/clientes.py
        let url = `${API_URL}/clientes/`;
        if (filtro) url += `?buscar=${filtro}`;

        const response = await fetch(url);
        const clientes = await response.json();
        renderizarTablaClientes(clientes);
    } catch (error) {
        console.error("Error cargando clientes:", error);
    }
}

// Escuchamos el buscador avanzado en tiempo real
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
              <td class="tnum">$ 0.00</td> <!-- Acá luego conectamos el saldo -->
              <td>
                <button class="btn secondary" style="font-size:12px; padding:6px 12px;" onclick="abrirFicha('${cliente.id}')">Ver Ficha</button>
                <button class="btn" style="background:#25D366; padding:6px; margin-left:4px;" onclick="abrirWhatsApp('${cliente.telefono}')">WA</button>
              </td>
            </tr>
        `;
    });
}

// --- 4. INTEGRACIÓN WHATSAPP NATIVA ---
function abrirWhatsApp(telefono) {
    // Limpiamos el número de espacios o guiones
    const numeroLimpio = telefono.replace(/\D/g, '');
    const mensaje = encodeURIComponent("¡Hola! Te escribo de Gráfica Viamonte. ");
    window.open(`https://wa.me/549${numeroLimpio}?text=${mensaje}`, '_blank');
}

// --- 5. GENERACIÓN DE REPORTES PDF ---
function generarInformeDiarioPDF() {
    // Apuntamos al contenedor del tablero Kanban
    const elemento = document.querySelector('.kanban-board');
    const opciones = {
        margin:       10,
        filename:     'Hoja_Ruta_Taller.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2 },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'landscape' }
    };
    
    // La librería hace el render visual y te descarga el archivo
    html2pdf().set(opciones).from(elemento).save();
}

// --- 6. CALCULADOR DE PRESUPUESTOS (Dinámico) ---
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

// --- 7. GRÁFICOS CON CHART.JS ---
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