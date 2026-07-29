// Navegacion: pestanas, drawers y acordeones.

function switchTab(tabId, element) {
    document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    if(element) element.classList.add('active');

    // En el celular el menú se abre encima del contenido: si no se cierra acá,
    // elegís una sección y el menú queda tapando justo lo que fuiste a ver.
    cerrarSidebar();

    // Guardamos la última pestaña visitada en la memoria
    localStorage.setItem('viamonte_last_tab', tabId);
}

// El menú lateral en pantalla chica. En la PC no hace nada visible: ahí el
// sidebar está siempre a la vista y el botón que llama a esto no se muestra.
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

function cerrarSidebar() {
    document.getElementById('sidebar').classList.remove('open');
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

