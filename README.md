# CRM Gráfica Viamonte

**Sistema interno de gestión para gráficas: centraliza operaciones, reduce trabajo manual y proporciona trazabilidad completa de todos los movimientos.**

Administra clientes, presupuestos, trabajos, stock, pagos, cheques, gastos, asistencia y reportes financieros en una plataforma unificada.

## 🎯 Resumen

Este proyecto nace de una necesidad real: una gráfica operaba con múltiples hojas de cálculo y registros dispersos. El CRM centraliza todo.

**Problemas que resuelve:**
- ❌ Saldos de clientes inconsistentes entre sistemas
- ❌ Seguimiento manual de estado de trabajos
- ❌ Control de stock sin historial
- ❌ Gestión caótica de cheques y pagos
- ❌ Análisis de rentabilidad por trabajo imposible

**Resultado:** Una plataforma operativa que automatiza workflows, mantiene consistencia de datos y proporciona visibilidad en tiempo real.

## ✨ Funcionalidades principales

- **Gestión de clientes** — ficha, saldo, historial de transacciones
- **Presupuestos** — múltiples ítems por comprobante, conversión a trabajo
- **Tablero de producción** — seguimiento visual de trabajos por estados
- **Cuenta corriente** — registro de pagos y movimientos de clientes
- **Gestión de cheques** — historial completo de cambios de estado
- **Control de stock** — historial de altas, compras, ajustes y consumo
- **Registro de gastos** — vínculo opcional a trabajos para análisis de costo
- **Planilla de asistencia** — seguimiento de horas y resumen por empleado
- **Dashboard financiero** — indicadores de ingresos, egresos, ganancia neta
- **Generación de PDFs** — presupuestos y órdenes de producción
- **Backup automático** — descarga de la base de datos

## 🛠 Stack tecnológico

| Componente | Tecnología |
|-----------|-----------|
| Backend | FastAPI |
| ORM | SQLAlchemy |
| Validación | Pydantic v2 |
| Base de datos | SQLite |
| Frontend | HTML, CSS, JavaScript (vanilla) |
| Generación de PDFs | ReportLab |
| Servidor | Uvicorn / Gunicorn |

## 📊 Módulos del sistema

| Módulo | Descripción |
|--------|-----------|
| Clientes | Ficha completa, saldo, historial |
| Presupuestos | Creación, edición, conversión a trabajo |
| Trabajos | Seguimiento por etapas de producción |
| Movimientos | Registro de pagos y transacciones |
| Cheques | Gestión y seguimiento de cambios de estado |
| Stock | Inventario con historial de movimientos |
| Gastos | Registro con vínculo a trabajos |
| Asistencia | Planilla de horas trabajadas |
| Reportes | Dashboard con KPIs financieros |
| Autenticación | Control de acceso por usuario |

## 🔄 Flujo de trabajo típico

1. Se carga o selecciona un cliente existente
2. Se crea un presupuesto con uno o varios ítems
3. El presupuesto se convierte en trabajo (queda bloqueado para consistencia)
4. El trabajo avanza por etapas de producción (diseño → producción → entrega)
5. Se registran pagos, cheques y gastos asociados
6. El sistema calcula automáticamente saldos, costo y ganancia neta
7. **Toda la operación queda trazada** para auditoría y consulta posterior

## ⚡ Características destacadas

- **Presupuestos multi-ítem:** Un presupuesto puede contener varios productos con precios independientes
- **Inmutabilidad operativa:** Un presupuesto convertido en trabajo queda bloqueado para evitar inconsistencias
- **Historial completo:** Stock, cheques, movimientos — todo conserva su historial de cambios
- **Lógica de saldos consistente:** Los saldos de clientes se calculan idénticamente en toda la aplicación
- **Dashboard separado:** Ingresos reales vs. egresos vs. costos presupuestados vs. ganancia neta
- **Frontend integrado:** Se sirve desde el mismo backend (una única instancia a deployar)

## 🚀 Instalación

### Requisitos
- Python 3.11 o superior
- pip

### Pasos

