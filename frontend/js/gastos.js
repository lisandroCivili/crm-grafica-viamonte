// Gastos: carga, informe mensual y ABM.

// ==========================================
// MÓDULO DE GASTOS
// ==========================================

let idGastoEditando = null;
// Última lista de trabajos traída para el select del drawer. La guardamos para
// que editarGasto pueda recuperar un trabajo ya entregado sin pedirla de nuevo.
let trabajosParaGasto = [];
// Categoría cuyo costo ya está contemplado en el margen del presupuesto.
// Mismo valor que CATEGORIA_COSTO_PRESUPUESTADO en calculos.py.
const CATEGORIA_COSTO_PRESUPUESTADO = 'Costo Presupuestado';

// Muestra la aclaración de la categoría sólo cuando aplica.
function actualizarAyudaCategoriaGasto() {
    const ayuda = document.getElementById('fg_ayuda_categoria');
    if (!ayuda) return;
    const esCosteado = document.getElementById('fg_categoria').value === CATEGORIA_COSTO_PRESUPUESTADO;
    ayuda.style.display = esCosteado ? 'block' : 'none';
}

async function abrirDrawerGasto() {
    idGastoEditando = null;
    document.getElementById('titulo-drawer-gasto').innerText = 'Registrar Salida de Dinero';
    document.getElementById('form-gasto').reset();
    document.getElementById('fg_fecha').value = fechaHoyLocal();

    try {
        const respT = await fetch(`${API_URL}/trabajos/`);
        if (respT.ok) {
            const trabajos = await respT.json();
            trabajosParaGasto = trabajos;
            const selectT = document.getElementById('fg_trabajo_id');
            selectT.innerHTML = '<option value="">Ninguno (Gasto general del taller)</option>';
            
            // Filtramos para mostrar solo los que están en proceso (Aprobados, en Diseño, etc.)
            const activos = trabajos.filter(t => t.estado !== 'Entregado' && t.estado !== 'Cancelado').reverse();
            activos.forEach(t => {
                const shortId = t.id.substring(0,6).toUpperCase();
                selectT.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</option>`;
            });
        }
    } catch(e) { console.error(e); }

    actualizarAyudaCategoriaGasto();
    toggleDrawer('drawer-nuevo-gasto');
}

// El select sólo lista trabajos activos, así que un gasto de un trabajo ya
// entregado no encontraría su opción y el vínculo se perdería en silencio al
// guardar. Le agregamos la opción que falta para que eso no pase.
function asegurarOpcionTrabajoGasto(trabajoId) {
    const selectT = document.getElementById('fg_trabajo_id');
    if (!trabajoId || selectT.querySelector(`option[value="${trabajoId}"]`)) return;

    const t = trabajosParaGasto.find(x => x.id === trabajoId);
    const shortId = trabajoId.substring(0, 6).toUpperCase();
    const detalle = t ? `${t.cantidad}x ${t.descripcion_producto}` : 'trabajo no encontrado';
    const estado = t ? t.estado.toLowerCase() : 'sin datos';
    selectT.innerHTML += `<option value="${trabajoId}">(${estado}) #${shortId} - ${detalle}</option>`;
}

// Abre el drawer de gasto en modo edición, precargado con los datos del gasto elegido
async function editarGasto(id) {
    try {
        const resp = await fetch(`${API_URL}/gastos/`);
        const gastos = await resp.json();
        const g = gastos.find(x => x.id === id);
        if (!g) return;

        await abrirDrawerGasto(); // Prepara el drawer (llena el select de trabajos y resetea)
        idGastoEditando = id;
        document.getElementById('titulo-drawer-gasto').innerText = 'Editar Gasto';

        document.getElementById('fg_categoria').value = g.categoria;
        document.getElementById('fg_concepto').value = g.concepto;
        asegurarOpcionTrabajoGasto(g.trabajo_id);
        document.getElementById('fg_trabajo_id').value = g.trabajo_id || '';
        document.getElementById('fg_metodo').value = g.metodo_pago;
        document.getElementById('fg_comprobante').value = g.comprobante;
        document.getElementById('fg_responsable').value = g.responsable || 'General';
        document.getElementById('fg_monto').value = g.monto;
        document.getElementById('fg_fecha').value = g.fecha;
        actualizarAyudaCategoriaGasto();
    } catch (e) { console.error("Error al abrir edición de gasto:", e); }
}

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
            sumaTotal += Number(g.monto); // Vamos sumando la plata

            let colorCat = 'var(--ink)';
            if(g.categoria === 'Insumos') colorCat = 'var(--blue)';
            else if(g.categoria === 'Servicios') colorCat = 'var(--amber)';
            else if(g.categoria === 'Sueldos') colorCat = 'var(--magenta)';
            else if(g.categoria === CATEGORIA_COSTO_PRESUPUESTADO) colorCat = 'var(--green)';

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
                            💳 ${g.metodo_pago} | 🧾 ${g.comprobante} | 👤 ${g.responsable || 'General'}
                        </span>
                    </td>
                    <td class="tnum" style="color:var(--red); font-weight:bold;">$ ${fmtMoney(g.monto)}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarGasto('${g.id}')">✏️ Editar</button>
                        <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarGasto('${g.id}', this)">🗑️ Borrar</button>
                    </td>
                </tr>
            `;
        });

        // 4. ACTUALIZAR EL TOTAL EN PANTALLA
        document.getElementById('lbl-total-gastos').innerText = `$ ${fmtMoney(sumaTotal)}`;

    } catch (e) {
        console.error("Error cargando gastos:", e);
    }
}

async function guardarGasto(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);
    const tr_id = document.getElementById('fg_trabajo_id').value;
    const montoGasto = parseFloat(document.getElementById('fg_monto').value);

    // El gasto tiene que ser un número mayor a 0.
    if (isNaN(montoGasto) || montoGasto <= 0) {
        Swal.fire('Monto inválido', 'El gasto tiene que ser un número mayor a 0.', 'warning');
        restore();
        return;
    }

    // Un costo presupuestado no resta de la ganancia: sin trabajo asociado no
    // hay margen contra el cual compensarlo y el gasto desaparecería del cálculo.
    const categoria = document.getElementById('fg_categoria').value;
    if (categoria === CATEGORIA_COSTO_PRESUPUESTADO && !tr_id) {
        Swal.fire(
            'Falta el trabajo',
            'Un gasto de categoría "Costo Presupuestado" tiene que estar asociado a un trabajo, porque su costo ya está contemplado en ese presupuesto. Si es un gasto general del taller, elegí otra categoría.',
            'warning'
        );
        restore();
        return;
    }

    const payload = {
        categoria: categoria,
        concepto: document.getElementById('fg_concepto').value,
        monto: montoGasto,
        fecha: document.getElementById('fg_fecha').value,
        metodo_pago: document.getElementById('fg_metodo').value,
        comprobante: document.getElementById('fg_comprobante').value,
        responsable: document.getElementById('fg_responsable').value,
        trabajo_id: tr_id ? tr_id : null
    };

    try {
        const url = idGastoEditando ? `${API_URL}/gastos/${idGastoEditando}` : `${API_URL}/gastos/`;
        const metodo = idGastoEditando ? 'PUT' : 'POST';
        const resp = await fetch(url, {
            method: metodo,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            const titulo = idGastoEditando ? '¡Gasto actualizado!' : '¡Salida registrada!';
            idGastoEditando = null;
            toggleDrawer('drawer-nuevo-gasto');
            cargarGastos();
            Swal.fire({ title: titulo, icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const error = await resp.json().catch(() => ({}));
            Swal.fire('No se pudo guardar', detalleError(error), 'error');
        }
    } catch (error) {
        console.error("Error al guardar gasto:", error);
        Swal.fire('Error de conexión', 'No se pudo guardar el gasto.', 'error');
    } finally {
        restore();
    }
}

const MESES_INFORME = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

// Abre un selector de mes/año y genera el informe imprimible de gastos.
async function abrirInformeGastos() {
    const hoy = new Date();
    const opcionesMes = MESES_INFORME
        .map((m, i) => `<option value="${i}" ${i === hoy.getMonth() ? 'selected' : ''}>${m}</option>`)
        .join('');

    const { value: datos } = await Swal.fire({
        title: 'Informe de Gastos',
        html: `
            <p style="font-size:13px; color:#666; margin-bottom:12px;">Elegí el período a imprimir.</p>
            <select id="inf-mes" class="swal2-input" style="width:auto;">${opcionesMes}</select>
            <input id="inf-anio" type="number" class="swal2-input" style="width:120px;" value="${hoy.getFullYear()}">
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Generar PDF',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#D5006D',
        preConfirm: () => {
            const mes = parseInt(document.getElementById('inf-mes').value, 10);
            const anio = parseInt(document.getElementById('inf-anio').value, 10);
            if (isNaN(anio) || anio < 2000) {
                Swal.showValidationMessage('Ingresá un año válido.');
                return false;
            }
            return { mes, anio };
        }
    });

    if (datos) generarInformeGastos(datos.mes, datos.anio);
}

async function generarInformeGastos(mes, anio) {
    try {
        const resp = await fetch(`${API_URL}/gastos/`);
        if (!resp.ok) throw new Error('No se pudieron traer los gastos.');
        const gastos = await resp.json();

        // Filtramos por mes/año (el + 'T00:00:00' evita el desfase de zona horaria).
        const delPeriodo = gastos.filter(g => {
            const f = new Date(g.fecha + 'T00:00:00');
            return f.getMonth() === mes && f.getFullYear() === anio;
        }).sort((a, b) => new Date(a.fecha) - new Date(b.fecha));

        if (delPeriodo.length === 0) {
            Swal.fire('Sin datos', `No hay gastos registrados en ${MESES_INFORME[mes]} ${anio}.`, 'info');
            return;
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        doc.setFontSize(22);
        doc.setTextColor(213, 0, 109);
        doc.text('Gráfica Viamonte', 14, 20);

        doc.setFontSize(14);
        doc.setTextColor(50, 50, 50);
        doc.text('Informe de Gastos', 14, 29);

        doc.setFontSize(11);
        doc.setTextColor(100, 100, 100);
        doc.text(`Período: ${MESES_INFORME[mes]} ${anio}`, 14, 37);
        doc.text(`Emitido: ${new Date().toLocaleDateString('es-AR')}`, 14, 43);

        let total = 0;
        const filas = delPeriodo.map(g => {
            total += Number(g.monto);
            return [
                new Date(g.fecha + 'T00:00:00').toLocaleDateString('es-AR'),
                g.concepto,
                g.categoria,
                g.responsable || 'General',
                `$ ${fmtMoney(g.monto)}`
            ];
        });

        doc.autoTable({
            startY: 50,
            head: [['Fecha', 'Concepto', 'Categoría', 'Responsable', 'Monto']],
            body: filas,
            foot: [['', '', '', 'TOTAL', `$ ${fmtMoney(total)}`]],
            theme: 'grid',
            headStyles: { fillColor: [40, 40, 40], fontSize: 11 },
            footStyles: { fillColor: [245, 245, 245], textColor: [213, 0, 109], fontStyle: 'bold' },
            bodyStyles: { fontSize: 10, textColor: [50, 50, 50] },
            alternateRowStyles: { fillColor: [248, 248, 248] },
            columnStyles: { 4: { halign: 'right', fontStyle: 'bold' } }
        });

        doc.save(`Informe_Gastos_${MESES_INFORME[mes]}_${anio}.pdf`);
    } catch (e) {
        console.error('Error generando informe de gastos:', e);
        Swal.fire('Error', 'No se pudo generar el informe.', 'error');
    }
}

async function eliminarGasto(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️ Borrar';

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

    if (button) {
        button.disabled = true;
        button.innerText = 'Borrando...';
    }

    try {
        await fetch(`${API_URL}/gastos/${id}`, { method: 'DELETE' });
        cargarGastos();
        Swal.fire('¡Eliminado!', 'El gasto fue borrado del sistema.', 'success');
    } catch (e) {
        console.error("Error al eliminar gasto:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

