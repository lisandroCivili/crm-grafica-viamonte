// Arranque: control de acceso, respaldo y carga inicial de modulos.

// ==========================================
// CONTROL DE ACCESO
// ==========================================
// usuarioActual (quien entro y con que rol) vive en core.js, junto al resto
// del estado compartido.

document.addEventListener("DOMContentLoaded", async () => {
    // Sin token no hay nada que preguntar: telon arriba. (El overlay ya viene
    // visible desde el HTML, asi que no llega a verse la app por detras.)
    if (!tokenGuardado()) return;

    // Con token guardado le preguntamos al backend si sigue valiendo, en vez de
    // confiar en una marca del navegador. Si vencio, arrancariamos una app que
    // no puede pedir un solo dato y todo se veria vacio sin explicacion.
    try {
        const resp = await fetch(`${API_URL}/auth/me`);
        if (!resp.ok) return; // el interceptor de core.js ya limpio el token
        usuarioActual = await resp.json();
    } catch (e) {
        console.error("No se pudo verificar la sesion", e);
        return;
    }

    entrarAlSistema();
});

// Baja el telon y arranca la app. Lo comparten el login y el arranque con una
// sesion ya iniciada, para que el orden de las cosas sea uno solo.
function entrarAlSistema() {
    document.getElementById('login-overlay').style.display = 'none';

    // Antes de cargar nada: la pantalla tiene que quedar armada segun el puesto.
    aplicarPermisos();
    iniciarApp();
    abrirPestanaInicial();
}

// Saca de la vista lo que este puesto no maneja. El backend igual lo rechaza;
// esto evita que alguien apriete un boton para recibir un "no tenes permiso".
function aplicarPermisos() {
    document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
        if (!puedeVerPestana(item.dataset.tab)) item.style.display = 'none';
    });

    // Todo lo que muestra plata: saldos de cuenta corriente, el respaldo de la
    // base, el alta de trabajos (que exige precio).
    if (!puedeVerPlata()) {
        document.querySelectorAll('.solo-admin').forEach(el => {
            el.style.display = 'none';
            // Un input required escondido bloquea el submit del formulario
            // entero: el navegador no lo puede validar ni enfocar, y el usuario
            // ve que el boton Guardar no hace nada, sin ningun mensaje.
            el.querySelectorAll?.('[required]').forEach(campo => { campo.required = false; });
        });
    }
}

// La ultima pestaña abierta, salvo que sea una que este puesto ya no ve (o que
// nunca vio: el default historico es el Dashboard, que es solo del dueño).
function abrirPestanaInicial() {
    const guardada = localStorage.getItem('viamonte_last_tab');
    const primeraPropia = document.querySelector('.nav-item[data-tab]:not([style*="none"])');

    const tabId = (guardada && puedeVerPestana(guardada)) ? guardada : primeraPropia?.dataset.tab;
    if (!tabId) return;

    const boton = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (boton) switchTab(tabId, boton);
}

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
            const data = await resp.json();
            localStorage.setItem(TOKEN_KEY, data.access_token);
            usuarioActual = data.usuario;
            entrarAlSistema();
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
    localStorage.removeItem(TOKEN_KEY);
    usuarioActual = null;
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
// Todo se carga de una al entrar (switchTab solo muestra y esconde secciones ya
// cargadas), pero cada carga esta atada a la pestaña a la que pertenece: pedir
// el dashboard o los cheques con un puesto que no los tiene serian 403 y la
// consola llena de errores rojos.
function iniciarApp() {
    const siPuede = (tabId, ...cargas) => {
        if (puedeVerPestana(tabId)) cargas.forEach(cargar => cargar());
    };

    siPuede('tab-clientes', cargarClientes);
    siPuede('tab-dashboard', cargarDashboard);
    // cargarSelectorClientes encadena los selectores de papel, y es el UNICO
    // lugar donde se llenan: sin esto los combos de papel quedan vacios y no
    // avisa nada.
    siPuede('tab-trabajos', cargarTrabajos, cargarSelectorClientes);
    siPuede('tab-presupuestos', cargarPresupuestos);
    siPuede('tab-gastos', cargarGastos);
    siPuede('tab-stock', cargarStock);
    siPuede('tab-cheques', cargarCheques);
    siPuede('tab-asistencia', cargarPlanilla, inicializarPeriodoResumen);
    siPuede('tab-auditoria', cargarAuditoria);
    siPuede('tab-manual', cargarManual);
}

