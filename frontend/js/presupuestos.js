// Presupuestos: items, modal, conversion a trabajo y PDFs.

// ==========================================
// MÓDULO DE PRESUPUESTOS AVANZADO
// ==========================================

const LISTA_COSTOS = ["Papel", "Troquel", "Luz", "Diseño", "Chapas", "Impresión", "Barniz / Laminado", "Cordón de bolsas", "Troquelado", "Tinta", "Pegado y armado", "Empaquetado / Flete", "Corte / Encuadernación", "Gastos otros"];

let idPresupuestoVersionDe = null; // Para saber si estamos duplicando uno viejo
let idPresupuestoEditando = null; // Para saber si estamos editando un presupuesto existente (en vez de crear uno nuevo)

// Contador para IDs únicos de los selects de papel de cada tarjeta de ítem
// (cargarSelectoresPapel/sincronizarPliegosConPapel trabajan por id).
let _itemSeq = 0;

// HTML de una tarjeta de ítem del presupuesto. datos precarga los valores (al
// editar/duplicar); vacío para un ítem nuevo. Cada tarjeta es autocontenida: sus
// inputs se recolectan con querySelectorAll('.item-*') dentro de la tarjeta.
function renderItemPresupuesto(datos = {}) {
    const n = _itemSeq++;
    const papelSelId = `mp_papel_id_${n}`;
    const pliegosId = `mp_cantidad_pliegos_${n}`;
    const costos = datos.detalles_costos || {};
    const filasCostos = LISTA_COSTOS.map(c => {
        const val = (costos[c] != null) ? costos[c] : '';
        return `<div class="costo-row"><label>${c}</label><input type="number" class="input-costo" data-nombre="${esc(c)}" value="${val}" placeholder="0" oninput="recalcularPrecioItem(this)" onfocus="if(this.value=='0')this.value=''"></div>`;
    }).join('');

    return `
    <div class="item-presupuesto" data-papel-select="${papelSelId}" data-pliegos="${pliegosId}"
         style="border:1px solid var(--line); border-radius:8px; padding:15px; position:relative;">
        <button type="button" onclick="quitarItemPresupuesto(this)" title="Quitar producto"
                style="position:absolute; top:8px; right:8px; background:none; border:none; font-size:16px; cursor:pointer; color:var(--red);">🗑️</button>

        <div style="margin-bottom: 12px;">
            <label style="font-size:12px; color:var(--muted);">Producto</label>
            <input type="text" class="item-descripcion" placeholder="Ej: Bolsas 26x33x12 tipo delivery" required
                   value="${esc(datos.descripcion || '')}"
                   style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
        </div>

        <div style="display:flex; gap:12px; margin-bottom: 12px;">
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Cantidad</label>
                <input type="number" class="item-cantidad" value="${datos.cantidad != null ? datos.cantidad : 1}" min="1" required
                       oninput="recalcularPrecioItem(this)"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
            </div>
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Precio unitario</label>
                <input type="number" class="item-precio-unitario" step="0.01" min="0" value="${datos.precio_unitario != null ? datos.precio_unitario : ''}" placeholder="Ej: 265" required
                       oninput="calcularModal()"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
            </div>
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Total</label>
                <input type="text" class="item-total" readonly value="$ 0"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--magenta-soft); font-weight:bold; color:var(--magenta);">
            </div>
        </div>

        <div style="display:flex; gap:12px; margin-bottom: 12px;">
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Material / Tipo de papel</label>
                <input type="text" class="item-material" placeholder="Ej: Kraft" value="${esc(datos.material || '')}"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
            </div>
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Gramaje (g/m²)</label>
                <input type="text" class="item-gramaje" placeholder="Ej: 120" value="${esc(datos.gramaje || '')}"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
            </div>
        </div>

        <!-- Papel del stock: permite que la orden del trabajo convertido descuente
             pliegos. material/gramaje de arriba es el texto del presupuesto. -->
        <div style="display:flex; gap:12px; margin-bottom: 12px;">
            <div style="flex:2;">
                <label style="font-size:12px; color:var(--muted);">Papel del stock (opcional, para descontar)</label>
                <select id="${papelSelId}" class="item-papel-id" style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;"
                        onchange="sincronizarPliegosConPapel('${papelSelId}', '${pliegosId}')">
                    <option value="">Sin papel del stock</option>
                </select>
            </div>
            <div style="flex:1;">
                <label style="font-size:12px; color:var(--muted);">Pliegos a consumir</label>
                <input type="number" id="${pliegosId}" class="item-cantidad-pliegos" step="1" min="1" placeholder="Ej: 500" disabled
                       value="${datos.cantidad_pliegos != null ? datos.cantidad_pliegos : ''}"
                       style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
            </div>
        </div>

        <!-- Costos internos + margen: cargados acá, autocalculan el Precio unitario
             de arriba (costos × (1 + margen%) ÷ cantidad). El operador puede pisar
             ese precio a mano para redondear; tocar un costo o el margen lo recalcula. -->
        <details style="margin-bottom: 5px;" ${Object.keys(costos).length ? 'open' : ''}>
            <summary style="cursor:pointer; font-size:12px; color:var(--muted);">Costos internos y ganancia</summary>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:10px;">
                ${filasCostos}
            </div>
            <div style="display:flex; gap:12px; margin-top:10px; align-items:flex-end;">
                <div style="flex:1;">
                    <label style="font-size:12px; color:var(--muted);">% de ganancia</label>
                    <input type="number" class="item-margen" step="0.01" min="0" placeholder="Ej: 35" value="${datos.margen_ganancia != null ? datos.margen_ganancia : ''}"
                           oninput="recalcularPrecioItem(this)"
                           style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px;">
                </div>
                <div style="flex:1;">
                    <label style="font-size:12px; color:var(--muted);">Costo total del producto</label>
                    <input type="text" class="item-costo-total" readonly value="$ 0"
                           style="width:100%; padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--bg, #f7f7f7); color:var(--muted);">
                </div>
            </div>
        </details>
    </div>`;
}

