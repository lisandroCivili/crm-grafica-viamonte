// Calendario de cheques: alerta de vencimientos, resumen del mes y calendario
// navegable. Se dibuja arriba de la tabla de Cheques (ver cargarCheques en cheques.js).

// Cuántos días antes del vencimiento se avisa con el cartel rojo.
const DIAS_ALERTA_CHEQUE = 3;
// Si una semana tiene más cheques propios pendientes que esto, se pinta de naranja
// para que no se amontonen los pagos.
const MAX_EMITIDOS_POR_SEMANA = 2;

// Ya pagados o cobrados: se muestran tachados y no cuentan como pendientes.
const ESTADOS_CERRADOS_CALENDARIO = ['Cobrado', 'Endosado'];

const DIAS_SEMANA_CALENDARIO = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

let chequesCalendario = [];
let clientesCalendario = [];
let mesCalendarioCheques = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

function renderCalendarioCheques(cheques, clientes) {
    // Los rechazados no tienen fecha de pago real: no entran al calendario.
    chequesCalendario = cheques.filter(ch => ch.estado !== 'Rechazado');
    clientesCalendario = clientes;
    pintarCalendarioCheques();
}

function moverCalendarioCheques(meses) {
    mesCalendarioCheques = new Date(mesCalendarioCheques.getFullYear(), mesCalendarioCheques.getMonth() + meses, 1);
    pintarCalendarioCheques();
}

function pintarCalendarioCheques() {
    const contenedor = document.getElementById('calendario-cheques');
    if (!contenedor) return;
    contenedor.innerHTML = htmlAlertaCheques() + htmlResumenCheques() + htmlMesCheques();
}

// "2026-03-15" -> Date local (sin el desfasaje de zona horaria de new Date("2026-03-15")).
function fechaDeCheque(ch) {
    const [anio, mes, dia] = ch.fecha_cobro.split('-').map(Number);
    return new Date(anio, mes - 1, dia);
}

function clavaFecha(fecha) {
    const mes = String(fecha.getMonth() + 1).padStart(2, '0');
    const dia = String(fecha.getDate()).padStart(2, '0');
    return `${fecha.getFullYear()}-${mes}-${dia}`;
}

function estaEnMesCalendario(fecha) {
    return fecha.getFullYear() === mesCalendarioCheques.getFullYear()
        && fecha.getMonth() === mesCalendarioCheques.getMonth();
}

function estaCerrado(ch) {
    return ESTADOS_CERRADOS_CALENDARIO.includes(ch.estado);
}

function esPropio(ch) {
    return ch.clasificacion === 'Emitido';
}

// Recibido: el cliente que lo entregó. Emitido: a quién se le pagó.
function nombreDeCheque(ch) {
    if (esPropio(ch)) return ch.destinatario_endoso || 'Proveedor';
    const cliente = clientesCalendario.find(c => c.id === ch.cliente_id);
    return cliente ? nombreMarca(cliente) : 'Sin cliente';
}

// Cartel rojo: pendientes que vencen en los próximos días o ya vencieron.
function htmlAlertaCheques() {
    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    const limite = new Date(hoy);
    limite.setDate(limite.getDate() + DIAS_ALERTA_CHEQUE);

    const alertas = chequesCalendario
        .filter(ch => ch.estado === 'En Cartera' && fechaDeCheque(ch) <= limite)
        .sort((a, b) => fechaDeCheque(a) - fechaDeCheque(b));
    if (!alertas.length) return '';

    const filas = alertas.map(ch => {
        const dias = Math.round((fechaDeCheque(ch) - hoy) / 86400000);
        const cuando = dias < 0 ? `vencido hace ${-dias} día(s)`
            : dias === 0 ? 'vence hoy'
            : `vence en ${dias} día(s)`;
        const accion = esPropio(ch) ? 'Pagar a' : 'Cobrar a';
        return `<li>${accion} ${esc(nombreDeCheque(ch))}: ${esc(ch.banco)} N° ${esc(ch.numero)}, $ ${fmtMoney(ch.monto)} (${cuando})</li>`;
    }).join('');

    return `
        <div style="background:var(--red); color:white; padding:12px 16px; border-radius:6px; margin-top:20px;">
            <b>⚠️ Cheques por vencer o vencidos</b>
            <ul style="margin:8px 0 0 18px;">${filas}</ul>
        </div>`;
}

