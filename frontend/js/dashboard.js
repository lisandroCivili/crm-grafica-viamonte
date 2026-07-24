// Dashboard: KPIs, graficos y reporte ejecutivo.

// ==========================================
// MÓDULO DASHBOARD Y ESTADÍSTICAS
// ==========================================

let miChartFlujo = null;
let miChartDistribucion = null;

async function cargarDashboard() {
    try {
        // 1. Traemos toda la info de la base de datos
        const [respT, respG, respC, respCl, respM] = await Promise.all([
            fetch(`${API_URL}/trabajos/`),
            fetch(`${API_URL}/gastos/`),
            fetch(`${API_URL}/cheques/`),       // <-- NUEVO
            fetch(`${API_URL}/clientes/`),      // <-- NUEVO
            fetch(`${API_URL}/movimientos/`)    // <-- para restar pagos en "morosos"
        ]);

        let trabajos = await respT.json();
        let gastos = await respG.json();
        let cheques = await respC.json();
        let clientes = await respCl.json();
        let movimientos = respM.ok ? await respM.json() : [];

        // LOGICA DE CHEQUES
        let plataEnCheques = 0;
        let plataChequesAPagar = 0;
        let htmlAlertasCheques = '';
        const hoyMs = new Date().getTime();
        const limiteMs = hoyMs + (7 * 24 * 60 * 60 * 1000); // 7 días para adelante

        cheques.forEach(ch => {
            // Sólo los recibidos son plata por cobrar: un cheque propio en cartera
            // es plata que va a SALIR, mostrarlo acá infla la caja esperada.
            const esRecibido = (ch.clasificacion || 'Recibido') === 'Recibido';
            if (ch.estado === 'En Cartera' && esRecibido) {
                plataEnCheques += Number(ch.monto);

                const fechaCobroDate = new Date(ch.fecha_cobro + 'T00:00:00');
                if (fechaCobroDate.getTime() <= limiteMs) {
                    const cli = clientes.find(c => c.id === ch.cliente_id);
                    const nomCli = cli ? (cli.nombre_completo || cli.nombre || 'Desc.') : 'Desc.';
                    const esVencido = fechaCobroDate.getTime() < hoyMs ? 'color:var(--red);' : '';
                    
                    htmlAlertasCheques += `
                        <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                            <span style="${esVencido}">📅 ${fechaCobroDate.toLocaleDateString('es-AR')} - ${esc(nomCli)}</span>
                            <span style="font-weight:bold;">$ ${fmtMoney(ch.monto)}</span>
                        </div>
                    `;
                }
            } else if (ch.estado === 'En Cartera') {
                // Emitido en cartera: cheque propio que todavía no cobraron.
                plataChequesAPagar += Number(ch.monto);
            }
        });

        // 2. Leemos la "Máquina del tiempo"
        const filtro = document.getElementById('dash-filtro-tiempo').value;

        // KPIs financieros: fuente de verdad en el backend (plata realmente
        // cobrada, ganancia proporcional a lo cobrado y conteos de trabajos).
        let kpis = null;
        try {
            const respKpi = await fetch(`${API_URL}/reportes/dashboard?filtro=${encodeURIComponent(filtro)}`);
            if (respKpi.ok) kpis = await respKpi.json();
        } catch (e) { console.error('Error cargando KPIs del dashboard:', e); }

        const hoy = new Date();
        const mesActual = hoy.getMonth();
        const anioActual = hoy.getFullYear();

        // Funciones de ayuda para filtrar por fecha
        const cumpleFiltro = (fechaStr) => {
            if (filtro === 'historico') return true;
            const f = new Date(fechaStr + 'T00:00:00');
            if (filtro === 'este_mes') return f.getMonth() === mesActual && f.getFullYear() === anioActual;
            if (filtro === 'mes_pasado') {
                let m = mesActual - 1; let a = anioActual;
                if (m < 0) { m = 11; a--; }
                return f.getMonth() === m && f.getFullYear() === a;
            }
            if (filtro === 'este_anio') return f.getFullYear() === anioActual;
            return true;
        };

        // Aplicamos el filtro a las listas
        const trabajosFiltrados = trabajos.filter(t => cumpleFiltro(t.fecha_creacion));
        const gastosFiltrados = gastos.filter(g => cumpleFiltro(g.fecha));

        // Plata estancada: trabajos que todavía dan vueltas en el taller. Este sí
        // se calcula acá porque no depende de cobranzas, sólo del estado.
        let plataEstancada = 0;
        trabajosFiltrados.forEach(t => {
            if (t.estado === 'Aprobado' || t.estado === 'En Diseño' || t.estado === 'En Producción') {
                plataEstancada += Number(t.precio_venta);
            }
        });

        let gastosPorCat = {};
        gastosFiltrados.forEach(g => {
            gastosPorCat[g.categoria] = (gastosPorCat[g.categoria] || 0) + Number(g.monto);
        });

        // Los KPIs financieros salen SOLO del backend: ingresos = plata realmente
        // cobrada, ganancia = margen proporcional a lo cobrado − gastos, y morosos
        // que contemplan cheques recibidos. El cálculo local que había acá los
        // ignoraba y mostraba deuda inflada, así que ante un fallo preferimos
        // avisar antes que dibujar números equivocados.
        const avisoError = document.getElementById('dash-error');
        if (!kpis) {
            if (avisoError) avisoError.style.display = 'block';
            ['kpi-ingresos', 'kpi-egresos', 'kpi-ganancia', 'kpi-calle',
             'kpi-trabajos-pendientes', 'kpi-sin-presupuesto'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.innerText = '—';
            });
            document.getElementById('kpi-ganancia').style.color = 'var(--muted)';
            document.getElementById('kpi-ganancia-nota').innerText = '';
            document.getElementById('kpi-ingresos-nota').innerText = '';
            document.getElementById('lista-morosos').innerHTML =
                '<div style="color:var(--muted); margin-top:10px;">No se pudo calcular la deuda de clientes.</div>';
        } else {
            if (avisoError) avisoError.style.display = 'none';

            const ingresosReales = Number(kpis.ingresos);
            const egresosPeriodo = Number(kpis.egresos);
            const gananciaNeta = Number(kpis.ganancia_neta);
            // Parte de los egresos que no restó de la ganancia por estar ya contemplada
            // en el margen de un presupuesto. Explica por qué ganancia ≠ ingresos − egresos.
            const costosPresupuestados = Number(kpis.costos_presupuestados || 0);

            // Parte de lo cobrado que no está imputada a ningún trabajo (un pago a
            // cuenta, un cheque suelto). Es plata real, pero no aporta ganancia: sin
            // trabajo no hay presupuesto del cual sacar el costo. Se muestra para que
            // se pueda imputar después, en vez de quedar escondida en la diferencia
            // entre ingresos y ganancia.
            const sinImputar = Number(kpis.ingresos_sin_imputar || 0);
            document.getElementById('kpi-ingresos-nota').innerText = sinImputar > 0
                ? `Incluye $ ${fmtMoney(sinImputar)} sin imputar a un trabajo`
                : '';

            document.getElementById('kpi-ingresos').innerText = `$ ${fmtMoney(ingresosReales)}`;
            document.getElementById('kpi-egresos').innerText = `$ ${fmtMoney(egresosPeriodo)}`;
            document.getElementById('kpi-ganancia').innerText = `$ ${fmtMoney(gananciaNeta)}`;
            document.getElementById('kpi-ganancia').style.color = gananciaNeta >= 0 ? 'var(--magenta)' : 'var(--red)';
            document.getElementById('kpi-ganancia-nota').innerText = costosPresupuestados > 0
                ? `No descuenta $ ${fmtMoney(costosPresupuestados)} ya contemplados en presupuestos`
                : '';
            document.getElementById('kpi-calle').innerText = `$ ${fmtMoney(Number(kpis.plata_en_la_calle))}`;
            document.getElementById('kpi-trabajos-pendientes').innerText = kpis.trabajos_pendientes;
            document.getElementById('kpi-sin-presupuesto').innerText = kpis.trabajos_sin_presupuesto;

            const htmlMorosos = kpis.morosos.map(m => `
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line);">
                    <span><b>#${m.trabajo_id.substring(0,6).toUpperCase()}</b> - ${esc(m.descripcion_producto)}</span>
                    <span style="color:var(--red); font-weight:bold;">$ ${fmtMoney(Number(m.saldo_pendiente))}</span>
                </div>
            `).join('');
            document.getElementById('lista-morosos').innerHTML = htmlMorosos || '<div style="color:var(--green); font-weight:bold; margin-top:10px;">¡No hay morosos! 🎉 Todos los entregados están pagados.</div>';
        }

        // KPIs que no dependen del backend de reportes.
        document.getElementById('alerta-estancada').innerText = `$ ${fmtMoney(plataEstancada)}`;
        document.getElementById('kpi-cheques').innerText = `$ ${fmtMoney(plataEnCheques)}`;
        document.getElementById('kpi-cheques-pagar').innerText = `$ ${fmtMoney(plataChequesAPagar)}`;
        document.getElementById('alerta-cheques').innerHTML = htmlAlertasCheques || '<div style="color:var(--muted); margin-top:10px;">No hay cheques por vencer esta semana.</div>';

        // 4. CÁLCULO DE BLOQUE 2 (GRÁFICOS)
        dibujarGraficoDistribucion(gastosPorCat);

        // Para el gráfico de barras armamos el flujo anual (Agrupamos por mes).
        // Ingresos reales (pagos cobrados + cheques cobrados), mismos criterios
        // que el KPI, para no dejar dos definiciones de "ingreso" conviviendo.
        // Los gastos van SIN filtrar: el gráfico es anual y ya filtra por año.
        // Pasarle gastosFiltrados hacía que con "Este mes" se compararan gastos
        // de un mes contra ingresos de todo el año.
        dibujarGraficoFlujo(movimientos, cheques, gastos, anioActual);

    } catch (e) {
        console.error("Error cargando dashboard:", e);
    }
}

