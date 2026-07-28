// Stock: carrito de compras, ajustes rapidos e historial.

// ==========================================
// MÓDULO DE STOCK E INVENTARIO
// ==========================================

let idStockEditando = null;
let carritoCompras = [];      // ítems pendientes de enviar a POST /stock/compras
let stockCacheCompras = [];   // artículos existentes para el selector de recompra

function abrirDrawerStock() {
    idStockEditando = null;
    carritoCompras = [];
    document.getElementById('titulo-drawer-stock').innerText = 'Registrar Compra';
    document.getElementById('form-stock').reset();
    cargarArticulosExistentes();
    setModoEdicionStock(false);
    onArticuloExistenteChange(); // restaura visibilidad de todos los grupos (llama a onUnidadStockChange)
    renderCarritoStock();
    toggleDrawer('drawer-nuevo-stock');
}

async function cargarArticulosExistentes() {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        stockCacheCompras = await resp.json();
        const sel = document.getElementById('fs_articulo_existente');
        sel.innerHTML = '<option value="">— Artículo nuevo —</option>' +
            stockCacheCompras.map(a => `<option value="${a.id}">${esc(a.nombre)} (${a.cantidad} ${a.unidad})</option>`).join('');
    } catch (e) { console.error("Error cargando artículos existentes:", e); }
}

// Muestra u oculta un bloque del form de stock.
function setVisibleStock(idGrupo, visible) {
    document.getElementById(idGrupo).style.display = visible ? '' : 'none';
}

function setModoEdicionStock(editando) {
    setVisibleStock('grupo-stock-existente', !editando);
    document.getElementById('btn-agregar-carrito').style.display = editando ? 'none' : '';
    document.getElementById('btn-guardar-stock').innerText = editando ? 'Guardar cambios' : 'Registrar compra';
    if (editando) setVisibleStock('carrito-stock', false);
}

function onArticuloExistenteChange() {
    const id = document.getElementById('fs_articulo_existente').value;
    const esRecompra = !!id;
    // El nombre, la categoría y el mínimo pertenecen a la ficha: en recompra no se tocan.
    setVisibleStock('grupo-stock-nombre', !esRecompra);
    setVisibleStock('grupo-stock-datos', !esRecompra);
    setVisibleStock('grupo-stock-minimo', !esRecompra);
    if (esRecompra) {
        const art = stockCacheCompras.find(a => a.id === id);
        if (art) {
            const tieneDimensiones = art.largo_cm && art.ancho_cm && art.gramaje_grs;
            document.getElementById('fs_unidad').value = tieneDimensiones ? 'Kg' : art.unidad;
            document.getElementById('fs_largo').value = art.largo_cm || '';
            document.getElementById('fs_ancho').value = art.ancho_cm || '';
            document.getElementById('fs_gramaje').value = art.gramaje_grs || '';
        }
    }
    onUnidadStockChange();
}

function onUnidadStockChange() {
    const esKg = document.getElementById('fs_unidad').value === 'Kg';
    const editandoConDims = !!idStockEditando && document.getElementById('fs_largo').value !== '';
    setVisibleStock('grupo-stock-kg', esKg || editandoConDims);
    setVisibleStock('grupo-stock-peso', esKg);
    setVisibleStock('grupo-stock-cantidad', !esKg);
    document.getElementById('lbl-fs-costo').innerText = esKg ? 'Costo total del paquete ($)' : 'Costo Unit. ($)';
}

// Arma el ítem de compra a partir del form. Devuelve null (con aviso) si falta algo.
function armarItemCompraStock() {
    const articuloId = document.getElementById('fs_articulo_existente').value || null;
    const unidad = document.getElementById('fs_unidad').value;
    const esKg = unidad === 'Kg';
    const nombre = document.getElementById('fs_nombre').value.trim();

    if (!articuloId && !nombre) {
        Swal.fire({ title: 'Falta el nombre', text: 'Ingresá el nombre del insumo o elegí un artículo existente.', icon: 'warning' });
        return null;
    }

    const item = { articulo_id: articuloId, unidad: unidad };
    if (!articuloId) {
        item.nombre = nombre;
        item.categoria = document.getElementById('fs_categoria').value;
        item.proveedor = document.getElementById('fs_proveedor').value || null;
        item.stock_minimo = parseFloat(document.getElementById('fs_minimo').value) || 0;
    }

    const costo = parseFloat(document.getElementById('fs_costo').value);
    if (esKg) {
        item.largo_cm = parseFloat(document.getElementById('fs_largo').value);
        item.ancho_cm = parseFloat(document.getElementById('fs_ancho').value);
        item.gramaje_grs = parseFloat(document.getElementById('fs_gramaje').value);
        item.peso_total_kg = parseFloat(document.getElementById('fs_peso').value);
        if (!(item.largo_cm > 0) || !(item.ancho_cm > 0) || !(item.gramaje_grs > 0) || !(item.peso_total_kg > 0)) {
            Swal.fire({ title: 'Faltan datos del papel', text: 'Para comprar por Kg completá largo, ancho, gramaje y peso del paquete.', icon: 'warning' });
            return null;
        }
        if (costo > 0) item.costo_total = costo;
    } else {
        item.cantidad = parseFloat(document.getElementById('fs_cantidad').value);
        if (!(item.cantidad > 0)) {
            Swal.fire({ title: 'Cantidad inválida', text: 'La cantidad debe ser mayor a cero.', icon: 'warning' });
            return null;
        }
        if (!isNaN(costo)) item.costo_unitario = costo;
    }

    const art = articuloId ? stockCacheCompras.find(a => a.id === articuloId) : null;
    item._etiqueta = `${art ? art.nombre : nombre} — ${esKg ? item.peso_total_kg + ' Kg' : item.cantidad + ' ' + unidad}`;
    return item;
}

