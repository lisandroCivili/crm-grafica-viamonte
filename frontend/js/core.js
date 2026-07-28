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
// Quién está usando el sistema. Lo completa el login (o /auth/me al abrir con
// una sesión ya iniciada) y de ahí sale el rol con el que se arma la pantalla.
let usuarioActual = null;
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
// HELPER: HOY EN HORA LOCAL (YYYY-MM-DD)
// ==========================================
// No se usa toISOString(), que devuelve UTC: en Argentina (UTC-3) desde las
// 21:00 el UTC ya es el día siguiente, así que todo lo cargado a la noche
// -gastos, trabajos, presupuestos, cheques- quedaba fechado mañana y caía en el
// mes equivocado en los informes. Es el equivalente en el frontend de
// ahora_local() (models.py): la fecha que vale es la del taller, no la del meridiano.
function fechaHoyLocal() {
    const ahora = new Date();
    const mes = String(ahora.getMonth() + 1).padStart(2, '0');
    const dia = String(ahora.getDate()).padStart(2, '0');
    return `${ahora.getFullYear()}-${mes}-${dia}`;
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
// SESION: EL TOKEN VIAJA EN CADA PEDIDO A LA API
// ==========================================
// Se envuelve window.fetch en lugar de tocar los ~98 fetch() repartidos en los
// 11 modulos: es un solo lugar donde mirar, y olvidarse de uno significaria que
// esa pantalla deje de funcionar sin motivo aparente.
//
// Solo se toca lo que va a /api: un fetch a cualquier otro lado pasa intacto y
// sin filtrarle el token a un tercero.
const TOKEN_KEY = 'viamonte_token';
const URL_LOGIN = `${API_URL}/auth/login`;

function tokenGuardado() {
    return localStorage.getItem(TOKEN_KEY);
}

const fetchOriginal = window.fetch;
window.fetch = async (recurso, opciones = {}) => {
    const url = typeof recurso === 'string' ? recurso : (recurso?.url ?? '');
    const esPedidoALaApi = url.startsWith(API_URL);
    const token = tokenGuardado();

    if (token && esPedidoALaApi) {
        opciones = {
            ...opciones,
            headers: { ...(opciones.headers || {}), Authorization: `Bearer ${token}` },
        };
    }

    const respuesta = await fetchOriginal(recurso, opciones);

    // 401 = el token vencio o al usuario lo dieron de baja. Sin esto la pantalla
    // se llenaria de errores raros en vez de pedir que vuelva a entrar.
    //
    // El login queda afuera a proposito: ahi un 401 significa "contraseña
    // equivocada" y hay que dejar que la pantalla muestre el mensaje, no
    // recargar la pagina mientras la persona esta tipeando.
    if (respuesta.status === 401 && esPedidoALaApi && !url.startsWith(URL_LOGIN)) {
        localStorage.removeItem(TOKEN_KEY);
        location.reload();
    }
    return respuesta;
};

// ==========================================
// QUE VE CADA PUESTO
// ==========================================
// Aca NO se protege nada: lo que protege son los permisos del backend, que
// responde 403 aunque el boton este a la vista. Esto evita mostrar pantallas y
// botones que van a fallar, que es distinto.
//
// Los roles son PUESTOS, no personas (ver ROLES en seguridad.py): el dia que
// cambie quien atiende el mostrador, no se toca nada de esto.
const PERMISOS = {
    admin: {
        pestanas: null,   // null = todas
        plata: true,      // precios, saldos, cuenta corriente
        borrar: true,
        crearTrabajos: true,
    },
    encargado: {
        pestanas: ['tab-trabajos', 'tab-clientes', 'tab-stock', 'tab-asistencia', 'tab-manual'],
        plata: false,
        borrar: false,
        crearTrabajos: false,
    },
    mostrador: {
        pestanas: ['tab-trabajos', 'tab-clientes', 'tab-stock', 'tab-gastos', 'tab-manual'],
        plata: false,
        borrar: false,
        crearTrabajos: false,
    },
};

// Ante la duda, el permiso mas chico: si todavia no se sabe quien entro, no se
// muestra nada de plata.
const PERMISOS_MINIMOS = { pestanas: [], plata: false, borrar: false, crearTrabajos: false };

function permisos() {
    return PERMISOS[usuarioActual?.rol] ?? PERMISOS_MINIMOS;
}

function puedeVerPestana(tabId) {
    const habilitadas = permisos().pestanas;
    return habilitadas === null || habilitadas.includes(tabId);
}

// Usado por los render que arman HTML con importes.
function puedeVerPlata() {
    return permisos().plata;
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