function dibujarGraficoDistribucion(gastosPorCat) {
    const ctx = document.getElementById('chartDistribucion').getContext('2d');
    if (miChartDistribucion) miChartDistribucion.destroy(); // Borra el anterior si existía

    const etiquetas = Object.keys(gastosPorCat);
    const valores = Object.values(gastosPorCat);

    miChartDistribucion = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: etiquetas,
            datasets: [{
                data: valores,
                backgroundColor: ['#D5006D', '#FFC107', '#007BFF', '#28A745', '#6C757D'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 } } }
            }
        }
    });
}

function dibujarGraficoFlujo(movimientos, cheques, gastos, anio) {
    const ctx = document.getElementById('chartFlujo').getContext('2d');
    if (miChartFlujo) miChartFlujo.destroy();

    // Arrays para los 12 meses
    const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    let ingresosMes = new Array(12).fill(0);
    let egresosMes = new Array(12).fill(0);

    // Ingreso real: pagos cobrados (método distinto de Cheque)...
    movimientos.forEach(m => {
        if (m.tipo !== 'Pago' || (m.metodo || '').toLowerCase() === 'cheque') return;
        // Sin 'T00:00:00' a propósito: m.fecha ya trae hora, y un ISO con hora y
        // sin zona lo parsea JS como local (los de gastos/cheques son sólo fecha
        // y sin el sufijo caerían en UTC, por eso ahí sí va).
        const f = new Date(m.fecha);
        if (!isNaN(f) && f.getFullYear() === anio) ingresosMes[f.getMonth()] += Number(m.monto);
    });
    // ...más los cheques recibidos efectivamente cobrados (por su fecha de cobro).
    cheques.forEach(ch => {
        if ((ch.clasificacion || 'Recibido') !== 'Recibido' || ch.estado !== 'Cobrado') return;
        const f = new Date(ch.fecha_cobro + 'T00:00:00');
        if (!isNaN(f) && f.getFullYear() === anio) ingresosMes[f.getMonth()] += Number(ch.monto);
    });

    gastos.forEach(g => {
        const f = new Date(g.fecha + 'T00:00:00');
        if (f.getFullYear() === anio) egresosMes[f.getMonth()] += Number(g.monto);
    });

    miChartFlujo = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: meses,
            datasets: [
                {
                    label: 'Ingresos Cobrados',
                    data: ingresosMes,
                    backgroundColor: '#28A745',
                    borderRadius: 4
                },
                {
                    label: 'Gastos y Egresos',
                    data: egresosMes,
                    backgroundColor: '#DC3545',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, ticks: { callback: function(value) { return '$' + value.toLocaleString('es-AR'); } } }
            },
            plugins: {
                legend: { position: 'top' }
            }
        }
    });
}