function agregarAlCarritoStock() {
    const item = armarItemCompraStock();
    if (!item) return;
    carritoCompras.push(item);
    renderCarritoStock();
    // Form limpio para cargar el siguiente ítem
    document.getElementById('form-stock').reset();
    onArticuloExistenteChange();
}

function quitarDelCarritoStock(indice) {
    carritoCompras.splice(indice, 1);
    renderCarritoStock();
}

function renderCarritoStock() {
    const lista = document.getElementById('carrito-stock-lista');
    const btn = document.getElementById('btn-guardar-stock');
    if (carritoCompras.length === 0) {
        setVisibleStock('carrito-stock', false);
        btn.innerText = 'Registrar compra';
        return;
    }
    setVisibleStock('carrito-stock', true);
    lista.innerHTML = carritoCompras.map((item, i) => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--line); font-size:13px;">
            <span>${item._etiqueta}</span>
            <button type="button" class="btn secondary" style="font-size:11px; padding:2px 6px;" onclick="quitarDelCarritoStock(${i})">✖</button>
        </div>`).join('');
    btn.innerText = `Registrar compra (${carritoCompras.length})`;
}

async function editarArticuloStock(id) {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        const stock = await resp.json();
        const art = stock.find(s => s.id === id);
        if (!art) return;

        document.getElementById('form-stock').reset();
        idStockEditando = id;
        carritoCompras = [];
        document.getElementById('titulo-drawer-stock').innerText = 'Editar Insumo';

        document.getElementById('fs_nombre').value = art.nombre;
        document.getElementById('fs_categoria').value = art.categoria;
        document.getElementById('fs_proveedor').value = art.proveedor || '';
        document.getElementById('fs_unidad').value = art.unidad;
        document.getElementById('fs_costo').value = art.costo_unitario;
        document.getElementById('fs_cantidad').value = art.cantidad;
        document.getElementById('fs_minimo').value = art.stock_minimo;
        document.getElementById('fs_largo').value = art.largo_cm || '';
        document.getElementById('fs_ancho').value = art.ancho_cm || '';
        document.getElementById('fs_gramaje').value = art.gramaje_grs || '';

        setModoEdicionStock(true);
        setVisibleStock('grupo-stock-nombre', true);
        setVisibleStock('grupo-stock-datos', true);
        setVisibleStock('grupo-stock-minimo', true);
        onUnidadStockChange();
        toggleDrawer('drawer-nuevo-stock');
    } catch (e) { console.error("Error al abrir edición de stock:", e); }
}

async function guardarArticuloStock(e) {
    e.preventDefault();
    const restore = disableButtonOnSubmit(e);

    try {
        if (idStockEditando) {
            // Edición: PATCH con los campos descriptivos + cantidad (queda registrada en el historial si cambió).
            const largo = document.getElementById('fs_largo').value;
            const ancho = document.getElementById('fs_ancho').value;
            const gramaje = document.getElementById('fs_gramaje').value;
            const payload = {
                nombre: document.getElementById('fs_nombre').value,
                categoria: document.getElementById('fs_categoria').value,
                proveedor: document.getElementById('fs_proveedor').value || null,
                unidad: document.getElementById('fs_unidad').value,
                stock_minimo: parseFloat(document.getElementById('fs_minimo').value),
                costo_unitario: parseFloat(document.getElementById('fs_costo').value),
                cantidad: parseFloat(document.getElementById('fs_cantidad').value),
                largo_cm: largo ? parseFloat(largo) : null,
                ancho_cm: ancho ? parseFloat(ancho) : null,
                gramaje_grs: gramaje ? parseFloat(gramaje) : null,
                motivo: "Corrección por edición de ficha"
            };
            const resp = await fetch(`${API_URL}/stock/${idStockEditando}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                idStockEditando = null;
                toggleDrawer('drawer-nuevo-stock');
                cargarStock();
                Swal.fire({ title: 'Artículo actualizado', icon: 'success', timer: 1000, showConfirmButton: false });
            }
        } else {
            // Si el form tiene un ítem a medio cargar (o el carrito está vacío), se suma solo.
            const formTieneDatos = document.getElementById('fs_nombre').value.trim() !== '' ||
                document.getElementById('fs_articulo_existente').value !== '';
            if (carritoCompras.length === 0 || formTieneDatos) {
                const item = armarItemCompraStock();
                if (!item) return; // el aviso ya se mostró
                carritoCompras.push(item);
                renderCarritoStock();
            }

            // _etiqueta es solo para la UI del carrito: no se manda al backend.
            const payload = carritoCompras.map(({ _etiqueta, ...item }) => item);
            const resp = await fetch(`${API_URL}/stock/compras`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                carritoCompras = [];
                toggleDrawer('drawer-nuevo-stock');
                cargarStock();
                cargarSelectoresPapel(); // el stock de papel pudo cambiar
                Swal.fire({ title: 'Compra registrada', icon: 'success', timer: 1200, showConfirmButton: false });
            } else {
                const err = await resp.json().catch(() => ({}));
                Swal.fire({ title: 'No se pudo registrar la compra', text: detalleError(err, 'Error inesperado'), icon: 'error' });
            }
        }
    } catch (error) { console.error("Error guardando stock:", error); }
    finally { restore(); }
}

