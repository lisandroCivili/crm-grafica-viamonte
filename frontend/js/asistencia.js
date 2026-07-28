// Asistencia: planilla diaria de entrada/salida y resumen por periodo.

let idEmpleadoEditando = null;

// fechaHoyLocal() vive en core.js: la usan todos los módulos que fechan algo.

// El backend manda las horas en decimal (8.5). Acá se muestran como "8h 30m",
// que es como las lee una persona.
function fmtHoras(horas) {
    if (horas === null || horas === undefined) return '—';
    const total = Number(horas);
    const h = Math.floor(total);
    const m = Math.round((total - h) * 60);
    if (!h && !m) return '—';
    return m ? `${h}h ${m}m` : `${h}h`;
}

// Preview en el cliente mientras el operador tipea. La fuente de verdad sigue
// siendo el cálculo del backend, que es el que vuelve al guardar.
function horasDeFila(entrada, salida) {
    if (!entrada || !salida) return null;
    const [he, me] = entrada.split(':').map(Number);
    const [hs, ms] = salida.split(':').map(Number);
    const minutos = (hs * 60 + ms) - (he * 60 + me);
    return minutos > 0 ? minutos / 60 : 0;
}

// ==========================================
// PLANILLA DEL DÍA
// ==========================================

function recalcularHorasFila(input) {
    const fila = input.closest('tr');
    const entrada = fila.querySelector('.fa-entrada').value;
    const salida = fila.querySelector('.fa-salida').value;
    const celda = fila.querySelector('.fa-horas');

    if (entrada && salida && horasDeFila(entrada, salida) <= 0) {
        celda.innerHTML = '<span style="color:var(--red);">⚠ revisar</span>';
        return;
    }
    celda.innerText = fmtHoras(horasDeFila(entrada, salida));
}

function renderPlanilla(datos) {
    const tbody = document.querySelector('#tablaPlanilla tbody');
    if (!tbody) return;

    if (!datos.filas.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No hay empleados cargados. Agregá uno desde el botón "Empleados".</td></tr>';
        return;
    }

    const estiloInput = 'width:100%; padding:8px; border:1px solid var(--line); border-radius:6px;';
    tbody.innerHTML = '';
    datos.filas.forEach(f => {
        tbody.innerHTML += `
            <tr data-empleado-id="${f.empleado_id}">
                <td style="font-weight:600;">${esc(f.nombre)}</td>
                <td><input type="time" class="fa-entrada" value="${f.hora_entrada || ''}" onchange="recalcularHorasFila(this)" style="${estiloInput}"></td>
                <td><input type="time" class="fa-salida" value="${f.hora_salida || ''}" onchange="recalcularHorasFila(this)" style="${estiloInput}"></td>
                <td class="tnum fa-horas" style="text-align:center; font-weight:bold;">${fmtHoras(f.horas)}</td>
                <td><input type="text" class="fa-obs" value="${esc(f.observaciones || '')}" placeholder="Franco, faltó, se fue al mediodía..." style="${estiloInput}"></td>
            </tr>
        `;
    });
}

async function cargarPlanilla() {
    const selectorFecha = document.getElementById('fa_fecha');
    if (!selectorFecha) return;

    if (!selectorFecha.value) selectorFecha.value = fechaHoyLocal();

    try {
        const resp = await fetch(`${API_URL}/asistencia/planilla?fecha=${selectorFecha.value}`);
        if (!resp.ok) return;
        renderPlanilla(await resp.json());
    } catch (e) {
        console.error("Error cargando la planilla:", e);
    }
}