1. **Cloná el repositorio**
   ```bash
   git clone https://github.com/lisandrocivili/crm-grafica-viamonte.git
   cd crm-grafica-viamonte
   ```

2. **Creá un entorno virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalá las dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Iniciá el servidor**
   ```bash
   uvicorn main:app --reload
   ```

5. **Accedé a la aplicación**
   - Abrí tu navegador en `http://localhost:8000`
   - Usuario y contraseña: (incluidos en la documentación local)

## 📁 Estructura del proyecto

```
crm-grafica-viamonte/
├── main.py                 # Punto de entrada de la aplicación
├── requirements.txt        # Dependencias de Python
├── app/
│   ├── routes/            # Endpoints de la API
│   ├── models/            # Modelos de base de datos
│   ├── schemas/           # Schemas de validación (Pydantic)
│   └── utils/             # Funciones auxiliares
├── static/                # HTML, CSS, JavaScript
├── templates/             # Templates HTML
└── README.md
```

## 🔧 Decisiones técnicas

### ¿Por qué FastAPI?
- **Performance:** 3x más rápido que Django en benchmarks
- **Validación automática:** Pydantic valida datos en entrada/salida sin boilerplate
- **Documentación automática:** Swagger UI integrada (útil para debugging)
- **Simple:** Perfecto para una startup o pequeño proyecto que necesita iterar rápido

### ¿Por qué SQLite?
- **Almacenamiento local:** La gráfica controla sus datos en su propia máquina
- **Cero configuración:** No requiere servidor de DB separado
- **Portabilidad:** Fácil de respaldar y migrar

### ¿Por qué ReportLab en vez de html2pdf?
- **Control fino de diseño:** Posibilidad de crear layouts complejos (ej. encabezado diagonal con logo)
- **Rendimiento:** Genera PDFs rápido sin dependencias de navegador
- **Edge cases manejados:** Resuelve problemas de renderizado que html2pdf tiene

### ¿Por qué el frontend integrado?
- **Deploy simple:** Una sola aplicación Python para subir a producción
- **Sincronización:** Frontend y backend siempre en la misma versión

## 📊 Caso de uso real

**Cliente:** Gráfica Viamonte (San Miguel de Tucumán, Argentina)
- **Operación anterior:** Hojas de cálculo + registros manuales
- **Problemas:** Inconsistencias de datos, seguimiento lento, análisis difícil
- **Resultado con CRM:** 
  - ✅ Operación centralizada
  - ✅ Trazabilidad completa de cada movimiento
  - ✅ Reportes instantáneos de rentabilidad
  - ✅ Reducción de errores administrativos

## 🛠 Tecnologías y aprendizajes clave

Este proyecto me permitió profundizar en:
- **Diseño de APIs REST:** Endpoints bien estructurados, validación de entrada, errores claros
- **Relaciones complejas en BD:** Clientes → Presupuestos → Trabajos → Movimientos (integridad referencial)
- **Generación de documentos:** PDFs con diseño personalizado (headers, footers, tablas)
- **Flujos de negocio:** Modelar reglas operativas (ej. bloqueo de presupuestos tras conversión a trabajo)
- **UX para usuarios no-técnicos:** Interfaz clara para usuarios sin experiencia en software

## 🚧 Mejoras futuras

- [ ] Autenticación con contraseña hasheada (actualmente básica)
- [ ] Exportación a Excel de reportes
- [ ] API pública para integraciones externas
- [ ] Multiusuario con roles (admin, usuario, solo lectura)
- [ ] Notificaciones de tareas pendientes

## 📄 Licencia

Este proyecto es privado. Contactar al autor para permisos de uso.

## 👨‍💻 Autor

**Lisandro Civili**  
Email: lisandro.civili@gmail.com  
GitHub: [@lisandrocivili](https://github.com/lisandrocivili)  
LinkedIn: [linkedin.com/in/lisandro-civili](https://www.linkedin.com/in/lisandro-civili)

---

**¿Preguntas o sugerencias?** Abrí un issue en el repo o contactame directamente.