// Agrega una tarjeta de ítem al contenedor y le puebla el select de papel.
async function agregarItemPresupuesto(datos = {}) {
    const cont = document.getElementById('contenedor-items');
    cont.insertAdjacentHTML('beforeend', renderItemPresupuesto(datos));
    const tarjeta = cont.lastElementChild;
    // Poblar el select de papel de esta tarjeta (por id, como el resto).
    await cargarSelectorPapelItem(tarjeta);
    // Precargar el papel elegido (al editar/duplicar) después de tener opciones.
    if (datos.papel_id) {
        const sel = tarjeta.querySelector('.item-papel-id');
        sel.value = datos.papel_id;
        sincronizarPliegosConPapel(tarjeta.dataset.papelSelect, tarjeta.dataset.pliegos);
        if (datos.cantidad_pliegos != null) {
            tarjeta.querySelector('.item-cantidad-pliegos').value = datos.cantidad_pliegos;
        }
    }
    // Muestra el costo total precargado sin pisar el precio unitario ya guardado.
    refrescarCostoTotalItem(tarjeta);
    calcularModal();
}

function quitarItemPresupuesto(btn) {
    const cont = document.getElementById('contenedor-items');
    if (cont.querySelectorAll('.item-presupuesto').length <= 1) {
        Swal.fire('Un producto como mínimo', 'El presupuesto tiene que tener al menos un producto.', 'info');
        return;
    }
    btn.closest('.item-presupuesto').remove();
    calcularModal();
}

// Puebla el select de papel de UNA tarjeta con los artículos medidos en pliegos.
async function cargarSelectorPapelItem(tarjeta) {
    const stock = await (await fetch(`${API_URL}/stock/`)).json();
    const papeles = stock.filter(a => a.unidad === 'Pliegos');
    const sel = tarjeta.querySelector('.item-papel-id');
    const actual = sel.value;
    sel.innerHTML = '<option value="">Sin papel del stock</option>' +
        papeles.map(a => `<option value="${a.id}">${esc(a.nombre)} (${a.cantidad} ${a.unidad})</option>`).join('');
    sel.value = actual;
}

async function abrirDrawerPresupuesto() {
    idPresupuestoVersionDe = null; // Reseteamos por si era nuevo
    idPresupuestoEditando = null;
    _itemSeq = 0;
    document.getElementById('modal-presupuesto').classList.remove('hidden');
    // Por defecto visible (editar lo oculta); acá lo restauramos.
    document.getElementById('mp-asociar-trabajo-row').style.display = '';
    // El número real (numero_secuencia) lo asigna el backend al guardar. Antes
    // acá se inventaba uno al azar que no coincidía con nada y cambiaba cada
    // vez que se abría el modal.
    document.getElementById('lbl-pres-id').innerHTML = `<span style="color:var(--muted); font-size:13px;">Nº (se asigna al guardar)</span>`;

    // Arrancamos con un ítem vacío. editarPresupuesto/duplicar lo limpian y
    // cargan los suyos.
    document.getElementById('contenedor-items').innerHTML = '';
    await agregarItemPresupuesto();

    try {
        const resp = await fetch(`${API_URL}/clientes/`);
        const clientes = await resp.json();
        const select = document.getElementById('mp_cliente_id');
        select.innerHTML = '<option value="">Sin cliente (borrador)</option>';
        clientes.forEach(c => select.innerHTML += `<option value="${c.id}">${esc(c.nombre_completo)}</option>`);
    } catch (e) { console.error(e); }

    // Trabajos que todavía no tienen presupuesto: se pueden asociar a este.
    try {
        const respT = await fetch(`${API_URL}/trabajos/?sin_presupuesto=true`);
        const trabajos = await respT.json();
        const selT = document.getElementById('mp_trabajo_id');
        selT.innerHTML = '<option value="">No asociar</option>';
        trabajos
            .filter(t => t.estado !== 'Cancelado')
            .forEach(t => {
                const shortId = t.id.substring(0, 6).toUpperCase();
                selT.innerHTML += `<option value="${t.id}">#${shortId} - ${t.cantidad}x ${esc(t.descripcion_producto)}</option>`;
            });
    } catch (e) { console.error(e); }

    calcularModal();
}