async function guardarPlanilla(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);

    const fecha = document.getElementById('fa_fecha').value;
    if (!fecha) {
        Swal.fire('Falta el día', 'Elegí la fecha de la planilla.', 'warning');
        restore();
        return;
    }

    const filas = [...document.querySelectorAll('#tablaPlanilla tbody tr[data-empleado-id]')].map(tr => ({
        empleado_id: tr.dataset.empleadoId,
        hora_entrada: tr.querySelector('.fa-entrada').value || null,
        hora_salida: tr.querySelector('.fa-salida').value || null,
        observaciones: tr.querySelector('.fa-obs').value.trim() || null,
    }));

    if (!filas.length) {
        Swal.fire('No hay nada que guardar', 'Primero cargá al menos un empleado.', 'warning');
        restore();
        return;
    }

    // Se avisa acá y no se espera el 422 del backend: así el mensaje dice de
    // quién es el horario mal cargado. Comparar "HH:MM" como texto alcanza.
    const conError = filas.filter(f => f.hora_entrada && f.hora_salida && f.hora_salida <= f.hora_entrada);
    if (conError.length) {
        Swal.fire('Revisá los horarios', 'Hay alguien con la hora de salida anterior a la de entrada.', 'warning');
        restore();
        return;
    }

    try {
        const resp = await fetch(`${API_URL}/asistencia/planilla`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha, filas })
        });

        if (resp.ok) {
            // La respuesta ya trae el día guardado con las horas recalculadas
            // por el backend: se redibuja con eso y no hace falta pedirlo de nuevo.
            renderPlanilla(await resp.json());
            Swal.fire({ title: '¡Día guardado!', icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar', detalleError(error), 'error');
        }
    } catch (error) {
        console.error("Error al guardar la planilla:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar la planilla.', 'error');
    } finally {
        restore();
    }
}

// ==========================================
// ABM DE EMPLEADOS
// ==========================================

function abrirDrawerEmpleados() {
    cancelarEdicionEmpleado();
    cargarEmpleados();
    toggleDrawer('drawer-empleados');
}

async function cargarEmpleados() {
    try {
        const resp = await fetch(`${API_URL}/empleados/?incluir_inactivos=true`);
        if (!resp.ok) return;
        const empleados = await resp.json();

        const tbody = document.querySelector('#tablaEmpleados tbody');
        if (!tbody) return;

        if (!empleados.length) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--muted);">Todavía no hay empleados cargados.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        empleados.forEach(emp => {
            const estado = emp.activo
                ? '<span style="color:var(--green); font-size:12px;">● Activo</span>'
                : '<span style="color:var(--muted); font-size:12px;">○ De baja</span>';
            const botonBaja = emp.activo
                ? `<button class="btn secondary" style="font-size:12px; padding:5px;" onclick="cambiarEstadoEmpleado('${emp.id}', false)">Dar de baja</button>`
                : `<button class="btn secondary" style="font-size:12px; padding:5px;" onclick="cambiarEstadoEmpleado('${emp.id}', true)">Reactivar</button>`;

            tbody.innerHTML += `
                <tr>
                    <td>${esc(emp.nombre)}<br>${estado}</td>
                    <td style="text-align:right; white-space:nowrap;">
                        <button class="btn secondary" style="font-size:12px; padding:5px;" onclick="editarEmpleado('${emp.id}', '${esc(emp.nombre).replace(/'/g, "\\'")}')">✏️</button>
                        ${botonBaja}
                        ${permisos().borrar ? `<button class="btn secondary" style="font-size:12px; padding:5px; border-color:var(--red); color:var(--red);" onclick="eliminarEmpleado('${emp.id}', this)">🗑️</button>` : ''}
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        console.error("Error cargando empleados:", e);
    }
}

function editarEmpleado(id, nombre) {
    idEmpleadoEditando = id;
    document.getElementById('fa_nombre').value = nombre;
    document.getElementById('fa_label_empleado').innerText = 'Nuevo nombre *';
    document.getElementById('fa_guardar_empleado').innerText = 'Guardar cambios';
    document.getElementById('fa_cancelar_empleado').style.display = 'block';
    document.getElementById('fa_nombre').focus();
}

function cancelarEdicionEmpleado() {
    idEmpleadoEditando = null;
    const form = document.getElementById('form-empleado');
    if (form) form.reset();
    document.getElementById('fa_label_empleado').innerText = 'Nombre del empleado *';
    document.getElementById('fa_guardar_empleado').innerText = 'Agregar';
    document.getElementById('fa_cancelar_empleado').style.display = 'none';
}

async function guardarEmpleado(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);

    const nombre = document.getElementById('fa_nombre').value.trim();
    if (!nombre) {
        Swal.fire('Falta el nombre', 'Escribí el nombre del empleado.', 'warning');
        restore();
        return;
    }

    try {
        const url = idEmpleadoEditando ? `${API_URL}/empleados/${idEmpleadoEditando}` : `${API_URL}/empleados/`;
        const metodo = idEmpleadoEditando ? 'PUT' : 'POST';
        const resp = await fetch(url, {
            method: metodo,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre })
        });

        if (resp.ok) {
            const titulo = idEmpleadoEditando ? '¡Nombre actualizado!' : '¡Empleado agregado!';
            cancelarEdicionEmpleado();
            cargarEmpleados();
            cargarPlanilla();  // La grilla del día cambia con el alta.
            Swal.fire({ title: titulo, icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar', detalleError(error), 'error');
        }
    } catch (error) {
        console.error("Error al guardar empleado:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar el empleado.', 'error');
    } finally {
        restore();
    }
}

async function cambiarEstadoEmpleado(id, activo) {
    if (!activo) {
        const confirmacion = await Swal.fire({
            title: '¿Dar de baja?',
            text: "Va a dejar de aparecer en la planilla del día, pero las horas que ya trabajó no se pierden.",
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, dar de baja',
            cancelButtonText: 'Cancelar',
            cancelButtonColor: '#555'
        });
        if (!confirmacion.isConfirmed) return;
    }

    try {
        const resp = await fetch(`${API_URL}/empleados/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ activo })
        });

        if (resp.ok) {
            cargarEmpleados();
            cargarPlanilla();
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo actualizar', detalleError(error), 'error');
        }
    } catch (e) {
        console.error("Error al cambiar el estado del empleado:", e);
    }
}

