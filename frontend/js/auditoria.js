// Auditoría: quién modificó qué y cuándo.
//
// Pantalla de sólo lectura, únicamente para el dueño (ver PERMISOS en core.js).
// No hay botones de editar ni de borrar a propósito: un registro de auditoría
// que se puede tocar desde la misma pantalla que audita no registra nada. El
// backend tampoco expone endpoints para escribirlo.

// Cuántos movimientos se traen de una. El backend topea en 1000; con este
// número entra una jornada larga sin scrollear media hora, y si se llena
// significa que hay que acotar el rango de fechas (se avisa al pie de la tabla).
const LIMITE_AUDITORIA = 200;

// Un color por acción para poder barrer la columna con la vista: lo que
// preocupa es lo que se borró.
const COLOR_ACCION = {
    'creó': 'var(--green)',
    'editó': 'var(--ink)',
    'eliminó': 'var(--red)',
    'ingresó': 'var(--muted)',
    'intento fallido': 'var(--red)',
};

async function cargarAuditoria() {
    const tbody = document.querySelector('#tableAuditoria tbody');
    if (!tbody) return;

    // Sólo van los filtros con algo cargado: mandar entidad= vacío filtraría
    // por la entidad "" y no devolvería nada.
    const filtros = new URLSearchParams({ limite: LIMITE_AUDITORIA });
    const agregar = (clave, id) => {
        const valor = document.getElementById(id)?.value.trim();
        if (valor) filtros.set(clave, valor);
    };
    agregar('entidad', 'filtro-entidad-auditoria');
    agregar('usuario', 'filtro-usuario-auditoria');
    agregar('desde', 'filtro-desde-auditoria');
    agregar('hasta', 'filtro-hasta-auditoria');

    try {
        const resp = await fetch(`${API_URL}/auditoria/?${filtros}`);
        if (!resp.ok) return;

        const movimientos = await resp.json();
        document.getElementById('lbl-total-auditoria').innerText = movimientos.length;

        if (movimientos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No hay movimientos para este filtro.</td></tr>';
            return;
        }

        tbody.innerHTML = movimientos.map(m => `
            <tr>
                <td style="white-space: nowrap;">${new Date(m.fecha).toLocaleString('es-AR')}</td>
                <td>${esc(m.usuario_nombre)}</td>
                <td style="color: ${COLOR_ACCION[m.accion] || 'var(--ink)'}; font-weight: 600;">${esc(m.accion)}</td>
                <td><span style="color: var(--muted);">${esc(m.entidad)}</span> ${esc(m.resumen)}</td>
                <td style="color: var(--muted);">${esc(m.detalle || '—')}</td>
            </tr>
        `).join('');

        // Si vinieron justo el máximo, es muy probable que haya más atrás y que
        // lo que se está buscando no esté a la vista. Sin este aviso la lista
        // parece completa y no lo está.
        if (movimientos.length === LIMITE_AUDITORIA) {
            tbody.innerHTML += `
                <tr><td colspan="5" style="text-align:center; color:var(--muted); font-style: italic;">
                    Se muestran los ${LIMITE_AUDITORIA} más recientes. Acotá las fechas para ver más atrás.
                </td></tr>`;
        }
    } catch (e) {
        console.error('Error cargando la auditoría', e);
    }
}

function limpiarFiltrosAuditoria() {
    ['filtro-entidad-auditoria', 'filtro-usuario-auditoria',
     'filtro-desde-auditoria', 'filtro-hasta-auditoria'].forEach(id => {
        const campo = document.getElementById(id);
        if (campo) campo.value = '';
    });
    cargarAuditoria();
}