function cerrarModalPresupuesto() {
    document.getElementById('modal-presupuesto').classList.add('hidden');
    document.getElementById('form-presupuesto').reset();
    document.getElementById('contenedor-items').innerHTML = '';
}

// Recalcula el total de cada ítem (cantidad × precio unitario) y el total del
// presupuesto (suma de los ítems). Preview en vivo; el valor definitivo lo
// guarda el backend (Decimal).
// Autocalcula el Precio unitario de un ítem a partir de sus costos y su margen:
//   costo_total = suma de los costos cargados
//   precio_total = costo_total * (1 + margen/100)
//   precio_unitario = precio_total / cantidad
// Se dispara al tocar un costo o el margen (no al tipear el precio a mano: eso lo
// deja libre para redondear, y sólo se pierde si después se vuelve a tocar la
// calculadora). 'origen' es el input que disparó el evento; se usa sólo para
// ubicar la tarjeta.
// Suma de los costos internos de una tarjeta (costo total del producto).
function _costoTotalItem(tarjeta) {
    let total = 0;
    tarjeta.querySelectorAll('.input-costo').forEach(inp => {
        total += parseFloat(inp.value) || 0;
    });
    return total;
}

function recalcularPrecioItem(origen) {
    const tarjeta = origen.closest('.item-presupuesto');
    if (!tarjeta) return;

    const costoTotal = _costoTotalItem(tarjeta);
    const margen = parseFloat(tarjeta.querySelector('.item-margen').value) || 0;
    const cantidad = parseInt(tarjeta.querySelector('.item-cantidad').value) || 1;

    tarjeta.querySelector('.item-costo-total').value = `$ ${fmtMoney(costoTotal)}`;

    // Sin costos cargados no hay precio que calcular: se respeta lo que el
    // operador haya puesto a mano en el Precio unitario.
    if (costoTotal > 0) {
        const precioUnitario = (costoTotal * (1 + margen / 100)) / cantidad;
        // 2 decimales para no arrastrar la basura del float; el backend recuantiza.
        tarjeta.querySelector('.item-precio-unitario').value = precioUnitario.toFixed(2);
    }

    calcularModal();
}

// Refresca el label de costo total de una tarjeta SIN tocar el Precio unitario.
// Se usa al precargar (editar/duplicar): el precio ya viene guardado y aprobado,
// no hay que recalcularlo, sólo mostrar el costo.
function refrescarCostoTotalItem(tarjeta) {
    tarjeta.querySelector('.item-costo-total').value = `$ ${fmtMoney(_costoTotalItem(tarjeta))}`;
}

function calcularModal() {
    let total = 0;
    let costoTotal = 0;
    let hayCostos = false;
    document.querySelectorAll('.item-presupuesto').forEach(tarjeta => {
        const cantidad = parseInt(tarjeta.querySelector('.item-cantidad').value) || 0;
        const precioUnit = parseFloat(tarjeta.querySelector('.item-precio-unitario').value) || 0;
        const totalItem = cantidad * precioUnit;
        tarjeta.querySelector('.item-total').value = `$ ${fmtMoney(totalItem)}`;
        total += totalItem;

        // Ganancia = precio total − costo total, sumada sobre los ítems que
        // tienen costos cargados (los demás no aportan al cálculo de ganancia).
        const costoItem = _costoTotalItem(tarjeta);
        if (costoItem > 0) {
            hayCostos = true;
            costoTotal += costoItem;
        }
    });
    document.getElementById('lbl-m-total').innerText = `$ ${fmtMoney(total)}`;

    // Ganancia neta = suma de precios − suma de costos. Sólo se muestra si al
    // menos un ítem cargó costos; sin costos no hay ganancia que estimar.
    const fila = document.getElementById('lbl-m-ganancia-row');
    if (hayCostos) {
        const ganancia = total - costoTotal;
        document.getElementById('lbl-m-ganancia').innerText = `$ ${fmtMoney(ganancia)}`;
        fila.style.display = 'flex';
    } else {
        fila.style.display = 'none';
    }
}