async function eliminarArticuloStock(id, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || '🗑️';

    const confirmacion = await Swal.fire({
        title: '¿Eliminar este artículo?',
        text: "También se borra su historial de ajustes.",
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
        const resp = await fetch(`${API_URL}/stock/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            cargarStock();
            Swal.fire('¡Eliminado!', 'El artículo fue borrado del inventario.', 'success');
        }
    } catch (e) {
        console.error("Error al eliminar artículo:", e);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}

async function cargarStock() {
    try {
        const resp = await fetch(`${API_URL}/stock/`);
        if (!resp.ok) return;
        
        const stock = await resp.json();
        const tbody = document.querySelector('#tableStock tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        let capitalTotal = 0;
        let alertasTotales = 0;

        if (stock.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--muted);">Inventario vacío.</td></tr>';
            document.getElementById('lbl-valor-inventario').innerText = '$ 0';
            document.getElementById('lbl-alertas-stock').innerText = '0';
            return;
        }

        stock.forEach(s => {
            // Cálculos para la cabecera
            capitalTotal += (Number(s.cantidad) * Number(s.costo_unitario));
            const enAlerta = Number(s.cantidad) <= Number(s.stock_minimo);
            if (enAlerta) alertasTotales++;

            let badgeEstado = enAlerta
                ? `<span style="background:var(--red); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">¡COMPRAR!</span>`
                : `<span style="background:var(--green); color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold;">Suficiente</span>`;
            
            // Le agregamos un botón de historial
            badgeEstado += `<br><button class="btn secondary" style="font-size:10px; padding:2px 4px; margin-top:5px;" onclick="verHistorialStock('${s.id}', '${s.nombre}')">Ver Historial</button>`;

            // EL SISTEMA HÍBRIDO DE CANTIDAD: Botones y tipeo manual
            const controlCantidad = `
                <div style="display:flex; align-items:center; justify-content:center; gap:5px;">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, -1, '${s.unidad}', this)">-</button>
                    <input type="number" id="stk-input-${s.id}" value="${s.cantidad}" style="width:70px; text-align:center; padding:5px; border:1px solid var(--line); border-radius:4px;" onchange="ajustarStockRapido('${s.id}', ${s.cantidad}, 'manual', '${s.unidad}', this)">
                    <button class="btn secondary" style="padding:4px 8px; font-weight:bold;" onclick="ajustarStockRapido('${s.id}', ${s.cantidad}, 1, '${s.unidad}', this)">+</button>
                    <span style="font-size:11px; color:var(--muted);">${s.unidad}</span>
                </div>
            `;

            tbody.innerHTML += `
                <tr style="${enAlerta ? 'background-color: var(--red-soft);' : ''}">
                    <td><b>${s.nombre}</b></td>
                    <td>
                        <span style="font-size:11px; color:var(--ink); font-weight:600;">${s.categoria}</span><br>
                        <span style="font-size:11px; color:var(--muted);">🏭 ${s.proveedor || 'Sin proveedor'}</span>
                    </td>
                    <td class="tnum" style="text-align:center;">$ ${fmtMoney(s.costo_unitario)}</td>
                    <td style="text-align:center;">${controlCantidad}</td>
                    <td style="text-align:center;">${badgeEstado}</td>
                    <td style="text-align:center;">
                        <button class="btn secondary" style="font-size:12px; padding:6px;" onclick="editarArticuloStock('${s.id}')">✏️</button>
                        ${permisos().borrar ? `<button class="btn secondary" style="font-size:12px; padding:6px; border-color:var(--red); color:var(--red);" onclick="eliminarArticuloStock('${s.id}', this)">🗑️</button>` : ''}
                    </td>
                </tr>
            `;
        });

        // Refrescar paneles
        document.getElementById('lbl-valor-inventario').innerText = `$ ${fmtMoney(capitalTotal)}`;
        document.getElementById('lbl-alertas-stock').innerText = alertasTotales;

    } catch (e) { console.error("Error cargando stock:", e); }
}

async function ajustarStockRapido(id, cantidadActual, accion, unidad, button) {
    if (!button) button = event?.target;
    const originalText = button?.innerText || (accion === 1 ? '+' : '-');

    let nuevaCantidad;
    let motivo = "Ajuste rápido";

    if (accion === 'manual') {
        nuevaCantidad = parseFloat(document.getElementById(`stk-input-${id}`).value) || 0;
        if (nuevaCantidad === cantidadActual) return;

        const dif = nuevaCantidad - cantidadActual;
        const textoDif = dif > 0 ? `Ingreso de +${dif}` : `Salida de ${dif}`;

        const { value: razon, isDismissed } = await Swal.fire({
            title: 'Justificar movimiento',
            text: `Estás haciendo un ${textoDif} ${unidad}. ¿Cuál es el motivo? (Ej: Compra, Uso en Trabajo #123, Rotura)`,
            input: 'text',
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            inputValidator: (value) => {
                if (!value) return '¡Tenés que escribir un motivo!'
            }
        });

        if (isDismissed) {
            cargarStock();
            return;
        }
        motivo = razon;
    } else {
        nuevaCantidad = cantidadActual + accion;
        motivo = accion > 0 ? "Ajuste manual rápido (+1)" : "Ajuste manual rápido (-1)";
    }

    if (nuevaCantidad < 0) nuevaCantidad = 0;

    if (button) {
        button.disabled = true;
        button.innerText = 'Actualizando...';
    }

    try {
        const resp = await fetch(`${API_URL}/stock/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: nuevaCantidad, motivo: motivo })
        });

        if (resp.ok) cargarStock();
    } catch (e) { console.error("Error actualizando cantidad:", e); }
    finally {
        if (button) {
            button.disabled = false;
            button.innerText = originalText;
        }
    }
}


// NUEVA FUNCIÓN: Ver Historial (Pop-up lindo)
async function verHistorialStock(id, nombreArticulo) {
    try {
        const resp = await fetch(`${API_URL}/stock/${id}/historial`);
        const historial = await resp.json();
        
        if (historial.length === 0) {
            Swal.fire('Historial', 'No hay movimientos registrados para este artículo.', 'info');
            return;
        }

        let htmlLista = '<div style="max-height: 300px; overflow-y: auto; text-align: left;">';
        htmlLista += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">';
        htmlLista += '<tr style="border-bottom: 1px solid #ddd; color: #666;"><th>Fecha</th><th>Movimiento</th><th>Motivo</th></tr>';
        
        historial.forEach(h => {
            const fechaLocale = new Date(h.fecha).toLocaleString('es-AR', {dateStyle: 'short', timeStyle: 'short'});
            const colorDif = h.diferencia > 0 ? 'var(--green)' : 'var(--red)';
            const signo = h.diferencia > 0 ? '+' : '';
            
            htmlLista += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 4px;">${fechaLocale}</td>
                    <td style="padding: 8px 4px; color: ${colorDif}; font-weight: bold;">${signo}${h.diferencia}</td>
                    <td style="padding: 8px 4px;">${h.motivo}</td>
                </tr>
            `;
        });
        htmlLista += '</table></div>';

        Swal.fire({
            title: `Historial: ${nombreArticulo}`,
            html: htmlLista,
            width: 600,
            confirmButtonColor: '#D5006D',
            confirmButtonText: 'Cerrar'
        });

    } catch(e) { console.error("Error trayendo historial:", e); }
}