async function eliminarEmpleado(id, button) {
    const confirmacion = await Swal.fire({
        title: '¿Borrar este empleado?',
        text: "Borrar es sólo para deshacer un alta equivocada. Si trabajó, dalo de baja en vez de borrarlo.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#555',
        confirmButtonText: 'Sí, borrarlo',
        cancelButtonText: 'Cancelar'
    });

    if (!confirmacion.isConfirmed) return;

    const originalText = button?.innerText || '🗑️';
    if (button) { button.disabled = true; button.innerText = '...'; }

    try {
        const resp = await fetch(`${API_URL}/empleados/${id}`, { method: 'DELETE' });

        if (resp.ok) {
            cargarEmpleados();
            cargarPlanilla();
            Swal.fire({ title: '¡Eliminado!', icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se puede borrar', detalleError(error), 'error');
        }
    } catch (e) {
        console.error("Error al eliminar empleado:", e);
    } finally {
        if (button) { button.disabled = false; button.innerText = originalText; }
    }
}

// ==========================================
// RESUMEN POR PERÍODO
// ==========================================

async function cargarResumenAsistencia() {
    const desde = document.getElementById('fa_desde').value;
    const hasta = document.getElementById('fa_hasta').value;
    const tbody = document.querySelector('#tablaResumenAsistencia tbody');
    if (!tbody) return;

    if (!desde || !hasta) {
        Swal.fire('Faltan las fechas', 'Elegí el período que querés ver.', 'warning');
        return;
    }

    try {
        const resp = await fetch(`${API_URL}/asistencia/resumen?desde=${desde}&hasta=${hasta}`);

        if (!resp.ok) {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo calcular', detalleError(error), 'error');
            return;
        }

        const resumen = await resp.json();

        if (!resumen.length) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--muted);">No hay horas cargadas en ese período.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        resumen.forEach(r => {
            tbody.innerHTML += `
                <tr>
                    <td style="font-weight:600;">${esc(r.nombre)}</td>
                    <td class="tnum" style="text-align:center;">${r.dias_trabajados}</td>
                    <td class="tnum" style="text-align:right; font-weight:bold;">${fmtHoras(r.total_horas)}</td>
                </tr>
            `;
        });
    } catch (e) {
        console.error("Error cargando el resumen de asistencia:", e);
    }
}

// Al abrir por primera vez, el resumen arranca con el mes en curso.
function inicializarPeriodoResumen() {
    const desde = document.getElementById('fa_desde');
    const hasta = document.getElementById('fa_hasta');
    if (!desde || !hasta || desde.value) return;

    const ahora = new Date();
    const mes = String(ahora.getMonth() + 1).padStart(2, '0');
    desde.value = `${ahora.getFullYear()}-${mes}-01`;
    hasta.value = fechaHoyLocal();
}