// AGREGAR ESTA FUNCIÓN NUEVA
async function duplicarPresupuesto(id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const p = (await respP.json()).find(x => x.id === id);
        if (!p) return;

        await abrirDrawerPresupuesto(); // Prepara el modal limpio

        idPresupuestoVersionDe = id; // Clavamos la relación
        document.getElementById('lbl-pres-id').innerHTML = `<span style="color:var(--muted); font-size:13px;">Nº (se asigna al guardar)</span> <span style="color:var(--magenta); font-size:12px;">(Versión de #${id.substring(0,6).toUpperCase()})</span>`;

        document.getElementById('mp_cliente_id').value = p.cliente_id || '';
        document.getElementById('mp_estado').value = "Borrador";
        await cargarItemsEnModal(p.items);
        calcularModal();
    } catch (e) { console.error(e); }
}

// Abre el modal en modo edición, precargado con los datos del presupuesto elegido
async function editarPresupuesto(id) {
    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const p = (await respP.json()).find(x => x.id === id);
        if (!p) return;

        await abrirDrawerPresupuesto(); // Prepara el modal limpio (y resetea las banderas)

        idPresupuestoEditando = id;
        document.getElementById('lbl-pres-id').innerHTML = `Nº ${p.numero_secuencia || ''} <span style="color:var(--magenta); font-size:12px;">(Editando)</span>`;

        // Asociar a un trabajo sólo aplica al crear: al editar se oculta.
        document.getElementById('mp-asociar-trabajo-row').style.display = 'none';

        document.getElementById('mp_cliente_id').value = p.cliente_id || '';
        document.getElementById('mp_estado').value = p.estado;
        await cargarItemsEnModal(p.items);
        calcularModal();
    } catch (e) { console.error(e); }
}

// Reemplaza las tarjetas del modal por una por cada ítem del presupuesto.
async function cargarItemsEnModal(items) {
    document.getElementById('contenedor-items').innerHTML = '';
    _itemSeq = 0;
    for (const item of (items || [])) {
        await agregarItemPresupuesto(item);
    }
    // Un presupuesto siempre tiene al menos un ítem, pero por las dudas.
    if (!document.querySelector('.item-presupuesto')) {
        await agregarItemPresupuesto();
    }
}

// Recolecta los ítems de las tarjetas del modal, validando el par papel+pliegos
// por ítem. Devuelve el array o null si hay un error (ya avisado al operador).
function recolectarItemsDelModal() {
    const items = [];
    const tarjetas = document.querySelectorAll('.item-presupuesto');
    for (const [i, tarjeta] of tarjetas.entries()) {
        const descripcion = tarjeta.querySelector('.item-descripcion').value.trim();
        const cantidad = parseInt(tarjeta.querySelector('.item-cantidad').value);
        const precioUnitario = parseFloat(tarjeta.querySelector('.item-precio-unitario').value);
        const papelId = tarjeta.querySelector('.item-papel-id').value || null;
        const pliegos = parseFloat(tarjeta.querySelector('.item-cantidad-pliegos').value) || null;

        // Papel del stock: los dos campos van juntos o no van.
        if (papelId && !pliegos) {
            Swal.fire('Faltan los pliegos', `Producto ${i + 1}: elegiste un papel del stock, indicá cuántos pliegos consume para que la orden pueda descontarlos.`, 'warning');
            return null;
        }
        if (pliegos && !papelId) {
            Swal.fire('Falta el papel', `Producto ${i + 1}: cargaste una cantidad de pliegos pero no elegiste de qué papel del stock descontarlos.`, 'warning');
            return null;
        }

        // Costos internos de este ítem.
        const detalles = {};
        tarjeta.querySelectorAll('.input-costo').forEach(inp => {
            const val = parseFloat(inp.value) || 0;
            if (val > 0) detalles[inp.getAttribute('data-nombre')] = val;
        });
        const margen = parseFloat(tarjeta.querySelector('.item-margen').value);

        // Si el ítem carga costos, el % de ganancia es obligatorio: es lo que
        // convierte el costo en precio. Sin costos (precio puesto a mano) no
        // aplica y queda en null.
        const tieneCostos = Object.keys(detalles).length > 0;
        if (tieneCostos && !Number.isFinite(margen)) {
            Swal.fire('Falta el % de ganancia', `Producto ${i + 1}: cargaste costos, indicá el % de ganancia para calcular el precio.`, 'warning');
            return null;
        }

        items.push({
            descripcion,
            cantidad,
            precio_unitario: precioUnitario,
            material: tarjeta.querySelector('.item-material').value.trim() || null,
            gramaje: tarjeta.querySelector('.item-gramaje').value.trim() || null,
            papel_id: papelId,
            cantidad_pliegos: pliegos,
            detalles_costos: Object.keys(detalles).length ? detalles : null,
            margen_ganancia: Number.isFinite(margen) ? margen : null,
            orden: i,
        });
    }
    return items;
}

