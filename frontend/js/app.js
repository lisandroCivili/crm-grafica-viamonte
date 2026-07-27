// Arranque: control de acceso, respaldo y carga inicial de modulos.

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
    cargarManual();
}