async function generarPDFEjecutivo() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Capturamos los datos filtrados directamente desde la pantalla
    const selector = document.getElementById('dash-filtro-tiempo');
    const periodo = selector.options[selector.selectedIndex].text;
    
    const ingresos = document.getElementById('kpi-ingresos').innerText;
    const egresos = document.getElementById('kpi-egresos').innerText;
    const ganancia = document.getElementById('kpi-ganancia').innerText;
    const calle = document.getElementById('kpi-calle').innerText;
    const taller = document.getElementById('alerta-estancada').innerText;

    // --- ENCABEZADO FORMAL ---
    doc.setFontSize(24);
    doc.setTextColor(213, 0, 109); // Color Magenta corporativo
    doc.text("Gráfica Viamonte", 14, 22);
    
    doc.setFontSize(14);
    doc.setTextColor(50, 50, 50);
    doc.text("Reporte Ejecutivo de Resultados", 14, 32);
    
    doc.setFontSize(11);
    doc.setTextColor(100, 100, 100);
    doc.text(`Período analizado: ${periodo}`, 14, 42);
    doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-AR')}`, 14, 48);

    // --- TABLA DE RESULTADOS PRINCIPALES ---
    doc.autoTable({
        startY: 55,
        head: [['Concepto Financiero', 'Monto Registrado']],
        body: [
            ['Total Ingresos (Cobrado)', ingresos],
            ['Total Egresos (Gastos Operativos)', egresos],
            ['Ganancia Neta del Período', ganancia]
        ],
        theme: 'grid',
        headStyles: { fillColor: [40, 40, 40], fontSize: 12 },
        bodyStyles: { fontSize: 12, textColor: [50, 50, 50] },
        alternateRowStyles: { fillColor: [245, 245, 245] },
        columnStyles: {
            0: { fontStyle: 'bold' },
            1: { halign: 'right', fontStyle: 'bold' }
        }
    });

    // --- TABLA DE ESTADO Y ALERTA ---
    doc.autoTable({
        startY: doc.lastAutoTable.finalY + 15,
        head: [['Indicadores de Producción y Riesgo', 'Capital Involucrado']],
        body: [
            ['Capital estancado en taller (En producción)', taller],
            ['Cuentas por cobrar (Trabajos entregados)', calle]
        ],
        theme: 'grid',
        headStyles: { fillColor: [213, 0, 109], fontSize: 11 }, // Cabecera magenta para alertas
        bodyStyles: { fontSize: 11 },
        columnStyles: {
            0: { fontStyle: 'bold' },
            1: { halign: 'right', textColor: [200, 0, 0], fontStyle: 'bold' }
        }
    });

    // --- PIE DE PÁGINA ---
    doc.setFontSize(9);
    doc.setTextColor(150, 150, 150);
    doc.text("Documento generado automáticamente por el sistema de gestión CRM Viamonte.", 14, 280);

    // Descarga del archivo
    doc.save(`Reporte_Directorio_${periodo.replace(/ /g, '_')}.pdf`);
}