async function guardarPresupuestoModerno(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);

    const items = recolectarItemsDelModal();
    if (items === null) { restore(); return; }  // Error de papel/pliegos ya avisado.

    try {
        if (idPresupuestoEditando) {
            // Edición: cliente, estado y la lista completa de ítems (reemplaza).
            const payloadEdicion = {
                cliente_id: document.getElementById('mp_cliente_id').value || null,
                estado: document.getElementById('mp_estado').value,
                items,
            };
            const resp = await fetch(`${API_URL}/presupuestos/${idPresupuestoEditando}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payloadEdicion) });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
                return;
            }
            cerrarModalPresupuesto();
            cargarPresupuestos();
            Swal.fire({ title: '¡Actualizado!', text: 'Presupuesto editado con éxito', icon: 'success', timer: 1500, showConfirmButton: false });
        } else {
            const payload = {
                cliente_id: document.getElementById('mp_cliente_id').value || null,
                trabajo_asociado_id: document.getElementById('mp_trabajo_id').value || null,
                version_de: idPresupuestoVersionDe,
                estado: document.getElementById('mp_estado').value,
                fecha_creacion: new Date().toISOString().split('T')[0],
                items,
            };
            const respNuevo = await fetch(`${API_URL}/presupuestos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (!respNuevo.ok) {
                const err = await respNuevo.json().catch(() => ({}));
                Swal.fire('No se pudo guardar', err.detail || 'Error desconocido', 'error');
                return;
            }
            cerrarModalPresupuesto();
            cargarPresupuestos();
            if (typeof cargarTrabajos === "function") cargarTrabajos();
            Swal.fire({ title: '¡Guardado!', text: 'Presupuesto creado con éxito', icon: 'success', timer: 1500, showConfirmButton: false });
        }
    } catch (e) { console.error(e); }
    finally { restore(); }
}

