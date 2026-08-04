# Configuración del Servicio Demo en Railway

Este documento describe cómo armar un servicio de demostración del CRM completamente aislado de la producción, con su propia base de datos.

## ¿Por qué un servicio separado?

El usuario `demo` (con rol admin) necesita acceso a datos de ejemplo para grabar videos y hacer demostraciones en vivo. Si usara la misma base que producción, podría ver (y modificar) datos reales de clientes, trabajos, presupuestos, etc.

**Solución:** Un segundo servicio Railway (con repo y volumen propios) que comparte el código pero apunta a una base SQLite diferente. Infraestructura garantiza el aislamiento: es imposible que el usuario demo acceda a datos reales.

---

## Pasos de configuración

### 1. Clonar el repo en tu cuenta personal de GitHub

```bash
# En tu máquina local
git clone <tu-fork-del-repo> crm-viamonte-demo
cd crm-viamonte-demo
```

Este será el repo del demo, completamente separado del de producción.

### 2. Crear un nuevo servicio en Railway (o un proyecto nuevo)

Ve a **railway.app** → crea un proyecto nuevo o usa el existente, pero **crea un servicio nuevo dentro** (no uses el de producción).

**Opción A:** Un servicio "crm-viamonte-demo" en el mismo proyecto de producción  
**Opción B:** Un proyecto separado (recomendado para evitar accidentes)

**Recomendación:** Opción B, proyecto separado en Railway, apuntando a tu repo del demo.

### 3. Adjuntar un Volume al servicio demo

1. En el dashboard de Railway, ve al servicio demo.
2. **Settings** → **Volume** → **Create volume**.
3. Dale un nombre (ej. `viamonte-demo-data`) y dale 1 GB (o más).
4. Monta el volumen en la ruta `/data` (o la que prefieras, por defecto será `/data`).

Al hacer esto, `database.py` (que usa `RAILWAY_VOLUME_MOUNT_PATH`) creará automáticamente `viamonte.db` en ese volumen, separado del de producción.

### 4. Configurar variables de entorno en el servicio demo

En **Settings** → **Variables** del servicio demo en Railway, define **SOLO**:

```
CLAVE_INICIAL_DEMO=<una-contraseña-a-tu-elección>
```

**NO copies** `CLAVE_INICIAL_FACUNDO`, `CLAVE_INICIAL_MARCOS`, `CLAVE_INICIAL_LUCIO` ni `PROMOVER_A_ADMIN` — esas son de producción.

- `SECRET_KEY` es opcional: si no lo defines, se genera automáticamente la primera vez y se persiste en el volumen.
- El hostname/dominio será asignado automáticamente por Railway (ej. `crm-viamonte-demo.up.railway.app`).

### 5. Deployar el servicio

1. Conecta el servicio a tu repo del demo en GitHub.
2. Railway detectará los cambios y hará el primer deploy automáticamente.
3. En el log de Railway, deberías ver: `✅ Usuario demo creado` (cuando `CLAVE_INICIAL_DEMO` existe).

### 6. Poblar la base con datos de ejemplo

Una vez que el servicio esté corriendo, ejecuta el script que prepara los datos:

#### Opción A: Vía consola one-off de Railway

```bash
railway run python poblar_base_ejemplo.py
```

(Reemplaza con el comando exacto que Railway te muestre en la consola.)

#### Opción B: En tu máquina, apuntando al servicio demo

Si tienes acceso SSH/CLI a Railway:

```bash
# Dentro de la carpeta del repo demo local
export RAILWAY_VOLUME_MOUNT_PATH=/data  # O la ruta que hayas asignado
python poblar_base_ejemplo.py
```

### 7. Verificar que funciona

1. Abre `https://crm-viamonte-demo.up.railway.app` (o el dominio que Railway haya asignado).
2. Ingresa con: **Usuario:** `demo` | **Contraseña:** `<CLAVE_INICIAL_DEMO>`
3. Deberías ver el Kanban con los 3 trabajos de ejemplo en estado "Aprobado".
4. Verifica que **NO hay clientes reales** (Juan García y María López son ficticios, sólo del demo).

