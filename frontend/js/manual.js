// Módulo de Ayuda: trae el manual de usuario (Markdown) y lo renderiza como HTML.
// docs/manual_usuario.md en el backend es la única fuente de verdad; acá sólo
// se pinta, no se duplica contenido.

async function cargarManual() {
    const contenedor = document.getElementById('manual-contenido');
    try {
        const resp = await fetch(`${API_URL}/manual`);
        if (!resp.ok) throw new Error('No se pudo cargar el manual');
        const markdown = await resp.text();
        contenedor.innerHTML = marked.parse(markdown);
    } catch (e) {
        console.error('Error cargando el manual:', e);
        contenedor.innerHTML = '<p style="color:var(--red);">No se pudo cargar el manual. Verificá que el backend esté funcionando y recargá la página.</p>';
    }
}