async function eliminarPresupuesto(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este presupuesto?',
        text: "Esta acción no se puede deshacer.",
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
        button.innerText = '...';
    }

    try {
        const resp = await fetch(`${API_URL}/presupuestos/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            cargarPresupuestos();
            Swal.fire('¡Eliminado!', 'El presupuesto fue borrado del sistema.', 'success');
        } else {
            const err = await resp.json();
            Swal.fire('No se pudo eliminar', err.detail || 'Error desconocido', 'error');
        }
    } catch (e) {
        console.error("Error al eliminar presupuesto:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

async function cargarPresupuestos() {
    try {
        const [respP, respC] = await Promise.all([ fetch(`${API_URL}/presupuestos/`), fetch(`${API_URL}/clientes/`) ]);
        if(!respP.ok) return; 
        
        const presupuestos = await respP.json();
        const clientes = await respC.json();
        const tbody = document.querySelector('#tablePresupuestos tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        presupuestos.reverse().forEach(p => {
            const cliente = clientes.find(c => c.id === p.cliente_id);
            const nombreCliente = cliente ? cliente.nombre_completo : 'Sin cliente';
            const shortId = p.id.substring(0,6).toUpperCase(); // ID DEL NUEVO
            
            // Lógica de Vencimiento
            const diasPasados = Math.floor((new Date() - new Date(p.fecha_creacion)) / (1000 * 60 * 60 * 24));
            let estadoBadge = `<span style="background:var(--paper); padding:4px 8px; border-radius:4px; font-size:12px; font-weight:600;">${p.estado}</span>`;
            
            if ((p.estado === 'Borrador' || p.estado === 'Enviado') && diasPasados >= 15) {
                estadoBadge += `<br><span style="background:var(--red); color:white; padding:2px 6px; border-radius:4px; font-size:10px; display:inline-block; margin-top:4px;">⚠️ Vencido</span>`;
            }

            // Lógica de Relación (Versión de...)
            let versionBadge = '';
            if (p.version_de) {
                versionBadge = `<br><span style="font-size:10px; background:var(--magenta-soft); color:var(--magenta); padding:2px 4px; border-radius:4px; display:inline-block; margin-top:4px;">Versión de #${p.version_de.substring(0,6).toUpperCase()}</span>`;
            }

            const btnConvertir = p.convertido_a_trabajo
                ? `<button class="btn secondary" disabled style="font-size:12px; padding:6px; opacity:0.5;">Ya es Trabajo</button>`
                : `<button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--green); color:var(--green);" onclick="convertirATrabajo('${p.id}', this)">A Trabajo</button>`;

            const btnesEdicion = p.convertido_a_trabajo
                ? ''
                : `<button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarPresupuesto('${p.id}')">✏️ Editar</button>
                   <button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarPresupuesto('${p.id}', this)">🗑️</button>`;

            // Resumen de los productos: el primero, y "y N más" si hay varios.
            const items = p.items || [];
            const primero = items[0];
            let resumenItems = '<span style="color:var(--muted);">Sin productos</span>';
            if (primero) {
                resumenItems = `${primero.cantidad}x ${esc(primero.descripcion)}`;
                if (items.length > 1) {
                    resumenItems += ` <span style="font-size:11px; color:var(--muted);">y ${items.length - 1} más</span>`;
                }
            }

            tbody.innerHTML += `
                <tr>
                    <td>${p.fecha_creacion}</td>
                    <td><b>${esc(nombreCliente)}</b></td>
                    <td>
                        <span style="font-size:11px; color:var(--muted);">#${shortId}</span><br>
                        ${resumenItems}
                        ${versionBadge}
                    </td>
                    <td class="tnum" style="color:var(--magenta); font-weight:bold;">$ ${fmtMoney(p.total)}</td>
                    <td>${estadoBadge}</td>
                    <td style="display:flex; gap:5px; justify-content:center; flex-wrap:nowrap; white-space:nowrap;">
                        ${btnConvertir}
                        ${btnesEdicion}
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="duplicarPresupuesto('${p.id}')">Duplicar</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--ink);" onclick="generarPDFInterno('${p.id}')">PDF Int</button>
                        <button class="btn" style="font-size:12px; padding:6px; background:var(--blue);" onclick="generarPDFCliente('${p.id}')">PDF Cli</button>
                    </td>
                </tr>
            `;
        });
    } catch (e) { console.error(e); }
}

async function convertirATrabajo(presupuesto_id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || 'A Trabajo';
    if (button) {
        button.disabled = true;
        button.innerText = 'Procesando...';
    }

    try {
        const respP = await fetch(`${API_URL}/presupuestos/`);
        const presupuestos = await respP.json();
        const p = presupuestos.find(x => x.id === presupuesto_id);
        if (!p) throw new Error("No se encontró el presupuesto.");

        if (!p.cliente_id) {
            Swal.fire('Falta el cliente', 'Asigná un cliente al presupuesto antes de convertirlo a trabajo.', 'warning');
            return;
        }

        let cancelarAnterior = false;
        const madre = p.version_de ? presupuestos.find(x => x.id === p.version_de) : null;
        // Trabajos que generó la madre (uno por ítem convertido).
        const trabajosMadre = madre ? (madre.items || []).map(it => it.trabajo_id).filter(Boolean) : [];

        if (trabajosMadre.length) {
            const accion = await Swal.fire({
                title: 'Presupuesto Duplicado',
                text: 'Este presupuesto es una corrección/versión de otro anterior. ¿Qué hacemos con el trabajo original?',
                icon: 'question',
                showDenyButton: true,
                showCancelButton: true,
                confirmButtonText: 'Cancelar el anterior',
                denyButtonText: 'Mantener ambos',
                cancelButtonText: 'Abortar',
                confirmButtonColor: '#D5006D',
                denyButtonColor: '#555'
            });

            if (accion.isDismissed) return;
            if (accion.isConfirmed) cancelarAnterior = true;
        } else if (!p.version_de) {
            const confirmacion = await Swal.fire({
                title: '¿Pasar a Trabajo?',
                text: "Esto enviará el presupuesto al Dashboard de producción.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#D5006D',
                cancelButtonColor: '#555',
                confirmButtonText: 'Sí, enviar a Taller'
            });
            if (!confirmacion.isConfirmed) return;
        }

        // El backend crea el trabajo y marca el presupuesto en una sola transacción.
        const resp = await fetch(`${API_URL}/presupuestos/${presupuesto_id}/convertir`, { method: 'POST' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "No se pudo convertir el presupuesto.");
        }

        // La conversión ya está hecha: si falla la cancelación de algún trabajo
        // anterior avisamos, pero no la reportamos como fallida. Por eso el
        // fetch va con su propio try: un error de red acá NO significa que la
        // conversión haya fallado, y el catch de abajo diría lo contrario.
        // La versión anterior se descarta, así que su papel vuelve al stock.
        // La madre puede tener varios trabajos (uno por ítem): se cancelan todos.
        let avisoCancelacion = '';
        if (cancelarAnterior) {
            for (const trabajoId of trabajosMadre) {
                try {
                    const respCancel = await fetch(`${API_URL}/trabajos/${trabajoId}?devolver_papel=true`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ estado: "Cancelado" })
                    });
                    if (!respCancel.ok) throw new Error('respuesta no OK');
                } catch (e) {
                    console.error('Error al cancelar un trabajo anterior:', e);
                    avisoCancelacion = 'Los trabajos nuevos se crearon, pero no se pudo cancelar algún trabajo anterior. Cancelalo con el botón ✖ de su tarjeta en el Dashboard de trabajo.';
                }
            }
            // (Se eliminó el Movimiento monto:0 de "cancelado por corrección": no es plata real.)
        }

        cargarTrabajos();
        cargarPresupuestos();
        if (avisoCancelacion) {
            Swal.fire('Atención', avisoCancelacion, 'warning');
        } else {
            Swal.fire('¡Enviado!', 'El trabajo ya está en el tablero.', 'success');
        }

    } catch (e) {
        console.error(e);
        Swal.fire('No se pudo convertir', e.message, 'error');
    }
    finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