// Totales pendientes del mes que se está mirando: qué hay que pagar y qué hay que cobrar.
function htmlResumenCheques() {
    const delMes = chequesCalendario.filter(ch => ch.estado === 'En Cartera' && estaEnMesCalendario(fechaDeCheque(ch)));
    const pagar = delMes.filter(esPropio);
    const cobrar = delMes.filter(ch => !esPropio(ch));
    const total = lista => lista.reduce((suma, ch) => suma + Number(ch.monto), 0);
    const nombreMes = mesCalendarioCheques.toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });

    return `
        <div style="margin-top:16px; padding:12px 16px; background:var(--paper); border-radius:6px; display:flex; gap:24px; flex-wrap:wrap;">
            <b style="text-transform:capitalize;">${nombreMes}</b>
            <span style="color:var(--red); font-weight:600;">A pagar: ${pagar.length} cheque(s), $ ${fmtMoney(total(pagar))}</span>
            <span style="color:var(--green); font-weight:600;">A cobrar: ${cobrar.length} cheque(s), $ ${fmtMoney(total(cobrar))}</span>
        </div>`;
}

function htmlChequeCalendario(ch) {
    const propio = esPropio(ch);
    const flecha = propio ? '↑' : '↓';
    const color = propio ? 'var(--red)' : 'var(--green)';
    const tachado = estaCerrado(ch) ? 'text-decoration:line-through; opacity:0.6;' : '';
    return `<div title="${esc(ch.banco)} N° ${esc(ch.numero)}" style="font-size:11px; color:white; background:${color}; padding:2px 4px; border-radius:3px; margin-top:3px; ${tachado}">
        ${flecha} ${esc(nombreDeCheque(ch))} $${fmtMoney(ch.monto)}
    </div>`;
}

function htmlMesCheques() {
    const anio = mesCalendarioCheques.getFullYear();
    const mes = mesCalendarioCheques.getMonth();
    const diasDelMes = new Date(anio, mes + 1, 0).getDate();
    // La semana arranca en lunes: el primer día cae en la columna (getDay() + 6) % 7.
    const huecosIniciales = (new Date(anio, mes, 1).getDay() + 6) % 7;

    const porDia = {};
    chequesCalendario.filter(ch => estaEnMesCalendario(fechaDeCheque(ch))).forEach(ch => {
        const clave = clavaFecha(fechaDeCheque(ch));
        if (!porDia[clave]) porDia[clave] = [];
        porDia[clave].push(ch);
    });

    // Celdas del mes con huecos vacíos al principio y al final para completar semanas.
    const celdas = [];
    for (let i = 0; i < huecosIniciales; i++) celdas.push(null);
    for (let dia = 1; dia <= diasDelMes; dia++) celdas.push(new Date(anio, mes, dia));
    while (celdas.length % 7 !== 0) celdas.push(null);

    let semanas = '';
    for (let inicio = 0; inicio < celdas.length; inicio += 7) {
        const semana = celdas.slice(inicio, inicio + 7);
        const emitidosPendientes = semana
            .filter(Boolean)
            .flatMap(dia => porDia[clavaFecha(dia)] || [])
            .filter(ch => esPropio(ch) && !estaCerrado(ch)).length;
        const fondo = emitidosPendientes > MAX_EMITIDOS_POR_SEMANA ? 'background:#fde3c4;' : '';

        const celdasHtml = semana.map(dia => {
            if (!dia) return '<div style="min-height:70px; border:1px solid var(--line, #eee);"></div>';
            const chequesDia = porDia[clavaFecha(dia)] || [];
            return `<div style="min-height:70px; border:1px solid var(--line, #eee); padding:4px; overflow:hidden;">
                <div style="font-size:12px; color:var(--muted);">${dia.getDate()}</div>
                ${chequesDia.map(htmlChequeCalendario).join('')}
            </div>`;
        }).join('');

        semanas += `<div style="display:grid; grid-template-columns:repeat(7, 1fr); ${fondo}">${celdasHtml}</div>`;
    }

    const cabecera = DIAS_SEMANA_CALENDARIO
        .map(d => `<div style="text-align:center; font-size:12px; font-weight:600; padding:4px;">${d}</div>`)
        .join('');
    const nombreMes = mesCalendarioCheques.toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });

    return `
        <div style="margin-top:16px; background:white; border-radius:6px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <button class="btn secondary" style="font-size:13px; padding:6px 12px;" onclick="moverCalendarioCheques(-1)">‹ Anterior</button>
                <b style="text-transform:capitalize;">${nombreMes}</b>
                <button class="btn secondary" style="font-size:13px; padding:6px 12px;" onclick="moverCalendarioCheques(1)">Siguiente ›</button>
            </div>
            <div style="display:grid; grid-template-columns:repeat(7, 1fr);">${cabecera}</div>
            ${semanas}
        </div>`;
}