---

## Resetear datos antes de una nueva demo/grabación

El script `poblar_base_ejemplo.py` borra TODA la base y la recreza desde cero con datos de ejemplo.

```bash
# En la consola Railway del servicio demo
railway run python poblar_base_ejemplo.py
```

Esto:
- Borra todas las tablas (menos los usuarios).
- Recrea los 2 clientes de ejemplo, 3 trabajos, stock, gastos, cheques y movimientos.
- El usuario `demo` sigue existiendo (y su contraseña no cambia).

**Salvaguarda:** Si por error corres esto contra la base de producción (porque estés en la carpeta equivocada o `RAILWAY_VOLUME_MOUNT_PATH` apunte mal), el script detecta que ya existen `facundo`/`marcos`/`lucio` y aborta sin tocar nada.

---

## URLs

- **Producción:** `https://<dominio-producción>` (el que usa Facundo todos los días)
- **Demo:** `https://crm-viamonte-demo.up.railway.app` (o el que asigne Railway)

Son completamente independientes. El demo nunca puede afectar producción.

---

## Troubleshooting

### "Usuario demo no se crea"
- Verifica que `CLAVE_INICIAL_DEMO` esté definida en Railway (Settings → Variables).
- Revisa el log de deploy: debería decir `✅ Usuario demo creado`.

### "poblar_base_ejemplo.py aborta sin hacer nada"
- El script detectó que la base tiene usuarios reales (`facundo`/`marcos`/`lucio`).
- Verifica que estés en el servicio demo, no en producción.
- Si estás seguro de que es el demo, revisa el `RAILWAY_VOLUME_MOUNT_PATH` en el log.

### "Los datos de ejemplo no se ven"
- Ejecutaste `poblar_base_ejemplo.py` pero aún ves la base vacía o datos viejos.
- Intenta ejecutar el script nuevamente: es idempotente (si `USUARIOS_INICIALES` fue sin el `demo`, correr el arranque de nuevo lo va a crear).
- Limpia el cache del navegador (Ctrl+Shift+Supr).

### "El demo accedió a datos reales de clientes"
- **Contacto inmediato.** Esto significa que apunta a la base de producción.
- Verifica el `RAILWAY_VOLUME_MOUNT_PATH` en el servicio demo: debe apuntar a su propio volumen, no al de producción.

---

## Mantenimiento

- **Cada N semanas:** resetea el demo antes de una grabación (`python poblar_base_ejemplo.py`).
- **Si cambias el código:** los cambios se despliegan automáticamente a ambos servicios (producción y demo). El demo sigue aislado por BD, no por código.
- **Si necesitas cambiar la contraseña del demo:** edita `CLAVE_INICIAL_DEMO` en Railway, reinicia el servicio y corre `python arranque.py` en la consola. O simplemente elimina el usuario `demo` de la BD y el próximo arranque lo recrea.

---

## Resumen de la arquitectura

```
┌─────────────────────┐                ┌──────────────────────┐
│   Producción        │                │   Demo               │
├─────────────────────┤                ├──────────────────────┤
│ Repo: main          │                │ Repo: tu fork        │
│ Servicio: prod      │                │ Servicio: demo       │
│ Volumen: prod-data  │                │ Volumen: demo-data   │
│ BD: viamonte.db     │                │ BD: viamonte.db      │
│ (datos reales)      │                │ (datos ejemplo)      │
│                     │                │                      │
│ Usuarios:           │                │ Usuarios:            │
│ - facundo (admin)   │                │ - demo (admin)       │
│ - marcos (encargado)│                │                      │
│ - lucio (mostrador) │                │ Datos:               │
│                     │                │ - 2 clientes ficticios
│ URL:                │                │ - 3 trabajos         │
│ crm-viamonte.up.... │                │ - Stock de ejemplo   │
└─────────────────────┘                │                      │
   (datos reales)                       │ URL:                 │
                                        │ crm-viamonte-demo... │
                                        └──────────────────────┘
                                            (para demos)
```

Cero posibilidad de que el demo toque producción: bases de datos físicamente separadas en volúmenes distintos.