// ----------------------------------------------------
// GENERADORES DE PDF (Doble versión)
// ----------------------------------------------------
async function armarMoldeBasePDF(presupuesto_id) {
    const [respP, respC] = await Promise.all([ fetch(`${API_URL}/presupuestos/`), fetch(`${API_URL}/clientes/`) ]);
    const p = (await respP.json()).find(x => x.id === presupuesto_id);
    const c = (await respC.json()).find(x => x.id === p.cliente_id);
    return { p, c };
}

// PDF PARA EL CLIENTE (formal, formato Gráfica Viamonte)
// El PDF se arma en el backend con ReportLab (Etapa B): acá sólo se pide el
// endpoint y se dispara la descarga del archivo. El nombre viene en el header
// Content-Disposition; si por algo no llega, se arma uno con el id como fallback.
async function generarPDFCliente(presupuesto_id) {
    try {
        const resp = await fetch(`${API_URL}/presupuestos/${presupuesto_id}/pdf-cliente`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || "No se pudo generar el PDF.");
        }

        const dispo = resp.headers.get('Content-Disposition') || '';
        const match = dispo.match(/filename="?([^"]+)"?/);
        const nombreArchivo = match ? match[1] : `Presupuesto_${presupuesto_id.substring(0, 6).toUpperCase()}.pdf`;

        const blob = await resp.blob();
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(blob);
        enlace.download = nombreArchivo;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        URL.revokeObjectURL(enlace.href);
    } catch (error) {
        Swal.fire('No se pudo generar el PDF', error.message, 'error');
    }
}

