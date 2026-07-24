// ==========================================
// NUCLEO: ESTADO GLOBAL Y HELPERS COMPARTIDOS
// ==========================================
// Este archivo va PRIMERO: define API_URL, el estado compartido y los helpers
// que usan todos los demas modulos.
//
// Los modulos se cargan como <script> clasicos y NO como ES modules, a
// proposito: index.html llama a estas funciones desde 38 onclick inline, y eso
// solo funciona si son globales. Con type="module" quedarian encerradas en el
// scope del modulo y todos los botones dejarian de responder.
//
// Como los <script> clasicos comparten el scope lexico global, las const/let de
// este archivo se ven desde los demas.

// Ruta relativa: el frontend ahora lo sirve el mismo backend (FastAPI monta
// esta carpeta), así que siempre está en el mismo origen que la API.
const API_URL = '/api';
let clienteActualFicha = null; // Guardamos qué cliente está abierto
// Trabajos de la última carga del Kanban, indexados por id. Los onclick de las
// tarjetas pasan el id y leen de acá: interpolar textos en el atributo se rompe
// con un apóstrofo en la descripción.
const trabajosPorId = new Map();

// ==========================================
// HELPER: FORMATO DE DINERO (siempre 2 decimales)
// ==========================================
// El backend es la fuente de verdad de la matemática (Decimal). Acá solo mostramos.
function fmtMoney(valor) {
    const n = Number(valor) || 0;
    return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ==========================================
// HELPER: CÓMO SE MUESTRA UN SALDO DE CUENTA CORRIENTE
// ==========================================
// Un saldo negativo NO es deuda negativa: es plata que el cliente tiene a favor
// (la seña de un trabajo que después se canceló, un pago de más). Mostrarlo como
// "-$ 5.000" en una columna que dice "Saldo" se lee como un error de cálculo, así
// que se muestra el valor absoluto y se nombra qué es. Vive acá porque el saldo se
// pinta en la tabla de clientes y en la ficha, y la regla tiene que ser una sola.
function saldoMostrable(saldo) {
    const n = Number(saldo) || 0;
    return {
        monto: `$ ${fmtMoney(Math.abs(n))}`,
        color: n > 0 ? "var(--red)" : "var(--green)",
        aclaracion: n < 0 ? "Saldo a favor" : "",
    };
}

// ==========================================
// HELPER: ESCAPE DE TEXTO PARA innerHTML
// ==========================================
// Todo el render arma HTML por interpolación. Un cliente "O'Brien" o una
// descripción con < rompían el markup (y los onclick inline). Pasar SIEMPRE
// por acá cualquier texto que venga de la base.
const ESCAPES_HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function esc(valor) {
    return String(valor ?? '').replace(/[&<>"']/g, c => ESCAPES_HTML[c]);
}

// ==========================================
// HELPER: MENSAJE DE ERROR DE LA API
// ==========================================
// El `detail` de FastAPI es un string en los HTTPException nuestros, pero un
// array de objetos en los 422 de validación de Pydantic. Devolvemos algo
// legible en los dos casos.
function detalleError(error, porDefecto = 'Revisá los datos e intentá de nuevo.') {
    const detail = error?.detail;
    if (!detail) return porDefecto;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('\n') || porDefecto;
    }
    return porDefecto;
}

// ==========================================
// HELPER: DISABLE ON SUBMIT
// ==========================================
function disableButtonOnSubmit(e) {
    const button = e.submitter || e.target.querySelector('button[type="submit"]');
    if (button) {
        button.disabled = true;
        button._originalText = button.innerText;
        button.innerText = 'Procesando...';
        return () => {
            button.disabled = false;
            button.innerText = button._originalText || 'Guardar';
        };
    }
    return () => {};
}