// PDF INTERNO (Detalle de todos los costos e ítems del formulario)
async function generarPDFInterno(presupuesto_id) {
    const { p, c } = await armarMoldeBasePDF(presupuesto_id);
    const nombreCliente = c ? c.nombre_completo : 'Sin cliente';
    const shortId = p.id.substring(0,6).toUpperCase();
    const items = p.items || [];

    // Una sección por producto: su desglose de costos, subtotal y precio.
    let totalPresupuesto = 0;
    const secciones = items.map((it, idx) => {
        const totalItem = Number(it.cantidad) * Number(it.precio_unitario);
        totalPresupuesto += totalItem;
        const costo = Number(it.costo_materiales || 0);

        let filasCostos = '';
        for (const [nombre, monto] of Object.entries(it.detalles_costos || {})) {
            filasCostos += `<tr><td style="border:1px solid #ddd; padding:8px;">${esc(nombre)}</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$ ${fmtMoney(monto)}</td></tr>`;
        }
        if (!filasCostos) filasCostos = `<tr><td colspan="2" style="border:1px solid #ddd; padding:8px; color:#999;">Sin costos cargados</td></tr>`;

        // page-break-inside: avoid evita que un producto se corte a la mitad al
        // pasar de página; el bloque entero salta a la hoja siguiente.
        return `
        <div style="margin-top:18px; page-break-inside:avoid; break-inside:avoid;">
            <p style="font-size:13px; margin:2px 0;"><b>Producto ${idx + 1}:</b> ${it.cantidad}x ${esc(it.descripcion)}</p>
            <p style="font-size:13px; margin:2px 0;"><b>Material:</b> ${esc(it.material) || '-'} &nbsp;|&nbsp; <b>Gramaje:</b> ${it.gramaje ? esc(it.gramaje) + ' g/m²' : '-'}</p>
            <p style="font-size:13px; margin:2px 0;"><b>Precio unitario:</b> $ ${fmtMoney(it.precio_unitario)} &nbsp;|&nbsp; <b>Total:</b> $ ${fmtMoney(totalItem)}</p>
            <table style="width:100%; border-collapse:collapse; margin-top:8px; font-size:13px;">
                <tr style="background:#eee;"><th style="border:1px solid #ddd; padding:8px; text-align:left;">Ítem de Costo</th><th style="border:1px solid #ddd; padding:8px; text-align:right;">Monto</th></tr>
                ${filasCostos}
                <tr style="background:#ffe6f2;"><td style="border:1px solid #ddd; padding:8px;"><b>SUBTOTAL COSTOS</b></td><td style="border:1px solid #ddd; padding:8px; text-align:right;"><b>$ ${fmtMoney(costo)}</b></td></tr>
                <tr><td style="border:1px solid #ddd; padding:8px;">Ganancia estimada${it.margen_ganancia != null ? ` (${it.margen_ganancia}%)` : ''}</td><td style="border:1px solid #ddd; padding:8px; text-align:right;">$ ${fmtMoney(totalItem - costo)}</td></tr>
            </table>
        </div>`;
    }).join('');

    const div = document.createElement('div');
    div.style.padding = '40px'; div.style.fontFamily = 'Arial';
    div.innerHTML = `
        <h2 style="margin-bottom:6px;">[INTERNO] Hoja de Costos - #${shortId}</h2>
        <p style="font-size:13px; margin:2px 0;"><b>Cliente:</b> ${esc(nombreCliente)}</p>
        ${secciones}
        <h3 style="text-align:right; color:#D5006D; margin-top:20px;">PRECIO FINAL COBRADO: $ ${fmtMoney(totalPresupuesto)}</h3>
    `;
    // pagebreak avoid-all + css: respeta el page-break-inside:avoid de cada
    // producto para no cortar un bloque por la mitad entre páginas.
    html2pdf().set({
        margin: 10,
        filename: `Costos_Internos_${shortId}.pdf`,
        pagebreak: { mode: ['avoid-all', 'css'] },
    }).from(div).save();
}

// Informe general de trabajos a clientes. Se arma desde los presupuestos
// (el backend cruza el trabajo asociado y calcula cobrado/días de producción).
async function generarInformeTrabajosPDF() {
    try {
        const resp = await fetch(`${API_URL}/presupuestos/informe-trabajos`);
        if (!resp.ok) throw new Error('No se pudo generar el informe.');
        const filas = await resp.json();

        if (!filas.length) {
            Swal.fire('Sin datos', 'Todavía no hay presupuestos para informar.', 'info');
            return;
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'landscape' });

        doc.setFontSize(18);
        doc.setTextColor(213, 0, 109);
        doc.text('Gráfica Viamonte', 14, 16);
        doc.setFontSize(12);
        doc.setTextColor(50, 50, 50);
        doc.text('Informe general de trabajos a clientes', 14, 23);
        doc.setFontSize(9);
        doc.setTextColor(120, 120, 120);
        doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-AR')}`, 14, 29);

        doc.autoTable({
            startY: 34,
            head: [['Nro Trabajo', 'Fecha entrada', 'Cliente', 'Descripción material', 'Gramaje', 'Colores', 'Cantidad', 'Fecha entrega', 'Días prod.', 'Estado', 'Cobrado', 'Observaciones']],
            body: filas.map(f => [
                f.nro_trabajo,
                f.fecha_entrada,
                f.cliente,
                f.descripcion_material,
                f.gramaje,
                f.colores,
                f.cantidad,
                f.fecha_entrega,
                f.dias_produccion,
                f.estado,
                f.cobrado ? 'Sí' : 'No',
                f.observaciones
            ]),
            theme: 'grid',
            headStyles: { fillColor: [40, 40, 40], fontSize: 8, halign: 'center' },
            bodyStyles: { fontSize: 8, textColor: [50, 50, 50] },
            alternateRowStyles: { fillColor: [245, 245, 245] },
            columnStyles: {
                6: { halign: 'center' },
                8: { halign: 'center' },
                10: { halign: 'center' }
            }
        });

        doc.save(`Informe_Trabajos_Clientes_${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (e) {
        console.error(e);
        Swal.fire('No se pudo generar el informe', e.message, 'error');
    }
}

