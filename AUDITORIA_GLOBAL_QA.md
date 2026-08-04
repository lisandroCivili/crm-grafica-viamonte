# Auditoría global de QA y Seguridad — CRM Gráfica Viamonte

> **Rol:** Senior QA Automation Engineer / Arquitecto de Seguridad
> **Fecha:** 2 de agosto de 2026
> **Commit base:** `e08db7c` (checkpoint previo, sobre `7b7dadd`)
> **Alcance:** backend (FastAPI/SQLAlchemy), frontend (HTML/CSS/JS), base de datos,
> migraciones, generación de PDFs, empaquetado y configuración de despliegue.
> **Naturaleza:** auditoría de **sólo lectura**. No se modificó una sola línea del
> código del proyecto. Todas las pruebas se ejecutaron contra bases SQLite
> temporales y descartables.

---

## Cómo leer este documento

Cada hallazgo lleva un identificador estable (`C-01`, `A-03`…), el archivo y la
línea donde vive, el impacto concreto sobre el negocio y —para todo lo CRÍTICO y
ALTO— el extracto del código actual junto a la corrección propuesta.

| Severidad | Criterio |
|---|---|
| **CRÍTICO** | Corrompe datos económicos, deja el sistema inoperable o permite acceso indebido. Se arregla antes del próximo deploy. |
| **ALTO** | Rompe un flujo real del taller, expone información o produce un 500 en un camino que un operador puede recorrer sin querer. |
| **MEDIO** | Falla en condiciones poco frecuentes o degrada el sistema a medida que crece. |
| **BAJO** | Molestia, inconsistencia o riesgo teórico. |
| **MEJORA** | No es un defecto: es una oportunidad de dejar el proyecto más claro o más mantenible. |

**Método.** No hay hallazgo escrito de memoria: cada uno se leyó en el código y,
cuando el comportamiento no era evidente por inspección, se **reprodujo
empíricamente** levantando la aplicación real (`main.app`) contra una base
temporal y disparando el pedido. Los resultados de esas pruebas se citan
textualmente. La suite existente (`pytest`) también se ejecutó completa.

---

## Resumen ejecutivo

**Impresión general.** El proyecto está muy por encima de la media para su
tamaño. El dinero se maneja en `Decimal` con un `TypeDecorator` propio (`money.py`),
la matemática financiera está centralizada en un único módulo (`calculos.py`), hay
una tabla de auditoría transversal, permisos por rol declarados a nivel de router,
415 tests, y —lo más valioso— los comentarios explican *por qué* está hecho así
cada cosa, no *qué* hace. Varias de las trampas clásicas ya están resueltas a
conciencia: el PRAGMA de foreign keys, el guard de idempotencia al imprimir la
orden, la re-imputación de saldo a favor con `UPDATE` condicional.

Los problemas encontrados se concentran en cuatro frentes bien delimitados:

1. **Numeración de comprobantes.** Los tres generadores de número correlativo
   (orden, presupuesto, remito) leen el máximo y suman uno, sin unicidad en la
   base ni tolerancia a un valor con formato inesperado. Uno de ellos deja el
   módulo de remitos permanentemente inoperable ante un dato que **el propio
   arranque del sistema puede generar**.
2. **Validación de entrada en el borde.** Varios `POST`/`PUT` construyen el modelo
   con `Model(**schema.model_dump())` sin verificar que las claves foráneas
   existan ni que los valores tengan sentido de negocio. El resultado es un 500
   con traza en vez de un 400 explicativo, y —en algunos casos— datos inválidos
   persistidos.
3. **Concurrencia.** El patrón "leer, decidir, escribir" está protegido en dos
   endpoints (imprimir orden, aplicar saldo a favor) pero falta en el resto. Se
   reprodujeron **cinco** carreras distintas: trabajos duplicados al convertir un
   presupuesto, números de orden repetidos, sobre-entrega de mercadería, clientes
   duplicados e historial de stock descuadrado.
4. **Escapado en el frontend.** El proyecto tiene su función `esc()` y la usa en
   la mayoría de los render, pero quedaron 25 interpolaciones de texto libre sin
   pasar por ella. Con el token de admin en `localStorage`, eso habilita una
   escalada de privilegios del puesto más bajo al de dueño.

| Severidad | Cantidad |
|---|---|
| CRÍTICO | 5 |
| ALTO | 20 |
| MEDIO | 26 |
| BAJO | 17 |
| MEJORA | 11 |
| **Total** | **79** |

### Los cinco CRÍTICOS, en una línea cada uno

| ID | Título | Dónde | ¿Reproducido? |
|---|---|---|---|
| **C-01** | Convertir un presupuesto dos veces crea trabajos duplicados y factura de más | `routers/presupuestos.py:340` | Sí — 4 pedidos → 3 trabajos |
| **C-02** | Un remito legado con sufijo `-DUP-` deja el módulo de entregas muerto (409 permanente) | `routers/entregas.py:41` | Sí — 409 irrecuperable |
| **C-03** | Cinco librerías del frontend desde CDNs externos, sin SRI, dos sin versión fija | `frontend/index.html:15-20` | Sí — por inspección |
| **C-04** | Órdenes de producción con número duplicado bajo uso normal | `routers/trabajos.py:58` | Sí — 10 órdenes, 2 números |
| **C-05** | XSS almacenado en 25 puntos, con escalada de `mostrador` a `admin` | `frontend/js/*.js` | Sí — 25 puntos localizados |

> **Lo primero de todo**, antes incluso de leer el resto: correr esta consulta contra
> la base de producción. Si devuelve alguna fila, el módulo de remitos **ya está
> caído** en esa instalación (ver C-02).
>
> ```sql
> SELECT numero_remito FROM entregas
> WHERE numero_remito NOT GLOB 'RE-[0-9][0-9][0-9][0-9][0-9][0-9]';
> ```

---
---

# FASE 1 — Configuración, arranque y despliegue

Archivos revisados: `main.py`, `database.py`, `rutas.py`, `arranque.py`,
`Procfile`, `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`,
`GraficaViamonte.spec`.

## Lo que está bien

- **`.secret_key`, `*.db` y `.env` no están versionados.** Se verificó contra
  `git ls-files`: de los 119 archivos trackeados, ninguno es una base ni un
  secreto. El comentario del `.gitignore` explica exactamente por qué, que es la
  forma de que nadie lo revierta por descuido.
- **`rutas.py`** resuelve los tres escenarios (servidor con volumen, PyInstaller,
  desarrollo) en un solo lugar y separa correctamente la carpeta escribible de la
  de sólo lectura.
- **El PRAGMA de foreign keys** está activo (`database.py:20-24`) y replicado en
  el `conftest.py` de los tests, con el comentario explicando por qué hace falta
  replicarlo. Es un detalle que casi todos los proyectos SQLite pasan por alto.

## A-01 — ALTO · `requirements.txt` no coincide con lo que realmente corre

**Dónde:** `requirements.txt` vs. el entorno instalado.

Lo declarado y lo instalado son versiones distintas en las cuatro dependencias
centrales:

| Paquete | `requirements.txt` | Instalado (donde corren los tests) |
|---|---|---|
| fastapi | 0.135.3 | **0.115.0** |
| SQLAlchemy | 2.0.50 | **2.0.35** |
| pydantic | 2.12.4 | **2.9.2** |

**Impacto.** Los 415 tests validan un comportamiento que **no es el que se va a
desplegar**. Entre 2.9.2 y 2.12.4 de Pydantic, y entre 2.0.35 y 2.0.50 de
SQLAlchemy, hay cambios en coerción de tipos y en el manejo de sesiones. Un
`pytest` verde acá no dice nada sobre producción. Además no hay lockfile: dos
instalaciones en fechas distintas pueden traer resoluciones distintas.

**Solución propuesta.**

```bash
# 1. Alinear el entorno local con lo declarado, y volver a correr la suite:
pip install -r requirements.txt
pytest

# 2. Congelar el árbol completo (no sólo los directos) en un archivo aparte,
#    que es el que usa el deploy:
pip freeze > requirements.lock.txt
```

```diff
  # Procfile
- web: gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app
+ # --preload evita que cada worker corra create_all/migraciones en paralelo.
+ web: gunicorn -w 1 -k uvicorn.workers.UvicornWorker --preload main:app
```

---

## A-02 — ALTO · El arranque fuerza a un usuario a `admin` en cada reinicio

**Dónde:** `arranque.py:68-72`.

```python
marcos_db = db.query(models.Usuario).filter(models.Usuario.nombre == "marcos").first()
if marcos_db and marcos_db.rol != ROL_ADMIN:
    marcos_db.rol = ROL_ADMIN
    db.commit()
    print("✅ Permisos de Marcos actualizados a ADMIN")
```

**Impacto.** Es una escalada de privilegios permanente y silenciosa, escrita en
el código. Contradice de frente la decisión de diseño que el propio proyecto
documenta en `seguridad.py:26-33` y en `models.Usuario` ("los roles son PUESTOS,
no personas"). Consecuencias concretas:

1. Si el dueño baja a `marcos` a `encargado` desde la pantalla de usuarios, el
   próximo reinicio se lo devuelve a `admin`. No hay forma de degradarlo sin
   tocar el código.
2. `admin` ve la facturación histórica completa (`GET /api/clientes/saldos`),
   descarga la base entera (`GET /api/backup`) y puede borrar movimientos.
3. **Rompe la suite:** es el único test en rojo de los 415
   (`test_crea_los_tres_puestos_en_una_base_vacia`). Un proyecto con la suite en
   rojo pierde la señal: el próximo fallo real se confunde con éste.

Entiendo que fue un parche deliberado y urgente. El problema no es la decisión de
negocio (que a Marcos le corresponda ser admin es legítimo) sino **el mecanismo**:
está escrito para una persona en vez de para un puesto, y no se puede deshacer
desde la aplicación.

**Solución propuesta.** Que el rol se defina por configuración, una sola vez, y
que sea revocable desde el sistema:

```python
# arranque.py — reemplaza el bloque de las líneas 68-72

# Los usuarios y su rol inicial salen de USUARIOS_INICIALES; el alta ya es
# idempotente. Para promover a alguien que YA existe, se define esta variable de
# entorno una vez, se reinicia, y después se la borra. Así la promoción queda
# registrada y, sobre todo, se puede revertir desde la pantalla de usuarios sin
# volver a tocar el código.
def _promover_por_entorno(db: Session) -> None:
    """Promueve a admin a los usuarios listados en PROMOVER_A_ADMIN.

    Formato: "marcos" o "marcos,lucio". Pensada para correrse una vez y
    desactivarse; mientras siga definida, una baja de rol se revierte en el
    próximo arranque (mismo criterio que las CLAVE_INICIAL_*).
    """
    nombres = [n.strip().lower() for n in os.getenv("PROMOVER_A_ADMIN", "").split(",") if n.strip()]
    if not nombres:
        return

    for usuario in db.query(models.Usuario).filter(models.Usuario.nombre.in_(nombres)).all():
        if usuario.rol != ROL_ADMIN:
            usuario.rol = ROL_ADMIN
            print(f"Rol de {usuario.nombre} promovido a admin por PROMOVER_A_ADMIN.")
    db.commit()
```

Y en `aplicar_migraciones_pendientes` / `_sembrar`, llamar a `_promover_por_entorno(db)`
en lugar del bloque hardcodeado. Con eso el test vuelve a verde sin tocarlo.

---

## M-01 — MEDIO · CORS acepta el origen `null`

**Dónde:** `main.py:42-62`.

```python
ORIGENES_PERMITIDOS = [
    ...
    "null",                    # index.html abierto directamente como archivo (file://)
]
```

**Impacto.** `Origin: null` no lo manda sólo un `file://`: también lo manda
**cualquier iframe con `sandbox`**, que un sitio hostil puede incrustar en su
propia página. Como no está `allow_credentials=True` y el token viaja en el header
`Authorization` (no en cookie), un tercero no puede robar sesión con esto; el
riesgo real es acotado. Pero la entrada existe para un modo de uso (abrir
`index.html` con doble clic) que **ya no es el que se usa**: desde que el backend
sirve el frontend (`main.py:147`), el navegador siempre está en el mismo origen.

**Solución.** Sacar `"null"` de la lista y, ya que la API no usa cookies, dejar
explícito que no se admiten credenciales:

```diff
  ORIGENES_PERMITIDOS = [
      "http://localhost:5500",   # Live Server de VS Code
      "http://127.0.0.1:5500",   # Live Server (variante 127.0.0.1)
      "http://localhost:8000",   # Backend local
      "http://127.0.0.1:8000",   # Backend local (127.0.0.1)
-     "null",                    # index.html abierto directamente como archivo (file://)
  ]
```

---

## M-02 — MEDIO · SQLite sin WAL ni `timeout`: "database is locked" bajo concurrencia

**Dónde:** `database.py:14`.

```python
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

**Impacto.** Los endpoints son funciones `def` (no `async`), así que FastAPI los
corre en un pool de hilos: hay escrituras realmente simultáneas. SQLite en modo
`journal` por defecto toma un lock exclusivo de base entera en cada escritura, y
sin `timeout` explícito el driver espera 5 segundos y tira
`OperationalError: database is locked`. Con tres personas usando el sistema a la
vez —que es exactamente el escenario que motivó la tabla de auditoría, según
`models.Auditoria`— esto aparece como un 500 esporádico e irreproducible.

**Solución.** WAL (permite lectores concurrentes con un escritor) y un timeout
generoso:

```python
engine = create_engine(
    DATABASE_URL,
    # timeout: cuántos segundos espera una escritura a que se libere el lock de
    # SQLite antes de tirar "database is locked". El default (5s) es corto para
    # tres puestos escribiendo a la vez.
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _configurar_conexion(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # SQLite tiene las FOREIGN KEYS desactivadas por defecto: sin este PRAGMA,
    # los ForeignKey de models.py son decorativos.
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL: los lectores dejan de bloquearse contra el escritor. Sin esto,
    # abrir el Kanban mientras alguien guarda un pago puede dar 500.
    cursor.execute("PRAGMA journal_mode=WAL")
    # NORMAL con WAL es seguro ante caída de la app (no ante corte de luz) y
    # evita un fsync por transacción, que es lo que hace lento el guardado.
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```

---

## B-01 — BAJO · `/api/backup` sirve un archivo SQLite que puede estar a medio escribir

**Dónde:** `main.py:87-104`.

`FileResponse` lee `viamonte.db` del disco tal como está. Si alguien guarda un
pago mientras se descarga el respaldo, el `.db` copiado puede quedar inconsistente
(y con WAL activado —ver M-02— quedaría directamente incompleto, porque los
cambios recientes viven en `viamonte.db-wal`, que no se copia).

**Solución.** Usar la API de backup online de SQLite, que produce una copia
consistente sin bloquear:

```python
@app.get("/api/backup", dependencies=[Depends(solo_admin)])
def descargar_respaldo():
    import sqlite3, tempfile
    from fastapi.background import BackgroundTasks

    db_path = os.path.join(BASE_DIR, "viamonte.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")

    # sqlite3.Connection.backup() copia la base con una transacción consistente:
    # incluye lo que esté en el WAL y no se corta si alguien escribe en el medio.
    destino = os.path.join(tempfile.gettempdir(), f"respaldo_{os.getpid()}.db")
    origen = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    origen.close(); copia.close()

    fecha_str = datetime.now().strftime("%d-%m-%Y")
    return FileResponse(
        path=destino,
        filename=f"respaldo_viamonte_{fecha_str}.db",
        media_type="application/octet-stream",
        background=BackgroundTask(os.remove, destino),  # from starlette.background
    )
```

---

## B-02 — BAJO · Cinco archivos `.db` de respaldo en la raíz del proyecto

`viamonte_backup_20260728_124522.db`, `..._155756.db`, `..._20260729_101710.db`,
`..._20260730_122449.db`, `viamonte_backup_30_7.db`, más dos en `backups/`.

Están correctamente ignorados por git, así que **no hay filtración**. El problema
es operativo: son copias completas de la base (clientes, precios, saldos, sueldos)
acumulándose sin política de retención en la carpeta de trabajo. Conviene moverlas
todas a `backups/` y borrar las que ya no sirvan.

---

## MJ-01 — MEJORA · El `.spec` de PyInstaller está en `.gitignore` con una excepción frágil

**Dónde:** `.gitignore:32-36`.

```
*.spec
!GraficaViamonte.spec
```

Funciona, pero un `.spec` nuevo (por ejemplo para una segunda variante del
empaquetado) se ignoraría en silencio. Es más claro invertir la regla: no ignorar
`*.spec` en absoluto, ya que el proyecto genera uno solo y a mano.

---
---

# FASE 2 — Autenticación, autorización y superficie de ataque

Archivos revisados: `seguridad.py`, `routers/auth.py`, `schemas/auth.py`,
`routers/_comun.py`, y las `dependencies` de los 13 routers.

## Lo que está bien

Esta capa es la mejor resuelta del proyecto y conviene decirlo con nombre propio:

- **`jwt.decode(..., algorithms=[ALGORITMO])`** con la lista explícita: cierra el
  ataque de `alg: none` y de confusión de algoritmos, que es el error nº1 en
  implementaciones de JWT.
- **El usuario se relee de la base en cada request** (`seguridad.py:137-139`) y se
  verifica `activo`: una baja tiene efecto inmediato, no en 12 horas.
- **`bcrypt` con salt por contraseña** y `verificar_password` tolerante a hashes
  corruptos, devolviendo `False` en vez de un 500.
- **`HTTPBearer(auto_error=False)`** para que la falta de header dé 401 y no 403,
  con el comentario explicando por qué importa la diferencia para el frontend.
- **`LoginRequest.password` acotado a 72 bytes**, que es el límite real de bcrypt.
  Muy pocos proyectos saben esto.
- **Los permisos se declaran a nivel de router**, no endpoint por endpoint, y
  `_trabajo_visible()` vacía los campos de plata en la **respuesta** en lugar de
  confiar en que el frontend no los pinte. El comentario de `routers/trabajos.py:47-50`
  explica exactamente por qué eso no alcanza.

## A-03 — ALTO · El login no tiene límite de intentos ni bloqueo

**Dónde:** `routers/auth.py:32-56`.

**Reproducido.** Se dispararon 40 intentos consecutivos con contraseña incorrecta
contra un usuario real:

```
40 intentos seguidos -> códigos {401}; filas de auditoría escritas: 42
```

Ni un solo bloqueo, ni una demora incremental, ni un 429. **Doble impacto:**

1. **Fuerza bruta.** Con el sistema publicado en Railway, cualquiera con la URL
   puede probar contraseñas indefinidamente. La única defensa es la fortaleza de
   la contraseña que eligió el operador — y `LoginRequest` sólo exige 4 caracteres
   (`min_length=4`), así que "1234" es una contraseña válida del sistema.
2. **Crecimiento descontrolado de la base.** Cada intento fallido escribe una fila
   en `auditoria` **con su propio commit** (línea 55, y el comentario explica que
   es deliberado). Un atacante infla la tabla sin límite: en la práctica, un
   agotamiento de disco del volumen de Railway, que se lleva puesta la base entera.

**Solución propuesta.** Un contador en memoria del proceso, que es suficiente
para un despliegue de un solo worker (`Procfile` usa `-w 1`) y no necesita
dependencias nuevas:

```python
# routers/auth.py

import time
from collections import defaultdict

# Cuántos intentos fallidos seguidos se toleran por nombre de usuario antes de
# frenar, y por cuánto. En memoria del proceso y no en la base: un reinicio los
# limpia, que es aceptable, y así un ataque no escribe una fila por intento.
# Va por nombre y no por IP porque detrás de un router del taller todos comparten IP.
MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 300  # 5 minutos

_intentos_fallidos: dict[str, list[float]] = defaultdict(list)


def _esta_bloqueado(nombre: str) -> int:
    """Segundos que faltan para poder reintentar, o 0 si puede intentar ahora."""
    ahora = time.monotonic()
    recientes = [t for t in _intentos_fallidos[nombre] if ahora - t < BLOQUEO_SEGUNDOS]
    _intentos_fallidos[nombre] = recientes
    if len(recientes) < MAX_INTENTOS:
        return 0
    return int(BLOQUEO_SEGUNDOS - (ahora - recientes[0])) + 1


@router.post("/login", response_model=schemas.TokenResponse)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    nombre = data.usuario.strip().lower()

    # Se corta ANTES de tocar la base: un ataque no escribe una fila por intento
    # ni consume el bcrypt (que es caro a propósito).
    espera = _esta_bloqueado(nombre)
    if espera:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Probá de nuevo en {espera} segundos.",
            headers={"Retry-After": str(espera)},
        )

    usuario = db.query(models.Usuario).filter(models.Usuario.nombre == nombre).first()

    if (
        usuario is None
        or not usuario.activo
        or not verificar_password(data.password, usuario.password_hash)
    ):
        _intentos_fallidos[nombre].append(time.monotonic())
        asentar(db, None, models.ACCION_INGRESO_FALLIDO, ENTIDAD, None,
                f"intento con el nombre '{nombre[:LARGO_MAXIMO_NOMBRE]}'")
        db.commit()
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    _intentos_fallidos.pop(nombre, None)  # entró bien: se limpia el contador
    ...
```

Y en `schemas/auth.py`, subir el piso de la contraseña:

```diff
  class LoginRequest(BaseModel):
-     usuario: str
+     usuario: str = Field(min_length=1, max_length=50)
      # bcrypt ignora todo lo que pase de 72 bytes. Cortar acá evita la falsa
      # sensación de que una contraseña larguísima protege más de lo que protege.
-     password: str = Field(min_length=4, max_length=72)
+     password: str = Field(min_length=8, max_length=72)
```

---

## A-04 — ALTO · El tiempo de respuesta del login revela qué usuarios existen

**Dónde:** `routers/auth.py:40-44`.

**Reproducido.** Medición sobre la aplicación real:

```
usuario inexistente:      15.3 ms
usuario real, clave mala: 312.6 ms
ratio: 20.5x
```

**Impacto.** El código hace un esfuerzo explícito por **no** revelar qué nombres
existen: usa un solo mensaje para los tres casos, y el comentario de las líneas
37-39 explica que es a propósito. Pero el cortocircuito de Python (`usuario is None or ...`)
saltea `bcrypt` cuando el usuario no existe, y bcrypt es caro **a propósito**. La
diferencia de 20x es medible desde cualquier cliente y anula por completo esa
protección: un atacante enumera los tres nombres válidos en segundos y después
concentra la fuerza bruta (ver A-03) sólo en ellos.

**Solución.** Ejecutar siempre un `checkpw` — contra un hash señuelo cuando el
usuario no existe — para que las dos ramas cuesten lo mismo:

```python
# seguridad.py

# Hash de una contraseña que nadie usa. Existe para gastar el mismo tiempo de
# bcrypt cuando el usuario NO existe: sin esto, la respuesta vuelve 20 veces más
# rápido y eso solo ya delata qué nombres de usuario son reales, que es
# justamente lo que el mensaje único del login trata de esconder.
_HASH_SENUELO = hashear_password("contraseña que no le sirve a nadie")


def verificar_password_constante(password: str, hash_guardado: str | None) -> bool:
    """Como verificar_password, pero tarda lo mismo exista o no el usuario."""
    return verificar_password(password, hash_guardado or _HASH_SENUELO) and hash_guardado is not None
```

```diff
  # routers/auth.py
- from seguridad import crear_token, usuario_actual, verificar_password
+ from seguridad import crear_token, usuario_actual, verificar_password_constante

  ...
-     if (
-         usuario is None
-         or not usuario.activo
-         or not verificar_password(data.password, usuario.password_hash)
-     ):
+     # El checkpw se ejecuta SIEMPRE (contra un hash señuelo si el usuario no
+     # existe): si se saltea, la respuesta vuelve 20x más rápido y eso delata
+     # qué nombres son reales, anulando el mensaje único de abajo.
+     password_ok = verificar_password_constante(
+         data.password, usuario.password_hash if usuario else None
+     )
+     if usuario is None or not usuario.activo or not password_ok:
```

---

## A-05 — ALTO · No hay forma de revocar un token emitido

**Dónde:** `seguridad.py:94-103`, `frontend/js/app.js:103-109`.

`cerrarSesion()` borra el token del `localStorage` del navegador, pero el token
sigue siendo **criptográficamente válido durante 12 horas**. Si alguien lo copia
(de la consola del navegador, de una PC compartida del mostrador, de un log), lo
usa hasta que venza y no hay nada que hacer al respecto salvo dar de baja al
usuario entero.

Dar de baja al usuario **sí** funciona de inmediato (`seguridad.py:138`, muy bien
resuelto), pero es un martillo: deja a esa persona sin sistema.

**Solución propuesta.** Un contador de sesión por usuario. Barato, sin tablas
nuevas ni estado en memoria:

```python
# models.py — en la clase Usuario
    # Se incrementa al cerrar sesión o al cambiar la contraseña. Va dentro del
    # token; si al validarlo no coincide con el de la base, ese token quedó
    # viejo. Es lo que permite invalidar una sesión sin dar de baja a la persona
    # ni esperar las 12 horas de vencimiento.
    version_sesion = Column(Integer, nullable=False, default=0)
```

```python
# seguridad.py
def crear_token(usuario: models.Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario.id,
        "nombre": usuario.nombre,
        "rol": usuario.rol,
        "ver": usuario.version_sesion or 0,   # <-- nuevo
        "iat": ahora,
        "exp": ahora + timedelta(hours=HORAS_VALIDEZ_TOKEN),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITMO)


def usuario_actual(...) -> models.Usuario:
    ...
    usuario = db.query(models.Usuario).filter(models.Usuario.id == payload.get("sub")).first()
    if usuario is None or not usuario.activo:
        raise _credenciales_invalidas()
    # Un token emitido antes del último "cerrar sesión" ya no vale, aunque no
    # haya vencido todavía.
    if payload.get("ver", 0) != (usuario.version_sesion or 0):
        raise _credenciales_invalidas()
    return usuario
```

Y un `POST /api/auth/logout` que haga `usuario.version_sesion += 1`.

---

## M-03 — MEDIO · El token vive en `localStorage` NO APLICAR

**Dónde:** `frontend/js/core.js:119-124`.

`localStorage` es legible por cualquier JavaScript del origen. Hoy no hay un XSS
explotable identificado (el escapado con `esc()` es consistente — ver Fase 7),
pero el token **es** el activo más valioso del sistema y las librerías del
frontend vienen de CDNs externos sin verificación de integridad (**C-03**). Si
alguno de esos CDNs se compromete, el atacante ejecuta
`localStorage.getItem('viamonte_token')` y se lleva una sesión de admin.

La alternativa correcta —cookie `HttpOnly; Secure; SameSite=Strict`— es un cambio
de arquitectura considerable (obliga a manejar CSRF). Dado el perfil de la
aplicación, **la mitigación costo-efectiva es cerrar C-03**: con SRI, el vector
principal desaparece.

---

## M-04 — MEDIO · El JWT no valida audiencia, emisor ni exige `exp` NO APLICAR

**Dónde:** `seguridad.py:133`.

```python
payload = jwt.decode(credenciales.credentials, SECRET_KEY, algorithms=[ALGORITMO])
```

PyJWT valida `exp` **si el claim está presente**, pero acepta sin chistar un token
que no lo traiga. Fabricar uno así exige conocer `SECRET_KEY`, así que hoy no es
explotable; es defensa en profundidad ante una fuga futura de la clave o un cambio
en cómo se emiten los tokens.

```diff
- payload = jwt.decode(credenciales.credentials, SECRET_KEY, algorithms=[ALGORITMO])
+ payload = jwt.decode(
+     credenciales.credentials,
+     SECRET_KEY,
+     algorithms=[ALGORITMO],
+     # Un token sin 'exp' hoy se aceptaría para siempre: PyJWT sólo valida el
+     # vencimiento si el claim viene. Exigirlo cierra esa puerta.
+     options={"require": ["exp", "sub"]},
+ )
```

---

## M-05 — MEDIO · `.secret_key` se escribe sin permisos restringidos NO APLICAR

**Dónde:** `seguridad.py:59-62`.

```python
clave = os.urandom(32).hex()
with open(ruta, "w") as f:
    f.write(clave)
```

El archivo queda con los permisos por defecto (en la PC del taller, legible por
cualquier usuario de esa máquina). Quien lo lea se fabrica tokens de admin.
La entropía (`os.urandom(32)`) es correcta; lo que falta es el candado del archivo:

```python
clave = os.urandom(32).hex()
# 0600: sólo el usuario que corre el sistema puede leerla. Quien lea este
# archivo se puede fabricar un token de admin, así que no alcanza con que no
# esté versionada. (En Windows el modo es orientativo; en Linux es efectivo.)
descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(descriptor, "w") as f:
    f.write(clave)
```

---

## M-06 — MEDIO · Sin cabeceras de seguridad HTTP

No hay `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options` ni
`Referrer-Policy`. Como el backend sirve el frontend (`main.py:147`), agregarlas es
un middleware de quince líneas y **es la mitigación estructural de C-03**:

```python
# main.py, después del CORSMiddleware

# El backend sirve también el frontend, así que estas cabeceras protegen la
# pantalla y no sólo la API. La CSP es la red de contención de un XSS: aunque
# alguna vez se cuele HTML sin escapar, el navegador no ejecuta script inline
# ni carga nada de un dominio que no esté acá.
@app.middleware("http")
async def cabeceras_de_seguridad(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    respuesta.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # Los CDN de Chart.js, SweetAlert2, jsPDF, html2pdf y marked.
        "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        # 'unsafe-inline' en estilos: index.html y los render usan style="...".
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    return respuesta
```

> Nota: la CSP de arriba todavía habilita los dos CDN porque el frontend depende
> de ellos. Lo ideal es servir esas librerías desde `frontend/vendor/` (ver C-03)
> y dejar `script-src 'self'` a secas.

---

## B-03 — BAJO · La documentación interactiva queda pública

`/docs`, `/redoc` y `/openapi.json` están habilitados (default de FastAPI) y **sin
autenticación**: exponen el mapa completo de la API, con cada schema, cada campo y
cada endpoint. No revela datos, pero le entrega el índice a cualquiera que
encuentre la URL de Railway.

```python
app = FastAPI(
    title="Gráfica Viamonte — API Local",
    description="Backend modularizado para la gestión interna del taller",
    version="2.0",
    # En el servidor la doc interactiva no la usa nadie y le entrega a cualquiera
    # el mapa completo de la API. En la compu del taller se deja, que es donde
    # sirve para desarrollar.
    docs_url=None if os.getenv("RAILWAY_PUBLIC_DOMAIN") else "/docs",
    redoc_url=None,
    openapi_url=None if os.getenv("RAILWAY_PUBLIC_DOMAIN") else "/openapi.json",
)
```

---

## B-04 — BAJO · `mostrador` y `encargado` pueden imprimir la orden de producción

**Dónde:** `routers/trabajos.py:741` (sin `dependencies` extra).

Se verificó el contenido del PDF: `pdf/orden.py` **no imprime precio ni costo**
(sólo cliente, descripción, papel, tintas, terminación). Así que **no hay fuga de
información** — está bien resuelto.

Lo que sí tiene efecto lateral es que ese endpoint **descuenta stock y consume un
número de orden correlativo**. Que cualquier puesto pueda hacerlo es coherente con
el flujo del taller (el operario imprime su boleta), pero conviene tenerlo
presente: es el endpoint con más efectos colaterales del sistema y el de permiso
más amplio.

---

## MJ-02 — MEJORA · El intento de ingreso fallido guarda el nombre tipeado

**Dónde:** `routers/auth.py:53-54`. Ya está bien acotado a 50 caracteres y la
contraseña **nunca** se guarda (con un comentario que lo deja explícito, que es
justo lo que hay que hacer). Como refuerzo, vale recortar a caracteres imprimibles:
hoy un nombre con saltos de línea o caracteres de control se ve raro en la pantalla
de auditoría.

---
---

# FASE 3 — Capa de datos: sesiones, transacciones y rendimiento

Archivos revisados: `models.py`, `database.py`, `money.py`, `calculos.py`,
`auditoria.py`, y el uso de la sesión en los 13 routers.

## Lo que está bien

- **No hay una sola fuga de sesión ni de conexión.** Se revisó endpoint por
  endpoint: todos toman la sesión por `Depends(get_db)`, y `get_db` cierra en un
  `finally` (`database.py:31-36`). Los tres lugares que abren una sesión a mano
  (`arranque.py:31-35`, `:87-92`) también cierran en `finally`. **Cero fugas.**
- **No hay corrutinas sin `await`.** Todo el backend es síncrono (`def`, no
  `async def`): no existe la clase de bug que produce un `await` faltante. Es una
  decisión correcta para SQLAlchemy sincrónico — mezclar `async def` con
  `db.query()` bloquearía el event loop, que es un error mucho más caro.
- **`auditoria.cambios()`** lee el historial de atributos de SQLAlchemy en vez de
  copiar el objeto antes de tocarlo, y el docstring documenta la precondición
  crítica (llamarlo antes del `flush`, y que funciona porque las sesiones son
  `autoflush=False`). Es la pieza más elegante del proyecto.
- **`Money`/`Cantidad`** persisten `Decimal` como TEXT ya cuantizado: el error de
  float nunca llega al disco. Correcto.
- **`registrar_compra`** (`routers/stock.py:206-211`) envuelve el lote en
  try/rollback: un ítem que falla no deja media compra aplicada.

## A-06 — ALTO · N+1 confirmado en `GET /api/trabajos` (el Kanban)

**Dónde:** `routers/trabajos.py:377-420` + `schemas/trabajos.py:89`.

**Reproducido.** Con 28 trabajos, 20 de ellos con un renglón de remito:

```
HTTP 200; 28 trabajos devueltos; 50 SELECT ejecutados para una sola request
```

**La cadena.** `TrabajoResponse` declara `entregas: list[ItemEntregaResponse]`
(`schemas/trabajos.py:89`). Al serializar cada trabajo, SQLAlchemy carga la
relación `entregas` en forma diferida → **1 query por trabajo**. Y como
`ItemEntregaResponse` pide `numero_remito` y `fecha`, que en `models.ItemEntrega`
son *properties* que hacen `self.entrega.numero_remito` (`models.py:188-194`) →
**otra query por renglón de remito**. El costo total es `1 + N + M`.

El Kanban es la pantalla que el taller tiene abierta todo el día y se refresca en
cada cambio de estado. Con 300 trabajos históricos y sus remitos, esto son
centenares de consultas por carga — sobre SQLite, con el lock de escritura de
M-02 en el medio.

**Solución.** Cargar las dos relaciones de una, con `selectinload`:

```python
# routers/trabajos.py
from sqlalchemy.orm import Session, selectinload

@router.get("/", response_model=list[schemas.TrabajoResponse])
def listar_trabajos(
    estado: str | None = None,
    sin_presupuesto: bool = False,
    solo_tablero: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    # TrabajoResponse expone 'entregas', y cada ItemEntrega lee numero_remito y
    # fecha de SU cabecera (models.ItemEntrega): sin esto son 1 + N + M
    # consultas para armar el tablero. selectinload las trae en dos queries
    # fijas, sin importar cuántos trabajos haya.
    query = db.query(models.Trabajo).options(
        selectinload(models.Trabajo.entregas).selectinload(models.ItemEntrega.entrega)
    )
    if estado:
        query = query.filter(models.Trabajo.estado == estado)
    ...
```

Mismo tratamiento para `listar_presupuestos` y `dashboard`, que recorren
`p.items` en un bucle (`routers/presupuestos.py:155`, `routers/reportes.py:71-76`):
agregarles `.options(selectinload(models.Presupuesto.items))`.

---

## A-07 — ALTO · Faltan índices en todas las claves foráneas de consulta frecuente

**Dónde:** `models.py`.

Sólo `Entrega` e `ItemEntrega` declaran `index=True` en sus FKs. Las demás no:

| Columna | Consultada en |
|---|---|
| `trabajos.cliente_id` | ficha de cliente, saldos, borrado de cliente |
| `movimientos.cliente_id` | `GET /api/movimientos/{cliente_id}`, saldo |
| `movimientos.trabajo_id` | saldo por trabajo, borrado, saldo a favor |
| `notas.cliente_id` / `.trabajo_id` | ficha de cliente, borrado de trabajo |
| `gastos.trabajo_id` | dashboard, borrado de trabajo |
| `cheques.cliente_id` / `.trabajo_id` | cartera, saldo, borrado |
| `historial_stock.articulo_id` | historial de papel |
| `items_presupuesto.presupuesto_id` / `.trabajo_id` | conversión, dashboard, informe |

**Impacto.** Cada una de esas consultas es un *full table scan*. Hoy, con pocos
datos, no se nota. A dos años de operación —y con el dashboard cargando cinco
tablas enteras en cada request— se nota mucho, y la primera víctima es el lock de
escritura de SQLite.

**Solución.** Agregar `index=True` a las columnas de la tabla y crear los índices
en las bases existentes (`create_all` **no** los agrega a tablas ya creadas — mismo
motivo documentado en `migraciones/README.md`):

```python
# models.py — ejemplo sobre Trabajo y Movimiento; aplicar igual al resto
class Trabajo(Base):
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False, index=True)

class Movimiento(Base):
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False, index=True)
    trabajo_id = Column(String, ForeignKey("trabajos.id"), nullable=True, index=True)
```

```python
# arranque.py — nueva función, llamada desde aplicar_migraciones_pendientes()
def _crear_indices_faltantes(db: Session) -> None:
    """Crea los índices de las FK que se consultan todo el tiempo.

    create_all() sólo crea tablas nuevas: los índices agregados después a un
    modelo ya existente no aparecen solos (ver migraciones/README.md). Como
    CREATE INDEX IF NOT EXISTS es idempotente, esto se puede correr en cada
    arranque sin costo.
    """
    indices = [
        ("ix_trabajos_cliente_id", "trabajos", "cliente_id"),
        ("ix_movimientos_cliente_id", "movimientos", "cliente_id"),
        ("ix_movimientos_trabajo_id", "movimientos", "trabajo_id"),
        ("ix_notas_cliente_id", "notas", "cliente_id"),
        ("ix_notas_trabajo_id", "notas", "trabajo_id"),
        ("ix_gastos_trabajo_id", "gastos", "trabajo_id"),
        ("ix_cheques_cliente_id", "cheques", "cliente_id"),
        ("ix_cheques_trabajo_id", "cheques", "trabajo_id"),
        ("ix_historial_stock_articulo_id", "historial_stock", "articulo_id"),
        ("ix_items_presupuesto_presupuesto_id", "items_presupuesto", "presupuesto_id"),
        ("ix_items_presupuesto_trabajo_id", "items_presupuesto", "trabajo_id"),
    ]
    for nombre, tabla, columna in indices:
        db.execute(text(f"CREATE INDEX IF NOT EXISTS {nombre} ON {tabla} ({columna})"))
    db.commit()
```

---

## M-07 — MEDIO · El dashboard carga cinco tablas completas en memoria por request

**Dónde:** `routers/reportes.py:63-67`.

```python
trabajos = db.query(models.Trabajo).all()
presupuestos = db.query(models.Presupuesto).all()
movimientos = db.query(models.Movimiento).all()
cheques = db.query(models.Cheque).all()
gastos = db.query(models.Gasto).all()
```

El comentario dice "una consulta por tabla y cruce en memoria", y como decisión
**es la correcta hoy**: evita el N+1 y mantiene la matemática en `calculos.py`, que
es la fuente de verdad. El problema es que no tiene techo — ni siquiera para el
filtro `este_mes`, donde el 99% de lo traído se descarta en el predicado.

Mismo patrón, con el mismo diagnóstico, en `routers/clientes.py:85-98` (`saldos_clientes`)
y `routers/presupuestos.py:168-181` (`informe_trabajos`).

**Solución mínima, sin tocar `calculos.py`:** empujar el rango de fechas al SQL.

```python
def _rango_periodo(filtro: str) -> tuple[date | None, date | None]:
    """(desde, hasta) del período, o (None, None) para histórico.

    Complementa a _predicado_periodo: éste acota lo que se TRAE de la base y
    aquél sigue siendo el que decide, para que la regla del período viva en un
    solo lugar y las dos no se puedan despegar.
    """
    hoy = date.today()
    if filtro == "este_mes":
        return hoy.replace(day=1), hoy
    if filtro == "mes_pasado":
        primero_de_este = hoy.replace(day=1)
        ultimo_del_pasado = primero_de_este - timedelta(days=1)
        return ultimo_del_pasado.replace(day=1), ultimo_del_pasado
    if filtro == "este_anio":
        return date(hoy.year, 1, 1), hoy
    return None, None


@router.get("/dashboard", response_model=schemas.DashboardResponse)
def dashboard(filtro: str = "este_mes", db: Session = Depends(get_db)):
    en_periodo = _predicado_periodo(filtro)
    desde, hasta = _rango_periodo(filtro)

    q_movimientos = db.query(models.Movimiento)
    q_gastos = db.query(models.Gasto)
    if desde:
        q_movimientos = q_movimientos.filter(models.Movimiento.fecha >= datetime.combine(desde, time.min))
        q_gastos = q_gastos.filter(models.Gasto.fecha >= desde, models.Gasto.fecha <= hasta)
    movimientos = q_movimientos.all()
    gastos = q_gastos.all()
    # Trabajos, presupuestos y cheques siguen enteros: los cheques se realizan
    # por fecha_cobro/fecha_endoso (no por la de alta) y los presupuestos hacen
    # falta completos para el mapa de trabajo -> costo.
    presupuestos = db.query(models.Presupuesto).options(
        selectinload(models.Presupuesto.items)
    ).all()
    ...
```

---

## M-08 — MEDIO · `Cliente.dni_cuit` no es único en la base

**Dónde:** `models.py:55` vs. `routers/clientes.py:40-42`.

El router verifica el duplicado con un `SELECT` previo, pero la columna no tiene
`unique=True`. Entre la lectura y el `INSERT` hay una ventana: dos altas
simultáneas del mismo cliente (el doble clic clásico) pasan las dos. Con clientes
duplicados, la cuenta corriente se parte en dos fichas y ninguna muestra el saldo
real.

```diff
  class Cliente(Base):
-     dni_cuit = Column(String, index=True, nullable=False)
+     # unique: el router ya chequea el duplicado antes de insertar, pero leer y
+     # escribir son dos pasos y dos altas simultáneas pasan las dos. La base es
+     # el único árbitro que no se puede esquivar.
+     dni_cuit = Column(String, index=True, nullable=False, unique=True)
```

Con el índice único, el `except IntegrityError` del router traduce el choque a un
400 con el mismo texto que ya devuelve.

---

## M-09 — MEDIO · `Trabajo.numero_orden` y `Presupuesto.numero_secuencia` no son únicos

**Dónde:** `models.py:100` y `models.py:234`.

Ambos son números de comprobante correlativos, generados leyendo el máximo y
sumando uno. `Entrega.numero_remito` **sí** declara `unique=True` (y el comentario
del modelo explica por qué), pero sus dos hermanos no. Es la raíz de **A-08** y
**A-09** (Fase 5).

---

## M-10 — MEDIO · `HistorialStock` e `HistorialCheque` guardan UTC; el resto, hora local

**Dónde:** `models.py:333` y `:364` (UTC con tz) vs. `models.py:37-48` (`ahora_local`, naive).

Ya está documentado como decisión consciente en `ahora_local()`, con la advertencia
de que mezclarlos en Python lanza `TypeError`. Se confirma que hoy **ningún** código
los mezcla, así que no es un bug activo. Queda anotado porque es una mina esperando:
el día que un reporte cruce el historial de stock con la auditoría, revienta.

---

## M-11 — MEDIO · Sin paginación en los listados

`GET /api/clientes/`, `/api/trabajos/`, `/api/presupuestos/`, `/api/movimientos/`,
`/api/gastos/`, `/api/cheques/`, `/api/stock/` devuelven **todo**, siempre. El único
endpoint con techo es `/api/auditoria/` (`limite` con `le=LIMITE_MAXIMO`), que está
bien hecho y sirve de modelo para el resto.

El caso más caro es `GET /api/presupuestos/`: lo llama `armarMoldeBasePDF()` del
frontend **cada vez que se genera un PDF**, para quedarse con un solo presupuesto
(ver Fase 6, A-13).

---

## B-05 — BAJO · `Trabajo.entregas` sin cascade: el borrado depende del guard del router

**Dónde:** `models.py:136-139`.

`eliminar_trabajo` verifica que no haya `ItemEntrega` antes de borrar
(`routers/trabajos.py:603-605`), así que el camino de la API está cubierto. Pero si
alguna vez se borra un trabajo por otra vía (script, migración), la FK con el
PRAGMA activo tira `IntegrityError`. Es correcto que falle; sólo conviene saber que
la protección vive en el router y no en el modelo.

---

## B-06 — BAJO · `pesos()` trunca centavos en vez de redondear

**Dónde:** `pdf/comun.py:31-42`.

```python
centavos = int((abs(numero) - abs(entero)) * 100)
```

Con un valor de más de dos decimales, `int()` trunca: `1.999` se imprime `1,99`.
Hoy no ocurre, porque todo lo que llega sale de una columna `Money` ya cuantizada
a dos decimales. Queda como nota defensiva.

---

## MJ-03 — MEJORA · `db.refresh()` innecesario después de `commit()`

Patrón repetido en ~15 endpoints:

```python
db.commit()
db.refresh(nuevo)
return nuevo
```

Con el default `expire_on_commit=True`, acceder a cualquier atributo después del
commit ya dispara la recarga: el `refresh()` explícito emite un `SELECT` extra por
cada alta. No es un bug (los datos son correctos), es una consulta de más por
request. Se puede quitar sin cambiar comportamiento.

---
---

# FASE 4 — Routers: casos borde y validación de entrada

Archivos revisados: los 13 routers y los 14 módulos de `schemas/`.

Esta fase se hizo **disparando pedidos reales** contra la aplicación levantada
sobre una base temporal. Cada hallazgo cita la respuesta textual del servidor.

## Lo que está bien

- **`NaN` e `Infinity` están cubiertos.** Era la primera hipótesis: `Decimal("NaN")`
  reventaría en `Q2()`. Pydantic v2 lo rechaza antes, con un 422 limpio:
  `{"type":"finite_number","msg":"Input should be a finite number"}`. Confirmado en
  `precio_venta`, `monto` de gasto y `monto` de seña.
- **`obtener_o_404`** (`routers/_comun.py`) colapsa el patrón repetido y conserva
  textual el mensaje de cada router. Bien hecho.
- **`schemas/entregas.py`** valida lista vacía **y** trabajos repetidos en el mismo
  remito (`_al_menos_un_item_sin_repetidos`). Las dos trampas obvias, cerradas.
- **`_validar_detalles_costos`** (`schemas/comun.py:10-38`) es un modelo de cómo
  hacerlo: valida sin convertir, explica por qué en el docstring, y menciona el 500
  opaco que venía a reemplazar.
- **`_validar_transicion`** de cheques (`routers/cheques.py:39-65`) es una FSM real,
  con tabla de transiciones y motivo obligatorio para revertir un estado final.

## A-08 — ALTO · Cinco endpoints devuelven 500 en vez de 400 ante una FK inexistente

**Dónde:** `routers/movimientos.py:60`, `routers/notas.py:36`, `routers/gastos.py:60`,
`routers/cheques.py:90`, `routers/presupuestos.py:110`.

Todos usan `models.X(**schema.model_dump())` sin verificar que los `*_id` referenciados
existan. Con el PRAGMA de foreign keys activo (correctamente activo), la base
rechaza el `INSERT` y la excepción sube sin manejar.

**Reproducido — las cinco:**

```
POST /api/movimientos  cliente_id inexistente -> IntegrityError: FOREIGN KEY constraint failed
POST /api/notas        cliente_id inexistente -> IntegrityError: FOREIGN KEY constraint failed
POST /api/gastos       trabajo_id inexistente -> IntegrityError: FOREIGN KEY constraint failed
POST /api/cheques      cliente_id inexistente -> IntegrityError: FOREIGN KEY constraint failed
POST /api/presupuestos version_de inexistente -> IntegrityError: FOREIGN KEY constraint failed
```

**Impacto.** El operador ve "Error 500" sin explicación. El caso realista no es un
id inventado a mano: es el frontend mandando el id de un cliente que otro puesto
acaba de borrar, o un `trabajo_id` que quedó en un formulario abierto. `routers/trabajos.py`
y `routers/clientes.py` **sí** validan (`obtener_o_404`), así que la corrección es
aplicar el criterio que el proyecto ya usa:

```python
# routers/movimientos.py

@router.post("/", response_model=schemas.MovimientoResponse)
def crear_movimiento(
    mov: schemas.MovimientoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    if mov.tipo == "Pago" and mov.monto <= Decimal("0"):
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0.")

    if mov.tipo == "Pago" and metodo_es_cheque(mov.metodo):
        raise HTTPException(status_code=400, detail=ERROR_PAGO_CHEQUE)

    # Sin esto, un cliente o un trabajo borrado por otro puesto sale como un 500
    # opaco (la FK lo rechaza en la base) en vez de decir qué pasó. Mismo
    # criterio que ya usan routers/trabajos.py y routers/clientes.py.
    obtener_o_404(db, models.Cliente, mov.cliente_id, "El cliente indicado no existe.")
    if mov.trabajo_id:
        db_trabajo = obtener_o_404(db, models.Trabajo, mov.trabajo_id, "El trabajo indicado no existe.")
        # Ver A-09: un pago del cliente A imputado a un trabajo de B descuadra
        # las dos cuentas corrientes a la vez.
        if db_trabajo.cliente_id != mov.cliente_id:
            raise HTTPException(
                status_code=400,
                detail="El trabajo indicado es de otro cliente: el pago quedaría mal imputado.",
            )

    nuevo = models.Movimiento(**mov.model_dump())
    ...
```

Mismo bloque, adaptado, en `notas.py` (cliente + trabajo), `gastos.py` (trabajo),
`cheques.py` (cliente + trabajo) y `presupuestos.py` (`version_de`).

**Red de seguridad transversal**, para que un caso no previsto nunca más sea un 500:

```python
# main.py

from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse

# Última red: cualquier violación de integridad que se escape de las
# validaciones del router sale como un 409 legible en vez de un 500 con traza.
# No reemplaza a validar en el endpoint (ahí se puede decir QUÉ falta); es para
# que un caso no previsto no le muestre una pantalla rota al operador.
@app.exception_handler(IntegrityError)
async def error_de_integridad(request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "La operación choca con un dato relacionado "
                           "(algo fue borrado o modificado por otra persona). Refrescá y reintentá."},
    )
```

---

## A-09 — ALTO · Se puede imputar un pago a un trabajo de OTRO cliente

**Dónde:** `routers/movimientos.py:41-66`.

**Reproducido:**

```
POST /api/movimientos {cliente_id: A, trabajo_id: <trabajo del cliente B>, monto: 500, tipo: "Pago"}
-> HTTP 200 (aceptado)
```

**Impacto: descuadre doble y silencioso.** El `Movimiento` cuenta en el saldo de A
(`calcular_saldo_cliente` filtra por `cliente_id` — `routers/movimientos.py:72`), pero
cuenta como pago del trabajo de B (`calcular_saldo_trabajo` filtra por `trabajo_id`
— `routers/reportes.py:113`). Resultado: **A figura como que pagó de más y B como
que su trabajo está saldado, con plata que no entró por él.** El dashboard toma a
B como no-moroso y la ganancia de B se calcula sobre un cobro ajeno
(`ganancia_bruta_realizada`).

No hace falta mala intención: alcanza con elegir mal en un desplegable.

**Solución:** el bloque de validación de A-08, que ya incluye la comprobación
cruzada. El mismo control corresponde en `ChequeCreate` (cliente vs. trabajo) y en
`MovimientoUpdate`, que hoy permite mover `trabajo_id` a cualquier valor.

---

## A-10 — ALTO · El alta de trabajo acepta cualquier `estado`

**Dónde:** `schemas/trabajos.py:19` + `routers/trabajos.py:359-375`.

**Reproducido:**

```
POST /api/trabajos {estado: "banana", ...} -> HTTP 200, {"estado":"banana"}
```

**Impacto.** El `PUT` valida el estado contra `models.ESTADOS_TRABAJO`
(`_validar_cambio_estado`, línea 85), pero el `POST` no pasa por ahí: construye el
modelo directo. Un trabajo en un estado inexistente:

- no aparece en ninguna columna del Kanban (el frontend arma las columnas desde la
  lista de estados válidos) — el trabajo **desaparece de la vista del taller**;
- no cuenta en `ESTADOS_PENDIENTES` del dashboard ni como `Cancelado`, así que
  **sí suma a `total_facturado`** (`calcular_saldo_cliente` sólo excluye "Cancelado").

Es exactamente el bug que el proyecto ya arregló para cheques
(`_validar_estado_cheque`, `schemas/cheques.py:11-21`, con el comentario "antes
'estado' era un str libre: se podía dejar un cheque en 'banana'"). Falta aplicar el
mismo criterio a trabajos.

**Solución.** Un validador en el schema, igual que el de cheques:

```python
# schemas/trabajos.py

import models


def _validar_estado_trabajo(valor: Optional[str]) -> Optional[str]:
    """Acota el estado a ESTADOS_TRABAJO. Mismo criterio que _validar_estado_cheque.

    El PUT ya lo valida en el router (_validar_cambio_estado), pero el POST arma
    el modelo directo con model_dump() y no pasa por ahí: un trabajo en un estado
    inventado no entra en ninguna columna del Kanban y desaparece de la pantalla
    donde el taller lo sigue, mientras sigue sumando a la facturación.
    """
    if valor is not None and valor not in models.ESTADOS_TRABAJO:
        raise ValueError(
            f"Estado inválido: '{valor}'. Válidos: {', '.join(models.ESTADOS_TRABAJO)}."
        )
    return valor


class TrabajoBase(BaseModel):
    ...
    _estado_valido = field_validator("estado")(_validar_estado_trabajo)


class TrabajoUpdate(BaseModel):
    ...
    _estado_valido = field_validator("estado")(_validar_estado_trabajo)
```

---

## A-11 — ALTO · Se puede crear un cheque directamente en estado final

**Dónde:** `schemas/cheques.py:45` + `routers/cheques.py:84-102`.

**Reproducido:**

```
POST /api/cheques {estado: "Cobrado", monto: 50000, ...} -> HTTP 200, {"estado":"Cobrado"}
```

**Impacto.** `ChequeBase.estado` valida que el valor esté en `ESTADOS_CHEQUE`, pero
no que sea el **estado inicial**. Un cheque nacido en "Cobrado":

- saltea la FSM entera (`_TRANSICIONES`) y su historial (`HistorialCheque`) queda
  con un único asiento "creado", sin el `estado_anterior -> estado_nuevo` que la
  máquina de estados existe para registrar;
- **cuenta de inmediato como ingreso realizado** (`_fecha_realizacion_cheque` →
  `estado == "Cobrado"` → suma por `fecha_cobro`), sin haber pasado nunca por
  "Depositado";
- ya no se puede borrar (`eliminar_cheque` bloquea los cobrados/endosados), así que
  un error de carga sólo se revierte con un motivo asentado.

Contradice de frente `models.ESTADO_CHEQUE_INICIAL` ("estado con el que nace un
cheque; los demás se alcanzan por transición", `models.py:25-26`).

**Solución.** Fijar el estado inicial en el alta y dejar que la FSM haga su trabajo:

```python
# routers/cheques.py

@router.post("/", response_model=schemas.ChequeResponse)
def crear_cheque(
    cheque: schemas.ChequeCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    datos = cheque.model_dump()

    # Un cheque nace SIEMPRE en el estado inicial (models.ESTADO_CHEQUE_INICIAL):
    # los demás se alcanzan por transición, que es lo que registra el historial.
    # Aceptarlo del cliente permitía crear uno ya 'Cobrado', que cuenta como
    # ingreso sin haber pasado nunca por la máquina de estados.
    if datos.get("estado") not in (None, models.ESTADO_CHEQUE_INICIAL):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Un cheque se da de alta en '{models.ESTADO_CHEQUE_INICIAL}'. "
                f"Para llevarlo a '{datos['estado']}' cambiale el estado después del alta, "
                "así queda el movimiento en el historial."
            ),
        )
    datos["estado"] = models.ESTADO_CHEQUE_INICIAL
    datos["fecha_endoso"] = None   # sólo la escribe el paso a 'Endosado'

    nuevo_cheque = models.Cheque(**datos)
    ...
```

---

## A-12 — ALTO · `PATCH /api/stock` con `motivo: null` da 500 y viola la regla del proyecto

**Dónde:** `schemas/stock.py:35` + `routers/stock.py:232-243`.

**Reproducido:**

```
PATCH /api/stock/{id} {"cantidad": "10", "motivo": null}
-> IntegrityError: NOT NULL constraint failed: historial_stock.motivo
```

**Impacto.** `StockUpdate.motivo` tiene default `"Ajuste rápido"`, así que el
frontend nunca lo omite; pero un `null` explícito lo atraviesa y muere en la base.
Y hay algo más de fondo: `motivo: ""` (string vacío) **pasa sin problema**, con lo
cual se puede mover el stock sin motivo real. `CLAUDE.md` es taxativo:
*"Stock: nunca modificar cantidades sin registrar motivo"*.

**Solución.** Exigir un motivo con contenido, en el schema:

```python
# schemas/stock.py
from pydantic import BaseModel, field_validator

class StockUpdate(BaseModel):
    ...
    motivo: str = "Ajuste rápido"

    @field_validator("motivo")
    @classmethod
    def _motivo_con_contenido(cls, v: str) -> str:
        """La regla del proyecto es que la cantidad nunca se toca sin motivo.

        Era Optional[str] con default: un null explícito llegaba hasta la base y
        moría contra el NOT NULL de historial_stock (500), y un "" pasaba entero,
        dejando un ajuste sin explicación en el historial que alimenta el costo
        del papel.
        """
        limpio = (v or "").strip()
        if not limpio:
            raise ValueError("Indicá el motivo del ajuste: queda en el historial del artículo.")
        return limpio
```

---

## M-12 — MEDIO · `PUT /api/movimientos` con `monto: null` da 500

**Dónde:** `routers/movimientos.py:99-101`.

**Reproducido:**

```
PUT /api/movimientos/{id} {"monto": null}
-> TypeError: '<=' not supported between instances of 'NoneType' and 'decimal.Decimal'
```

`update_data.get("monto", db_mov.monto)` devuelve `None` cuando el campo viene
explícitamente en null (no cuando falta), y la comparación explota.

```diff
      nuevo_tipo = update_data.get("tipo", db_mov.tipo)
      nuevo_monto = update_data.get("monto", db_mov.monto)
-     if nuevo_tipo == "Pago" and nuevo_monto <= Decimal("0"):
+     # get() devuelve None si el campo vino explícitamente en null (distinto de
+     # que no venga): sin este chequeo, la comparación de abajo es un TypeError.
+     if nuevo_monto is None:
+         raise HTTPException(status_code=400, detail="El monto no puede quedar vacío.")
+     if nuevo_tipo == "Pago" and nuevo_monto <= Decimal("0"):
          raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0.")
```

---

## M-13 — MEDIO · `cantidad` de trabajo y de ítem de presupuesto acepta 0 y negativos

**Dónde:** `schemas/trabajos.py:18`, `:55`; `schemas/presupuestos.py:16`.

**Reproducido:**

```
POST /api/trabajos {cantidad: 0}   -> HTTP 200
POST /api/trabajos {cantidad: -5}  -> HTTP 200
POST /api/presupuestos items:[{cantidad: -10, precio_unitario: 100}] -> HTTP 200
```

**Impacto.** Dos consecuencias concretas:

1. `saldo_pendiente_entrega` (`trabajos_comun.py:27`) da negativo, y `_validar_cambio_estado`
   deja de avisar que falta entregar.
2. **Es un bypass del validador de montos.** `_validar_monto_no_negativo` protege
   `precio_unitario`, pero `convertir_presupuesto` calcula
   `precio_venta = Q2(item.cantidad * item.precio_unitario)` (`routers/presupuestos.py:369`)
   sin volver a validar: con `cantidad = -10` nace un **trabajo con precio negativo**,
   que es justo lo que `schemas/comun.py:61-77` explica que hay que impedir ("un
   precio negativo hace que un trabajo entregado figure como plata a favor").

**Solución.**

```python
# schemas/comun.py — junto a los otros validadores compartidos

def _validar_cantidad_positiva(valor: Optional[int]) -> Optional[int]:
    """Una cantidad de unidades a producir tiene que ser al menos 1.

    Con 0 o negativo, saldo_pendiente_entrega da un número sin sentido y, sobre
    todo, convertir_presupuesto calcula precio_venta = cantidad * precio_unitario
    sin revalidar: una cantidad negativa es la puerta por la que entra un precio
    negativo a trabajos, esquivando _validar_monto_no_negativo.
    """
    if valor is not None and valor < 1:
        raise ValueError(f"La cantidad tiene que ser al menos 1 (recibido: {valor}).")
    return valor
```

```python
# schemas/trabajos.py
class TrabajoBase(BaseModel):
    _cantidad_valida = field_validator("cantidad")(_validar_cantidad_positiva)

class TrabajoUpdate(BaseModel):
    _cantidad_valida = field_validator("cantidad")(_validar_cantidad_positiva)

# schemas/presupuestos.py
class ItemPresupuestoBase(BaseModel):
    _cantidad_valida = field_validator("cantidad")(_validar_cantidad_positiva)
```

---

## M-14 — MEDIO · El stock puede quedar negativo

**Dónde:** `schemas/stock.py:11` y `routers/stock.py:232-243`.

**Reproducido:**

```
POST  /api/stock       {"cantidad": "-50"}   -> HTTP 200, cantidad "-50.000"
PATCH /api/stock/{id}  {"cantidad": "-9999"} -> HTTP 200
```

`_descontar_papel` **sí** avisa cuando el stock no alcanza y exige `forzar=true`
(`routers/trabajos.py:137-144`, bien resuelto), pero el alta y el ajuste manual
entran sin control. Un stock negativo hace que ese aviso deje de tener sentido y
distorsiona el costo del papel.

Corresponde `_validar_monto_no_negativo` en `StockBase.cantidad`/`stock_minimo`/`costo_unitario`,
y un chequeo explícito en el PATCH que exija `forzar=true` para dejar negativo.

---

## M-15 — MEDIO · `MovimientoCreate.tipo` y `GastoCreate.categoria` son texto libre

**Dónde:** `schemas/movimientos.py:13`, `schemas/gastos.py:10`.

`calculos.py` sólo reconoce `tipo == "Pago"` (`_monto_pagos`, `_cobros_realizados`).
Un movimiento con `tipo: "pago"` (minúscula) o `"Cobro"` se guarda perfecto y **no
cuenta en ningún cálculo**: plata que entró y desaparece del sistema sin error.

Lo mismo con `categoria`, donde `CATEGORIA_COSTO_PRESUPUESTADO` se compara por
igualdad exacta (`calculos.py:353`): un typo lo convierte en gasto operativo y
cambia la ganancia del mes.

Mismo criterio que `ESTADOS_CHEQUE`: una constante en `models.py` y un validador.

---

## M-16 — MEDIO · `_generar_numero_*` revienta con un número de formato inesperado

**Dónde:** `routers/trabajos.py:77`, `routers/presupuestos.py:68`, `routers/entregas.py:54`.

Los tres hacen `int(partes[1])` sin protección.

**Reproducido** (con un `numero_orden` de `"OP-XXXXXX"` en la base):

```
POST /api/trabajos/{id}/imprimir-orden
-> ValueError: invalid literal for int() with base 10: 'XXXXXX'
```

El caso no es hipotético: es exactamente el escenario de **C-02**, donde el propio
`arranque.py` escribe números con sufijo. Ver la corrección unificada allí.

---

## M-17 — MEDIO · Sin techo en el tamaño de los payloads de lista

`PlanillaGuardarRequest.filas`, `PresupuestoCreate.items` y el carrito de
`POST /api/stock/compras` no tienen `max_length`. Además
`_validar_empleados_de_la_planilla` usa `ids.count(i)` dentro de un comprehension
(`routers/asistencia.py:40`), que es O(n²): una planilla de 10.000 filas cuelga el
worker. Con `-w 1` en el `Procfile`, cuelga **el sistema entero**.

```python
# schemas/asistencia.py
class PlanillaGuardarRequest(BaseModel):
    fecha: date
    # El taller tiene una docena de empleados: el techo es para que un payload
    # armado a mano no cuelgue el worker (la validación de repetidos es O(n²) y
    # el Procfile corre un solo worker).
    filas: list[FilaPlanillaGuardar] = Field(max_length=200)
```

```python
# routers/asistencia.py — de O(n²) a O(n)
from collections import Counter

    repetidos = {i for i, n in Counter(ids).items() if n > 1}
```

---

## B-07 — BAJO · `1e500` en un monto produce un 500

**Reproducido:**

```
POST /api/trabajos {"precio_venta": "1e500"}
-> StatementError: (decimal.InvalidOperation)
```

Pydantic acepta el valor (es finito), pero `Q2()` no puede cuantizarlo a dos
decimales dentro del contexto decimal por defecto. Se resuelve poniéndole techo al
importe, que además es sensato de negocio:

```python
# schemas/comun.py
# Techo de un importe. No existe un trabajo de mil millones en esta gráfica, y
# sin tope un valor como "1e500" atraviesa Pydantic (es finito) y revienta en
# Q2() al persistir, con un 500 en vez de un 422.
TOPE_IMPORTE = Decimal("999999999.99")

def _validar_monto_no_negativo(valor: Optional[Decimal]) -> Optional[Decimal]:
    if valor is not None and valor < 0:
        raise ValueError(f"El importe no puede ser negativo (recibido: {valor}).")
    if valor is not None and valor > TOPE_IMPORTE:
        raise ValueError(f"El importe supera el máximo admitido ({TOPE_IMPORTE}).")
    return valor
```

---

## B-08 — BAJO · La búsqueda de clientes no escapa los comodines SQL

**Dónde:** `routers/clientes.py:61-67`.

```python
filtro = f"%{buscar}%"
query = query.filter((models.Cliente.nombre_completo.ilike(filtro)) | ...)
```

**No hay inyección SQL:** SQLAlchemy parametriza el valor. Se verificó:
`GET /api/clientes/?buscar=%` devuelve 200 con la lista. Lo que sí pasa es que un
`%` o un `_` tipeados por el usuario funcionan como comodín: buscar `_` trae todo.
Cosmético. Se corrige con `.ilike(filtro, escape="\\")` y escapando el término.

---

## B-09 — BAJO · `_predicado_periodo` acepta cualquier valor y cae a "histórico"

**Dónde:** `routers/reportes.py:45`. Un typo en el query param (`este_ano` sin
tilde) devuelve el histórico completo presentado como si fuera el período pedido.
Es silencioso: el dashboard muestra números plausibles pero de otro rango.
Conviene un `Literal["este_mes", "mes_pasado", "este_anio", "historico"]` para que
FastAPI devuelva 422.

---

## B-10 — BAJO · Se puede cargar asistencia con fecha futura

`guardar_planilla` no valida `planilla.fecha`. Se puede cargar la planilla del año
que viene, y esas horas entran en cualquier resumen cuyo rango las incluya.

---

## MJ-04 — MEJORA · `eliminar_movimiento` contradice la regla documentada

`CLAUDE.md` dice *"Movimiento: debe ser auditable. No eliminar movimientos
históricos"*, pero `DELETE /api/movimientos/{id}` los borra (con asiento de
auditoría, que mitiga pero no cumple la regla). O se ajusta la regla en la
documentación, o el borrado pasa a ser una anulación con contra-asiento. Es una
decisión de negocio, no un bug: lo señalo para que sea explícita.

---
---

# FASE 5 — Concurrencia y condiciones de carrera

Ésta es la fase con los hallazgos más graves. Todos se **reprodujeron** lanzando
pedidos simultáneos desde varios hilos contra la aplicación real.

## Lo que está bien

El proyecto **conoce el problema** y lo resolvió correctamente en dos lugares, con
comentarios que explican el razonamiento mejor que muchos libros:

- **`imprimir_orden`** (`routers/trabajos.py:773-784`) reclama la impresión con un
  `UPDATE ... WHERE orden_impresa IS NOT TRUE` en vez de un `setattr`, y el
  comentario explica que el síntoma no sería stock de menos sino un historial con
  dos descuentos para una sola orden.
- **`_aplicar_saldo_favor`** (`routers/trabajos.py:274-343`) consume cada crédito
  con un `UPDATE` condicional sobre el valor observado, verifica el `rowcount` y
  no re-aplica si perdió la carrera.

El patrón correcto ya existe en el código. Lo que falta es aplicarlo en el resto.

## C-01 — CRÍTICO · Convertir un presupuesto dos veces crea trabajos duplicados

**Dónde:** `routers/presupuestos.py:340-400`.

**Reproducido.** Cuatro llamadas simultáneas a `POST /api/presupuestos/{id}/convertir`
sobre un presupuesto de un ítem:

```
códigos: [200, 409, 200, 200]
trabajos "Carrera" creados: 3   (debería ser 1)
```

**La carrera.** El guard de la línea 358 lee el estado y decide:

```python
if db_presupuesto.convertido_a_trabajo or any(i.trabajo_id for i in db_presupuesto.items):
    raise HTTPException(status_code=409, detail="Este presupuesto ya fue convertido a trabajo.")
```

Entre esa lectura y el `db.commit()` de la línea 397 hay varios `INSERT` y `flush`.
Tres requests leen `convertido_a_trabajo = False` antes de que ninguno commitee, y
las tres convierten.

**Impacto — el peor del sistema.** No es un error cosmético: **el cliente queda
facturado tres veces**. Los tres trabajos entran con su `precio_venta` en
`calcular_saldo_cliente` (que suma todo lo no cancelado), así que el saldo del
cliente se triplica. Además:

- cada trabajo duplicado descuenta papel del stock al imprimir su orden;
- aparecen tres tarjetas idénticas en el Kanban y el taller produce de más;
- limpiar el desastre es manual: los trabajos duplicados no se pueden borrar
  (`eliminar_trabajo` los bloquea por tener presupuesto asociado).

Un doble clic en "Convertir" alcanza para provocarlo.

**Solución.** El mismo `UPDATE` condicional que ya usa `imprimir_orden`: que la
base sea el árbitro, no una lectura previa.

```python
@router.post("/{presupuesto_id}/convertir", response_model=list[schemas.TrabajoResponse])
def convertir_presupuesto(
    presupuesto_id: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(usuario_actual),
):
    """Convierte un presupuesto en trabajos en una sola transacción.

    Crea UN TRABAJO POR ÍTEM (cada producto se produce por separado) y marca el
    presupuesto como convertido con un único commit.
    """
    db_presupuesto = obtener_o_404(db, models.Presupuesto, presupuesto_id, "Presupuesto no encontrado")

    if not db_presupuesto.cliente_id:
        raise HTTPException(status_code=400, detail="Asigná un cliente al presupuesto antes de convertirlo.")

    # El reclamo es un UPDATE condicional y no un `if convertido: raise`, porque
    # leer el flag y escribirlo son dos pasos: un doble clic mete dos requests en
    # el medio, las dos lo leen en False y las dos convierten. El resultado son
    # trabajos duplicados que facturan dos veces al mismo cliente y que después
    # no se pueden ni borrar (eliminar_trabajo los bloquea por tener presupuesto).
    # Acá gana uno solo: el WHERE lo resuelve la base, que es el único punto
    # donde los dos requests se cruzan. Mismo criterio que imprimir_orden.
    reclamado = (
        db.query(models.Presupuesto)
        .filter(
            models.Presupuesto.id == presupuesto_id,
            models.Presupuesto.convertido_a_trabajo.isnot(True),
        )
        .update(
            {"convertido_a_trabajo": True, "estado": "Aprobado"},
            synchronize_session=False,
        )
    )
    if not reclamado:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este presupuesto ya fue convertido a trabajo.")

    # Defensa aparte: un ítem ya vinculado significa que se convirtió por el otro
    # camino (marcar_convertido / trabajo_asociado_id), que no toca el flag.
    if any(i.trabajo_id for i in db_presupuesto.items):
        db.rollback()
        raise HTTPException(status_code=409, detail="Este presupuesto ya fue convertido a trabajo.")

    trabajos_creados = []
    for item in db_presupuesto.items:
        nuevo_trabajo = models.Trabajo(...)   # sin cambios
        db.add(nuevo_trabajo)
        db.flush()
        item.trabajo_id = nuevo_trabajo.id
        trabajos_creados.append(nuevo_trabajo)

    # convertido_a_trabajo y estado ya los escribió el UPDATE de arriba.
    asentar(db, usuario, models.ACCION_EDICION, ENTIDAD, db_presupuesto.id, ...)
    db.commit()
    ...
```

---

## C-02 — CRÍTICO · Un remito legado con sufijo `-DUP-` deja el módulo de entregas muerto

**Dónde:** `routers/entregas.py:41-57` + `arranque.py:144-161`.

**Reproducido.** Con dos remitos en la base, `RE-000001` y `RE-000001-DUP-abcd1234`
(exactamente el formato que escribe `arranque.py`), cualquier intento de emitir un
remito nuevo devuelve:

```
POST /api/entregas -> HTTP 409 {"detail":"No se pudo numerar el remito, reintentá."}
```

**Y no se recupera nunca.** No es un fallo transitorio: es permanente.

**La cadena, paso a paso:**

1. `arranque.py:157` escribe, ante un choque de unicidad en la migración legada:
   `numero = f"{trabajo.numero_remito}-DUP-{trabajo.id[:8]}"` → `"RE-000001-DUP-abcd1234"`.
2. `_generar_numero_remito` pide el máximo con `ORDER BY numero_remito DESC`.
   Al ser texto, `"RE-000001-DUP-abcd1234"` ordena **después** de `"RE-000001"` y
   también de `"RE-000012"`: gana el sufijo.
3. `partes = ultimo.numero_remito.split("-")` → `["RE","000001","DUP","abcd1234"]`,
   de largo 4. El `if len(partes) == 2` falla y la función cae al `return "RE-000001"`.
4. Ese número **ya existe** → `IntegrityError` por el `unique` de `Entrega.numero_remito`.
5. El `while` reintenta… y `_generar_numero_remito` vuelve a devolver `"RE-000001"`,
   porque nada cambió. Los 3 intentos se consumen contra el mismo número y sale el 409.

**Impacto.** El taller no puede emitir un solo remito. La mercadería no se puede
entregar con comprobante. Y el disparador lo genera el propio sistema al arrancar
sobre una base con historial —justamente el escenario que la migración vino a
resolver—. La ironía es que `arranque.py:149-155` documenta con precisión el bug
de numeración del sistema viejo… y el parche que aplica es el que rompe el nuevo.

**Solución.** Dos cambios que se refuerzan: numerar sobre el máximo **numérico**
(ignorando lo que no tenga el formato canónico), y que el sufijo de la migración
no contamine el espacio de numeración.

```python
# routers/entregas.py

import re

# Formato canónico del número de remito. Lo que no matchea (un número legado con
# sufijo, un dato cargado a mano) no participa de la numeración: si participara,
# como el orden es alfabético, "RE-000001-DUP-x" ganaría sobre "RE-000012" y el
# correlativo volvería para atrás.
_PATRON_REMITO = re.compile(r"^RE-(\d{6})$")


def _generar_numero_remito(db: Session) -> str:
    """Número correlativo del remito: RE-000001, RE-000002...

    Se toma el máximo NUMÉRICO de los números bien formados, en vez del máximo
    alfabético de la tabla entera. Con el orden de texto, un remito legado
    "RE-000001-DUP-abcd1234" (los escribe arranque.py al migrar duplicados
    históricos) quedaba primero, el split daba 4 partes, la función caía al
    fallback "RE-000001" y ese número ya existía: IntegrityError, los 3
    reintentos devolvían siempre lo mismo y el módulo entero quedaba tirando 409.
    """
    numeros = [
        int(m.group(1))
        for (valor,) in db.query(models.Entrega.numero_remito).all()
        if (m := _PATRON_REMITO.match(valor or ""))
    ]
    return f"RE-{(max(numeros) + 1 if numeros else 1):06d}"
```

```diff
  # arranque.py — el sufijo del duplicado legado no debe parecer un número de remito
-             numero = f"{trabajo.numero_remito}-DUP-{trabajo.id[:8]}"
+             # Prefijo distinto a propósito: con "RE-...-DUP-..." el número
+             # legado entraba en el orden alfabético de _generar_numero_remito y
+             # rompía la numeración de todos los remitos nuevos.
+             numero = f"LEGADO-{trabajo.numero_remito}-{trabajo.id[:8]}"
```

**Verificación sugerida antes de desplegar** (sólo lectura, sobre la base real):

```sql
SELECT numero_remito FROM entregas
WHERE numero_remito NOT GLOB 'RE-[0-9][0-9][0-9][0-9][0-9][0-9]';
```

Si devuelve filas, **el módulo de remitos ya está caído en esa instalación**.

---

## C-04 — CRÍTICO · Órdenes de producción con números duplicados

**Dónde:** `routers/trabajos.py:58-80` + `models.py:100`.

**Reproducido.** Diez `POST /api/trabajos/{id}/imprimir-orden` simultáneos sobre
**diez trabajos distintos**:

```
códigos: [200 ×10]
números asignados: OP-000001 ×8, OP-000002 ×2
números únicos: 2 de 10
```

**Ocho boletas físicas con el mismo número de orden.**

**Por qué el guard existente no alcanza.** El `UPDATE` condicional de la línea 773
protege contra imprimir **el mismo trabajo** dos veces (idempotencia), y eso lo hace
bien. Pero `_generar_numero_orden` corre **antes** (línea 763), lee el máximo, y no
hay unicidad en `Trabajo.numero_orden`: diez requests sobre trabajos distintos leen
todos el mismo máximo y todos escriben el mismo número siguiente.

**Impacto.** El número de orden es **cómo el taller identifica un trabajo**: figura
en la boleta física, es lo que se canta en producción, es el `resumen` de cada
asiento de auditoría (`trabajos_comun.py:20`) y es la clave con la que se busca en
el informe. Con números repetidos:

- dos boletas distintas dicen "OP-000001" y no hay forma de saber cuál es cuál;
- el historial de stock atribuye descuentos a un número ambiguo (`"Orden OP-000001"`);
- la auditoría deja de poder rastrear qué trabajo se tocó.

No hace falta concurrencia extrema: dos personas imprimiendo su boleta al mismo
tiempo, que es la operación normal de un taller con tres puestos, alcanza.

**Solución.** Unicidad en la base + numeración numérica + reintento, igual que
`Entrega`. El mismo tratamiento se aplica a `Presupuesto.numero_secuencia` (**A-13**).

```python
# models.py
class Trabajo(Base):
    # unique: el número correlativo se genera leyendo el máximo y sumando uno, y
    # eso son dos pasos. Dos impresiones simultáneas sobre trabajos DISTINTOS
    # leen el mismo máximo y escriben el mismo número: ocho boletas físicas con
    # el mismo "OP-000001". La unicidad es lo que obliga a que gane una sola y
    # deja que el endpoint reintente. Mismo criterio que Entrega.numero_remito.
    numero_orden = Column(String, index=True, nullable=True, unique=True)
```

```python
# routers/trabajos.py
import re
from sqlalchemy.exc import IntegrityError

_PATRON_ORDEN = re.compile(r"^OP-(\d{6})$")


def _generar_numero_orden(db: Session) -> str:
    """Número correlativo de orden: OP-000001, OP-000002...

    Máximo NUMÉRICO de los números bien formados, no máximo alfabético: un
    numero_orden con otro formato (cargado a mano, migrado) hacía que
    int(partes[1]) tirara ValueError y el endpoint devolviera un 500.
    """
    numeros = [
        int(m.group(1))
        for (valor,) in db.query(models.Trabajo.numero_orden)
                          .filter(models.Trabajo.numero_orden.isnot(None)).all()
        if (m := _PATRON_ORDEN.match(valor or ""))
    ]
    return f"OP-{(max(numeros) + 1 if numeros else 1):06d}"


@router.post("/{trabajo_id}/imprimir-orden")
def imprimir_orden(trabajo_id: str, forzar: bool = False, ...):
    db_trabajo = obtener_o_404(db, models.Trabajo, trabajo_id, "Trabajo no encontrado")

    if not db_trabajo.orden_impresa:
        # El UPDATE condicional garantiza que un MISMO trabajo se imprima una
        # sola vez, pero no que dos trabajos DISTINTOS no se lleven el mismo
        # número: ambos leen el máximo antes de que ninguno commitee. Por eso
        # numero_orden es unique y acá se reintenta ante el choque.
        intentos_restantes = 5
        while True:
            numero_orden = _generar_numero_orden(db)
            reclamada = (
                db.query(models.Trabajo)
                .filter(models.Trabajo.id == trabajo_id, models.Trabajo.orden_impresa.isnot(True))
                .update(
                    {
                        "orden_impresa": True,
                        "numero_orden": numero_orden,
                        "fecha_orden_impresa": datetime.now(timezone.utc),
                    },
                    synchronize_session=False,
                )
            )
            if not reclamada:
                db.rollback()   # perdimos la carrera: el otro ya la imprimió
                break

            try:
                _descontar_papel(db, db_trabajo, numero_orden, forzar)
                detalle = f"orden {numero_orden} emitida"
                if forzar:
                    detalle += " (forzada: el papel no alcanzaba)"
                asentar(db, usuario, models.ACCION_EDICION, ENTIDAD, trabajo_id,
                        resumen_trabajo(db_trabajo), detalle)
                db.commit()
                break
            except IntegrityError:
                # Otro trabajo se quedó con ese número entre el cálculo y el
                # commit: se reintenta con el siguiente.
                db.rollback()
                intentos_restantes -= 1
                if not intentos_restantes:
                    raise HTTPException(status_code=409,
                                        detail="No se pudo numerar la orden, reintentá.")
        db.refresh(db_trabajo)

    pdf = construir_orden_pdf(db_trabajo, db_trabajo.cliente, db_trabajo.papel)
    ...
```

---

## A-13 — ALTO · Números de comprobante de presupuesto duplicados

**Dónde:** `routers/presupuestos.py:52-72` + `models.py:234`.

**Reproducido.** Diez altas simultáneas de presupuesto:

```
números de comprobante: 0001-000001 ×2, 0001-000002 ×3, 0001-000003 ×3, 0001-000004 ×2
únicos: 4 de 10
```

Mismo defecto que C-04, sobre el número que el cliente usa para referirse a su
presupuesto por teléfono. Se corrige igual: `unique=True` en la columna, máximo
numérico con `re`, y reintento ante `IntegrityError`. Es menos grave que la orden
sólo porque un presupuesto duplicado no dispara producción.

---

## A-14 — ALTO · Dos entregas simultáneas pueden superar la cantidad del trabajo

**Dónde:** `routers/entregas.py:93-112`.

**Reproducido.** Dos remitos de 60 unidades, en simultáneo, sobre un trabajo de 100:

```
códigos: [200, 200]
total entregado: 120 de 100
```

Ninguno de los dos pidió `forzar=true`. La validación de
`saldo_pendiente_entrega` (línea 103) lee las entregas existentes antes de que la
otra transacción commitee, así que ambas ven 100 disponibles.

**Impacto.** Se emiten remitos por mercadería que no existe, y el aviso de
`_validar_cambio_estado` al pasar a "Entregado" queda inservible (el pendiente da
negativo). El operador confía en un control que en ese momento no controló nada.

**Solución.** Revalidar dentro de la transacción, después del `flush` de los ítems
y antes del `commit`, releyendo desde la base:

```python
    for item in entrega_in.items:
        db.add(models.ItemEntrega(entrega_id=entrega.id, trabajo_id=item.trabajo_id, cantidad=item.cantidad))
    db.flush()

    if not forzar:
        # Revalidación DENTRO de la transacción: el chequeo de arriba lee el
        # saldo antes de insertar, así que dos remitos simultáneos ven los dos
        # el mismo pendiente y entre los dos entregan de más. Acá ya están
        # nuestros ítems en la transacción, así que el total es el real.
        for item in entrega_in.items:
            total = db.query(func.coalesce(func.sum(models.ItemEntrega.cantidad), 0)).filter(
                models.ItemEntrega.trabajo_id == item.trabajo_id
            ).scalar()
            trabajo = trabajos_por_id[item.trabajo_id]
            if total > trabajo.cantidad:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Otra entrega de '{trabajo.descripcion_producto}' se registró "
                        f"al mismo tiempo: entre las dos superan las {trabajo.cantidad} "
                        "unidades del trabajo. Revisá el saldo y reintentá."
                    ),
                )
```

---

## A-15 — ALTO · Ajustes de stock simultáneos descuadran el historial

**Dónde:** `routers/stock.py:217-255`.

**Reproducido.** Tres ajustes concurrentes de un artículo con 1000 pliegos, a 900,
800 y 700:

```
cantidad final:  800.000
historial:       -100 ("ajuste a 900"), -300 ("ajuste a 700"), -200 ("ajuste a 800")
1000 + suma(historial) = 400   vs.   cantidad real = 800
```

**Impacto.** `HistorialStock` es la fuente de verdad del movimiento de papel: es lo
que explica a dónde se fue el stock y lo que alimenta el costo. Acá quedó
**descuadrado en 400 pliegos**, sin ningún error visible. Peor que el "lost update"
en sí (que es esperable en un ajuste manual) es que el historial afirme algo que no
pasó: reconstruir la cantidad desde los movimientos da un número distinto al real.

**Solución.** Que la diferencia y la cantidad se apliquen con un `UPDATE`
condicional, y que el historial registre lo que la base efectivamente aplicó:

```python
    if update_data.cantidad is not None:
        # Leer la cantidad, restar y escribir son tres pasos: dos ajustes
        # simultáneos leen los dos el mismo valor de partida y el historial
        # termina afirmando movimientos que no cuadran con la cantidad real.
        # El UPDATE condicional sobre la cantidad observada hace que gane uno
        # solo; el que pierde recibe un 409 y vuelve a intentar sobre el dato
        # ya actualizado. Mismo criterio que _aplicar_saldo_favor.
        cantidad_previa = db_art.cantidad
        diferencia = update_data.cantidad - cantidad_previa

        if diferencia != 0:
            aplicado = (
                db.query(models.ArticuloStock)
                .filter(
                    models.ArticuloStock.id == articulo_id,
                    models.ArticuloStock.cantidad == cantidad_previa,
                )
                .update({"cantidad": update_data.cantidad}, synchronize_session=False)
            )
            if not aplicado:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Otra persona ajustó este artículo al mismo tiempo. Refrescá y reintentá.",
                )
            db.add(models.HistorialStock(
                articulo_id=db_art.id,
                diferencia=diferencia,
                motivo=update_data.motivo,
            ))
```

El mismo problema afecta a `_descontar_papel` y `_devolver_papel`
(`routers/trabajos.py:152` y `:183`), que hacen
`articulo.cantidad = Q3(articulo.cantidad ± pliegos)` sobre el valor en memoria.
Ahí el guard de `orden_impresa`/`papel_devuelto` limita el daño al mismo trabajo,
pero dos trabajos distintos descontando del mismo papel a la vez se pisan igual.

> Nota de implementación: `Cantidad` persiste como TEXT, así que un `UPDATE`
> relativo (`cantidad = cantidad - pliegos`) exigiría un `CAST` en SQL. La opción
> más simple para este proyecto es serializar las escrituras de stock abriendo la
> transacción con `BEGIN IMMEDIATE`, que SQLite sí soporta:
> `db.execute(text("BEGIN IMMEDIATE"))` al entrar en la sección crítica.

---

## A-16 — ALTO · Altas simultáneas del mismo cliente crean duplicados

**Dónde:** `routers/clientes.py:40-42` + `models.py:55`.

**Reproducido.** Seis altas simultáneas con el mismo DNI/CUIT:

```
códigos: [200, 200, 200, 400, 400, 400]
clientes creados con ese CUIT: 3   (debería ser 1)
```

El `SELECT` previo atrapó tres, pero los otros tres se cruzaron. Con la cuenta
corriente partida en tres fichas, ninguna muestra el saldo real del cliente.

**Solución:** ver **M-08** (`unique=True` en `dni_cuit`) más el manejo del choque:

```python
    nuevo_cliente = models.Cliente(**cliente.model_dump())
    db.add(nuevo_cliente)
    try:
        db.flush()
    except IntegrityError:
        # El SELECT de arriba filtra el caso normal, pero leer y escribir son dos
        # pasos: dos altas simultáneas del mismo CUIT lo pasan las dos. El unique
        # de la columna es el único árbitro que no se puede esquivar.
        db.rollback()
        raise HTTPException(status_code=400, detail="Este DNI/CUIT ya está registrado.")
```

---

## M-18 — MEDIO · `_migrar_entregas_legado` puede tumbar el arranque de la app

**Dónde:** `arranque.py:116-168`.

El `try/except IntegrityError` cubre el `flush()` de la cabecera `Entrega`, pero el
`db.add(models.ItemEntrega(...))` + `db.commit()` de las líneas 163-168 quedan
afuera. Si ese commit falla (por ejemplo, un `trabajo.cantidad` en NULL contra el
`nullable=False` del ítem), la excepción sube y **tumba el arranque de la
aplicación entera**: `aplicar_migraciones_pendientes()` se llama en el nivel de
módulo de `main.py` (línea 23), antes de que exista `app`. El sistema no levanta y
el error aparece en el log del deploy, no en una pantalla.

Conviene envolver cada trabajo migrado en su propio try/except que registre y siga,
que es justamente lo que el docstring dice que se busca ("si uno falla, no se pierda
lo que ya se migró antes en la misma corrida").

---

## M-19 — MEDIO · `guardar_planilla` sin protección de escritura concurrente

`RegistroAsistencia` tiene el `UniqueConstraint(empleado_id, fecha)` correcto
(`models.py:410-412`), pero el upsert del router (`routers/asistencia.py:139-155`)
lee y decide antes de escribir. Dos guardados simultáneos del mismo día chocan
contra el constraint → `IntegrityError` → 500. Es el caso menos probable (una sola
persona carga la planilla), pero el manejador global de A-08 lo convertiría en un
409 legible sin ningún trabajo extra.

---

## B-11 — BAJO · El rollback del reintento de remito expira objetos ya cargados

**Dónde:** `routers/entregas.py:126-130`. Tras `db.rollback()`, los objetos
`cliente` y `trabajos_por_id` quedan expirados y se recargan solos al usarlos
(SQLAlchemy lo maneja). Funciona, pero significa consultas extra silenciosas en el
camino de reintento.

---

---

# FASE 6 — Generación y descarga de PDFs

> Fase pedida explícitamente. Se revisaron las **cuatro** salidas en PDF del
> sistema, con foco en la hoja de costos internos.

| Comprobante | Dónde se arma | Cómo se descarga | Datos sensibles |
|---|---|---|---|
| Orden de producción | Backend, ReportLab (`pdf/orden.py`) | `POST /api/trabajos/{id}/imprimir-orden` → `Response` con `Content-Disposition` | **No** lleva precio ni costo |
| Presupuesto (cliente) | Backend, ReportLab (`pdf/presupuesto.py`) | `GET /api/presupuestos/{id}/pdf-cliente` → blob | Sólo precios de venta |
| Remito / Orden de entrega | Backend, ReportLab (`pdf/entrega.py`) | `POST /api/entregas` y `GET /api/entregas/{id}/pdf` | **No** lleva importes |
| **Hoja de costos internos** | **Frontend, html2pdf (CDN)** | `html2pdf().save()` en el navegador | **Costos, margen y ganancia por ítem** |

## Lo que está bien

- **La separación de responsabilidades en los tres PDF del backend es correcta.**
  `pdf/*.py` no toca la base ni tiene efectos: recibe objetos ya cargados y
  devuelve bytes. Los tres docstrings lo dicen explícitamente.
- **Ningún PDF filtra información de más.** Se verificó campo por campo: la orden
  de producción (que puede imprimir cualquier rol, incluido mostrador) muestra
  cliente, descripción, papel, tintas y terminación — **nunca precio ni costo**.
  Coherente con `CAMPOS_DE_PLATA` de `routers/trabajos.py`.
- **El método HTTP está bien elegido.** `imprimir-orden` es `POST` porque asigna
  número y descuenta stock; `pdf-cliente` y la reimpresión de remito son `GET`
  porque no tienen efectos. Esa distinción está razonada en los docstrings y es
  exactamente la correcta.
- **`_nombre_archivo_pdf`** (`routers/presupuestos.py:237-247`) sanitiza el nombre
  del cliente con `re.sub(r"[^a-zA-Z0-9]+", "_", crudo)` antes de meterlo en
  `Content-Disposition`. Eso **cierra la inyección de cabecera**: un cliente
  llamado `X"; attachment; filename="otro` no puede partir el header. Bien visto.

## A-17 — ALTO · La hoja de costos internos descarga la base de presupuestos entera

**Dónde:** `frontend/js/presupuestos.js:668-673`.

```javascript
async function armarMoldeBasePDF(presupuesto_id) {
    const [respP, respC] = await Promise.all([ fetch(`${API_URL}/presupuestos/`), fetch(`${API_URL}/clientes/`) ]);
    const p = (await respP.json()).find(x => x.id === presupuesto_id);
    const c = (await respC.json()).find(x => x.id === p.cliente_id);
    return { p, c };
}
```

**Impacto.** Para generar el PDF de **un** presupuesto, el navegador se baja:

- **todos** los presupuestos, cada uno con **todos** sus ítems, sus
  `detalles_costos` (JSON) y sus márgenes;
- **todos** los clientes.

…y descarta el 99% con un `.find()`. Se combina con **A-06**: `GET /api/presupuestos/`
no usa `selectinload`, así que cada presupuesto de la lista dispara su propia
consulta de ítems en el backend. Un clic en "PDF Int" con 400 presupuestos
cargados son cientos de consultas SQL y varios MB por la red, para armar una hoja.

**Solución.** Pedir el presupuesto puntual. El endpoint no existe todavía, y vale
la pena crearlo porque lo necesitan los dos PDF:

```python
# routers/presupuestos.py
# OJO: va DESPUÉS de /informe-trabajos y antes de cualquier otra ruta con
# parámetro, para que "informe-trabajos" no se interprete como un id (mismo
# cuidado que documenta routers/clientes.py).

@router.get("/{presupuesto_id}", response_model=schemas.PresupuestoResponse)
def obtener_presupuesto(presupuesto_id: str, db: Session = Depends(get_db)):
    """Un presupuesto con sus ítems.

    Existe porque el frontend armaba la hoja de costos bajándose TODOS los
    presupuestos y TODOS los clientes para quedarse con uno (ver
    armarMoldeBasePDF): con selectinload esto son dos consultas fijas.
    """
    return (
        db.query(models.Presupuesto)
        .options(selectinload(models.Presupuesto.items))
        .filter(models.Presupuesto.id == presupuesto_id)
        .first()
        or _no_encontrado()
    )
```

```javascript
// frontend/js/presupuestos.js
// Antes se bajaba la lista completa de presupuestos y de clientes para quedarse
// con uno solo: con 400 presupuestos eran varios MB y cientos de consultas en
// el backend por cada clic en "PDF Int".
async function armarMoldeBasePDF(presupuesto_id) {
    const resp = await fetch(`${API_URL}/presupuestos/${presupuesto_id}`);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(detalleError(err, 'No se encontró el presupuesto.'));
    }
    const p = await resp.json();

    let c = null;
    if (p.cliente_id) {
        const respC = await fetch(`${API_URL}/clientes/`);
        if (respC.ok) c = (await respC.json()).find(x => x.id === p.cliente_id) ?? null;
    }
    return { p, c };
}
```

---

## A-18 — ALTO · `generarPDFInterno` no maneja ningún error: el botón no hace nada

**Dónde:** `frontend/js/presupuestos.js:705-755`.

Éste es el hallazgo de "promesas no esperadas" que corresponde a esta fase, y hay
**tres** problemas encadenados en la misma función:

**1. La función es `async` y se la invoca desde un `onclick` sin `await` ni `.catch()`**
(`presupuestos.js:552`):

```html
<button ... onclick="generarPDFInterno('${p.id}')">PDF Int</button>
```

Cualquier excepción adentro se convierte en un *unhandled promise rejection*: va a
la consola del navegador y **el usuario no ve absolutamente nada**. Aprieta el
botón, no pasa nada, y no hay forma de saber por qué. Su hermana `generarPDFCliente`
**sí** tiene `try/catch` con `Swal.fire` (líneas 680-701); a ésta le falta.

**2. `armarMoldeBasePDF` revienta si el presupuesto no está en la lista.**
`const c = (await respC.json()).find(x => x.id === p.cliente_id)` — si el `.find()`
de la línea anterior no encontró el presupuesto (fue borrado por otro puesto, o la
lista se truncó), `p` es `undefined` y `p.cliente_id` tira
`TypeError: Cannot read properties of undefined`. Que, por el punto 1, es
silencioso.

**3. `html2pdf()` devuelve una promesa que nadie espera** (línea 750):

```javascript
html2pdf().set({ ... }).from(div).save();
```

`.save()` es asíncrono (renderiza con html2canvas y arma el PDF). Sin `await` ni
`.catch()`, un fallo del render —una imagen que no carga, memoria insuficiente con
muchos ítems— también termina en silencio. Y como la función retorna antes de que
el PDF esté listo, no hay manera de avisar "listo" ni de deshabilitar el botón
mientras trabaja.

**Solución.**

```javascript
// PDF INTERNO (Detalle de todos los costos e ítems del formulario)
// A diferencia de generarPDFCliente, este PDF se arma en el navegador con
// html2pdf: es la única salida que no pasó al backend todavía (ver A-19).
async function generarPDFInterno(presupuesto_id) {
    try {
        const { p, c } = await armarMoldeBasePDF(presupuesto_id);
        const nombreCliente = c ? c.nombre_completo : 'Sin cliente';
        const shortId = p.id.substring(0, 6).toUpperCase();
        const items = p.items || [];

        ...  // el armado del HTML no cambia

        // html2pdf().save() es asíncrono: renderiza con html2canvas y recién
        // después escribe el archivo. Sin await, un fallo del render (una imagen
        // que no carga, un presupuesto con muchos ítems) quedaba en silencio y
        // el operador veía que el botón no hacía nada.
        await html2pdf().set({
            margin: 10,
            filename: `Costos_Internos_${shortId}.pdf`,
            pagebreak: { mode: ['avoid-all', 'css'] },
        }).from(div).save();
    } catch (error) {
        // Sin esto la función es async, se la llama desde un onclick sin await y
        // cualquier error termina como unhandled rejection: sólo en la consola.
        console.error('Error generando la hoja de costos:', error);
        Swal.fire('No se pudo generar la hoja de costos', error.message, 'error');
    }
}
```

---

## M-20 — MEDIO · La hoja de costos es la única salida que no está en el backend

**Dónde:** `frontend/js/presupuestos.js:705-755` vs. `pdf/`.

Los otros tres comprobantes migraron a ReportLab en el backend. La hoja de costos
quedó armada con `html2pdf` en el navegador, lo que arrastra tres consecuencias:

1. **Depende de un CDN externo** (`cdnjs.cloudflare.com`). **Sin internet, el botón
   no funciona** — y el sistema está pensado para correr en la PC del taller, donde
   la conexión no está garantizada. Ver **C-03**.
2. **El resultado depende del navegador**: html2canvas rasteriza, así que el PDF
   sale como imagen (no seleccionable, no buscable, más pesado) y con tipografía y
   saltos distintos según Chrome o Firefox.
3. **Es una segunda forma de armar comprobantes** en un proyecto cuya filosofía
   declarada es evitar la duplicación de criterios.

No es urgente —funciona—, pero migrarla a `pdf/costos.py` cerraría el círculo y
haría que las cuatro salidas compartan estilo, helpers (`pesos`, `texto`,
`ruta_asset`) y comportamiento offline. Es la deuda técnica más clara que le queda
al módulo de PDFs.

---

## M-21 — MEDIO · `GET /api/entregas/{id}/pdf` no verifica a qué cliente pertenece el remito

**Dónde:** `routers/entregas.py:156-172`.

Cualquier usuario con token (los tres puestos) puede pedir el PDF de cualquier
remito con sólo tener el `entrega_id`. Como los ids son UUID v4, no se pueden
adivinar, así que el riesgo práctico es bajo — y el remito no lleva importes. Se
menciona porque es el único endpoint de descarga sin ninguna verificación de
pertenencia.

---

## B-12 — BAJO · `revokeObjectURL` inmediatamente después del `click()`

**Dónde:** `frontend/js/presupuestos.js:696-698`, `frontend/js/app.js:140-141`.

```javascript
enlace.click();
enlace.remove();
URL.revokeObjectURL(enlace.href);
```

Revocar la URL en el mismo tick que el `click()` es una carrera conocida: en la
práctica funciona (el click es síncrono y el navegador ya tomó el blob), pero la
forma robusta es diferirlo:

```javascript
enlace.click();
enlace.remove();
// Diferido: revocar en el mismo tick que el click puede cancelar la descarga en
// algunos navegadores, que todavía no tomaron el blob.
setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
```

---

## B-13 — BAJO · La orden de producción y el remito buscan un `logo.png` que no existe

**Dónde:** `pdf/orden.py:39`, `pdf/entrega.py:138`.

`ruta_asset("logo.png")` devuelve `None` porque en `frontend/assets/` sólo hay
`firma-facu.png` y `logo-presupuesto-cl.png`. Los dos comprobantes caen siempre al
fallback de texto ("GRÁFICA VIAMONTE"). Está previsto y comentado
(`pdf/entrega.py:26-27`), así que no es un bug — es una tarea pendiente: agregar el
archivo y los dos PDF se actualizan solos.

---

## MJ-05 — MEJORA · El nombre del archivo de la orden no se sanitiza

**Dónde:** `routers/trabajos.py:809`.

```python
headers={"Content-Disposition": f'attachment; filename="orden_{db_trabajo.numero_orden}.pdf"'}
```

`numero_orden` lo genera el backend con formato `OP-000001`, así que hoy es seguro.
Pero es el único de los cuatro que **no** pasa por un sanitizador, a diferencia de
`_nombre_archivo_pdf` en presupuestos. Conviene unificar el criterio, aunque más no
sea por consistencia.

---
---

# FASE 7 — Frontend

Archivos revisados: `index.html` (1361 líneas), `style.css`, y los 13 módulos de
`frontend/js/`.

## Lo que está bien

- **`esc()` existe, está bien implementada y se usa mucho.** Escapa los cinco
  caracteres correctos (`& < > " '`) y el comentario explica exactamente por qué
  hace falta (`core.js:69-77`). El problema no es que falte la herramienta: es que
  quedaron 25 lugares sin usarla (**C-05**).
- **El interceptor de `fetch`** (`core.js:126-152`) es una gran decisión: un solo
  lugar donde inyectar el token en vez de tocar ~98 llamadas, con la salvedad
  explícita de no filtrarlo a dominios de terceros y el manejo centralizado del 401.
- **No hay CSRF posible**: el token viaja en `Authorization`, no en cookie, así que
  un pedido cross-site no lo lleva.
- **`aplicarPermisos()`** oculta lo que el puesto no maneja y el comentario aclara
  que **acá no se protege nada** — que la protección real está en el backend. Ese
  es exactamente el modelo mental correcto, y se verificó que el backend cumple.
- **`fechaHoyLocal()`** evita el clásico `toISOString()` que desplaza el día en
  UTC-3. Está documentado y es correcto.
- **`saldoMostrable()`** implementa la regla de "saldo negativo = plata a favor" en
  un solo lugar, para que la tabla y la ficha no puedan divergir.

## C-05 — CRÍTICO · XSS almacenado en 25 puntos, con escalada de privilegios

**Dónde:** `clientes.js`, `cheques.js`, `gastos.js`, `stock.js`, `trabajos.js`,
`presupuestos.js`.

Todo el render arma HTML por interpolación y lo inserta con `innerHTML`. El proyecto
tiene `esc()` justamente para esto, pero **25 interpolaciones de campos de texto
libre no pasan por ahí**:

| Archivo:línea | Expresión sin escapar | Quién puede escribir ese texto |
|---|---|---|
| `clientes.js:131` | `${n.texto}` (texto de una nota) | **los tres puestos** |
| `clientes.js:88` | `${textoPago}` | derivado |
| `clientes.js:312` | `${cliente.nombre_empresa \|\| '-'}` | **los tres puestos** |
| `gastos.js:161` | `${g.concepto}` | **admin y mostrador** |
| `gastos.js:159` | `${g.categoria}` | admin y mostrador |
| `gastos.js:163` | `${g.metodo_pago}`, `${g.comprobante}`, `${g.responsable}` | admin y mostrador |
| `gastos.js:59,61` | `${t.descripcion_producto}`, `${detalle}` | admin |
| `stock.js:441` | `${h.motivo}` (motivo de un ajuste) | **los tres puestos** |
| `stock.js:335,336` | `${s.categoria}`, `${s.proveedor}` | **los tres puestos** |
| `stock.js:372` | `${textoDif}` | derivado |
| `trabajos.js:487` | `${t.descripcion_producto \|\| 'Trabajo'}` | admin |
| `cheques.js:36` | `${c.nombre_completo \|\| ...}` (en un `<option>`) | **los tres puestos** |
| `cheques.js:152,162,163` | `${ch.destinatario_endoso}`, `${ch.banco}`, `${ch.numero}`, `${nombreParte}` | admin |
| `cheques.js:371,375` | `${cheque.banco}`, `${cheque.numero}` (dentro de `Swal.fire({html:...})`) | admin |
| `presupuestos.js:318,543` | `${p.numero_secuencia}`, `${resumenItems}` | admin |

**El vector completo, paso a paso:**

1. Un usuario con rol **`mostrador`** (el permiso más bajo) da de alta un cliente o
   escribe una nota con este contenido, que el backend acepta sin problema porque
   `NotaCreate.texto` es un `str` sin restricciones:

   ```
   <img src=x onerror="fetch('/api/backup').then(r=>r.blob()).then(b=>/* exfiltrar */)">
   ```

2. El **admin** abre la ficha de ese cliente. `cargarFichaCliente()` inserta el
   texto con `innerHTML +=` (`clientes.js:131`) y el navegador ejecuta el `onerror`
   **con la sesión del admin**.

3. Desde ahí, el script tiene todo:
   - `localStorage.getItem('viamonte_token')` → el token de admin (**M-03**);
   - `GET /api/backup` → **la base de datos completa** (clientes, precios, saldos,
     cheques, sueldos) en un solo pedido;
   - `GET /api/clientes/saldos` → la facturación histórica de la gráfica;
   - cualquier `DELETE` del sistema.

**Es una escalada de privilegios de `mostrador` a `admin`.** Todo el trabajo de
`_trabajo_visible()` —vaciar los campos de plata en la respuesta para que el taller
no vea el margen, con ese comentario tan preciso sobre que no alcanza con no
pintarlos en el frontend— queda anulado por esta vía.

Y no hace falta mala intención para *romper* la pantalla: un cliente llamado
`Muebles < & Cía` desarma el HTML de la tabla. Es el mismo problema que
`core.js:70-73` describe ("un cliente O'Brien o una descripción con `<` rompían el
markup") y que `esc()` vino a resolver — sólo que quedó a medio aplicar.

**Solución.** Envolver cada uno de los 25 puntos en `esc()`. Los tres más urgentes,
como muestra del patrón:

```diff
  // frontend/js/clientes.js:131 — el más expuesto: lo escribe cualquier puesto
-                     <div>${n.texto}</div>
+                     <div>${esc(n.texto)}</div>
```

```diff
  // frontend/js/gastos.js:159-163
-                     <td><span style="...">${g.categoria}</span></td>
+                     <td><span style="...">${esc(g.categoria)}</span></td>
                      <td>
-                         ${g.concepto} ${badgeTrabajo}<br>
+                         ${esc(g.concepto)} ${badgeTrabajo}<br>
                          <span style="...">
-                             💳 ${g.metodo_pago} | 🧾 ${g.comprobante} | 👤 ${g.responsable || 'General'}
+                             💳 ${esc(g.metodo_pago)} | 🧾 ${esc(g.comprobante)} | 👤 ${esc(g.responsable || 'General')}
                          </span>
                      </td>
```

```diff
  // frontend/js/stock.js:441 — el motivo lo escribe cualquier puesto
-                     <td style="padding: 8px 4px;">${h.motivo}</td>
+                     <td style="padding: 8px 4px;">${esc(h.motivo)}</td>
```

**Los `<option>` también.** `cheques.js:36` inserta el nombre del cliente en un
`<option>`; ahí un `"` cierra el atributo `value` y un `<` corta la etiqueta:

```diff
- select.innerHTML += `<option value="${c.id}">${c.nombre_completo || c.nombre || 'Sin nombre'}</option>`;
+ select.innerHTML += `<option value="${esc(c.id)}">${esc(c.nombre_completo || c.nombre || 'Sin nombre')}</option>`;
```

**Ojo especial con SweetAlert2.** `Swal.fire({ html: ... })` **renderiza HTML**, a
diferencia de `text:`. En `cheques.js:355` y `:371` entra texto libre sin escapar:

```diff
      const conf = await Swal.fire({
          title: '¿Registrar el gasto?',
-         html: `Entregaste un cheque de <b>$ ${fmtMoney(cheque.monto)}</b> a <b>${nombre}</b>.<br><br>` +
+         // Swal 'html' renderiza HTML (a diferencia de 'text'): el destinatario
+         // es texto libre y tiene que ir escapado igual que en cualquier innerHTML.
+         html: `Entregaste un cheque de <b>$ ${fmtMoney(cheque.monto)}</b> a <b>${esc(nombre)}</b>.<br><br>` +
                'Si no lo registrás como gasto, los egresos del dashboard van a quedar cortos.',
```

**Defensa en profundidad (recomendado además del escapado):** la CSP de **M-06**.
Con `script-src 'self'`, un `onerror=` inline no se ejecuta aunque se cuele el HTML.

---

## C-03 — CRÍTICO · Cinco librerías desde CDNs externos, sin SRI y sin CSP

**Dónde:** `frontend/index.html:15-20`.

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

**Dos problemas graves, y uno operativo:**

**1. Sin `integrity` (SRI).** Nada verifica que lo que llega sea lo que se espera.
Si jsDelivr o cdnjs se comprometen —o alguien intercepta la conexión en una red
insegura—, se inyecta JavaScript arbitrario **en una aplicación que guarda un token
de admin en `localStorage` y expone `GET /api/backup`**. Es el mismo desenlace de
C-05, pero sin necesidad de tocar la base.

**2. Dos de las URLs no están ancladas a una versión:**
`npm/chart.js`, `npm/sweetalert2@11` y `npm/marked` resuelven a *la última* versión
publicada. **El código que corre en producción puede cambiar de un día para el otro
sin que nadie haya tocado nada**, y con él cualquier cambio de API o regresión.
Ni siquiera hace falta un ataque: alcanza con un release roto río arriba.

**3. Sin internet, la aplicación no funciona.** No es un detalle menor para un
sistema pensado para la PC del taller (empaquetado con PyInstaller):

- sin **SweetAlert2**, cada `Swal.fire(...)` es `ReferenceError` → todos los
  formularios de confirmación quedan mudos;
- sin **html2pdf**, no hay hoja de costos (**M-20**);
- sin **jsPDF/autotable**, no hay informe de trabajos;
- sin **marked**, el manual de usuario no se renderiza;
- sin **Chart.js**, el dashboard queda sin gráficos.

**Solución (recomendada): traer las librerías al repositorio.** Es lo que resuelve
los tres problemas a la vez y es coherente con un sistema que se empaqueta como
`.exe`:

```bash
mkdir -p frontend/vendor
curl -o frontend/vendor/chart.umd.js          https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js
curl -o frontend/vendor/html2pdf.bundle.min.js https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js
curl -o frontend/vendor/sweetalert2.all.min.js https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js
curl -o frontend/vendor/jspdf.umd.min.js       https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js
curl -o frontend/vendor/jspdf.plugin.autotable.min.js https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js
curl -o frontend/vendor/marked.min.js          https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js
```

```diff
  <!-- frontend/index.html -->
- <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
- <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
- <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
- <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
- <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js"></script>
- <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
+ <!-- Servidas desde el propio backend y no desde un CDN, por tres razones:
+      1. El sistema tiene que funcionar sin internet (la PC del taller).
+      2. Un CDN comprometido inyectaría JS en una app con el token de admin en
+         localStorage y con /api/backup a un pedido de distancia.
+      3. "npm/chart.js" y "npm/sweetalert2@11" sin versión fija hacían que el
+         código de producción cambiara solo cuando el paquete publicaba una
+         versión nueva. Las versiones exactas están en frontend/vendor/VERSIONES.md. -->
+ <script src="vendor/chart.umd.js"></script>
+ <script src="vendor/html2pdf.bundle.min.js"></script>
+ <script src="vendor/sweetalert2.all.min.js"></script>
+ <script src="vendor/jspdf.umd.min.js"></script>
+ <script src="vendor/jspdf.plugin.autotable.min.js"></script>
+ <script src="vendor/marked.min.js"></script>
```

`StaticFiles` ya sirve `frontend/`, así que no hace falta tocar el backend. En
`GraficaViamonte.spec`, `frontend/` ya viaja completo en `datas`, así que
`vendor/` entra solo.

**Alternativa mínima si se quiere seguir con CDN:** anclar versión y agregar SRI:

```html
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js"
        integrity="sha384-<hash>" crossorigin="anonymous"></script>
```

…pero eso no resuelve el punto 3 (funcionar sin internet), que para este proyecto
es el que más pesa.

---

## M-22 — MEDIO · El manual se renderiza con `marked` y se inserta como HTML

**Dónde:** `frontend/js/manual.js`.

`GET /api/manual` devuelve el Markdown crudo de `docs/manual_usuario.md` y el
frontend lo pasa por `marked` y lo inserta. **Hoy es seguro**: el archivo lo escribe
el equipo, no un usuario. Se anota porque el día que el manual sea editable desde la
aplicación, se convierte en un vector de XSS inmediato. Si eso llega a pasar,
corresponde `marked` con sanitizador (DOMPurify) o renderizarlo en el backend.

---

## M-23 — MEDIO · Errores de red silenciosos en el login y en varios `cargarX()`

**Dónde:** `frontend/js/app.js:96-98` y ~12 llamadas sueltas a `cargarX()`.

```javascript
} catch(e) {
    console.error("Error en login", e);
}
```

Si el backend está caído, el usuario aprieta "Entrar", el botón vuelve a la
normalidad y **no aparece ningún mensaje**. Queda pensando que tipeó mal la
contraseña.

```diff
      } catch(e) {
          console.error("Error en login", e);
+         Swal.fire('Sin conexión con el sistema',
+                   'No se pudo contactar al servidor. Revisá que el sistema esté encendido.',
+                   'error');
      }
```

El mismo patrón se repite en las llamadas "dispará y olvidate" (`cargarEmpleados()`,
`cargarCheques()`, `cargarDashboard()`, `cargarPlanilla()` sin `await` ni `.catch`,
en `asistencia.js:147,231,268-269,300-301` y `cheques.js:247-248,331-332,411-412`).
Cada una tiene su propio `try/catch` interno que hace `console.error`, así que no
rompen nada — pero un refresco que falla queda invisible y la pantalla muestra datos
viejos como si fueran actuales.

---

## B-14 — BAJO · El interceptor de `fetch` puede filtrar el token a rutas no-API

**Dónde:** `frontend/js/core.js:129`.

```javascript
const esPedidoALaApi = url.startsWith(API_URL);   // API_URL === '/api'
```

`startsWith('/api')` matchea también `/apixyz` o `/api-publico`. Hoy no existe
ninguna ruta así, y todas son del mismo origen, así que no hay filtración real. Se
ajusta con `url === API_URL || url.startsWith(API_URL + '/')`.

Nota adicional: el interceptor asume que `recurso` es un string o tiene `.url`. Si
alguna vez se le pasa un objeto `Request`, el header del spread se ignora en
silencio y ese pedido saldría sin token. Ningún llamador lo hace hoy.

---

## B-15 — BAJO · `abrirPestanaInicial` depende de un selector de atributo frágil

**Dónde:** `frontend/js/app.js:65`.

```javascript
const primeraPropia = document.querySelector('.nav-item[data-tab]:not([style*="none"])');
```

Depende de que `aplicarPermisos()` haya escrito literalmente `display: none` en el
atributo `style`. Un cambio a `classList.add('oculto')` rompe esto sin ningún error.
Es más robusto filtrar con `puedeVerPestana()`, que ya existe y es la fuente de
verdad.

---

## MJ-06 — MEJORA · `index.html` con 1361 líneas y 38 `onclick` inline

El comentario de `core.js:6-10` explica por qué los scripts son clásicos y no
módulos ES: los `onclick` inline necesitan funciones globales. La explicación es
correcta y la decisión, coherente. Pero es la deuda estructural más grande del
frontend: cada función de render es global, cualquier colisión de nombres entre
módulos es silenciosa, y una CSP estricta (**M-06**) rompería los `onclick` inline.

Migrar a `addEventListener` con delegación de eventos permitiría además endurecer
la CSP. Es un refactor grande: se anota como dirección, no como tarea inmediata.

---

## MJ-07 — MEJORA · `style.css` con estilos inline por todos lados

Prácticamente todo el HTML generado lleva `style="..."` embebido. Funciona, pero
duplica la paleta en decenas de lugares y obliga a `'unsafe-inline'` en la CSP de
estilos. Mover los patrones repetidos (badges de estado, botones de acción de tabla)
a clases de `style.css` reduciría el HTML generado a la mitad.

---

---

# FASE 8 — Migraciones, tests y deuda técnica

Archivos revisados: los 11 scripts de `migraciones/`, `migraciones/README.md`, los
12 archivos de `tests/`, y un barrido de `pyflakes` sobre los 60 módulos Python.

## Lo que está bien

- **`migraciones/README.md` es documentación de primer nivel.** Explica por qué las
  migraciones existen (`create_all()` no agrega columnas), en qué orden van, cómo
  correrlas (`python -m`, no `python migraciones/...`) y —lo mejor— **las dos
  trampas de rutas**: el `dirname()` de más y el hecho de que en Railway la base
  vive en el volumen, no en el checkout. Las dos fallan *en silencio* diciendo
  "nada para migrar", y el README lo dice con esas palabras.
- **Cada migración hace un backup fechado antes de tocar nada** y declara si es
  idempotente. `migracion_decimal` avisa explícitamente que **no** lo es.
- **345 tests** repartidos en 12 archivos, con un `conftest.py` que explica por qué
  usa archivo temporal y no `:memory:` (los tests de concurrencia necesitan dos
  sesiones sobre la misma base) y por qué replica el PRAGMA de foreign keys.
- **Hay tests de concurrencia con `threading`** (`test_trabajos.py:291,771`,
  `test_entregas.py:167`). Muy pocos proyectos de este tamaño los tienen.

| Archivo | Tests |
|---|---|
| `test_calculos.py` | 66 |
| `test_trabajos.py` | 59 |
| `test_auditoria.py` | 38 |
| `test_asistencia.py` | 33 |
| `test_presupuestos.py` | 29 |
| `test_schemas.py` | 24 |
| `test_montos.py` | 19 |
| `test_auth.py` | 17 |
| `test_entregas.py` | 17 |
| `test_permisos.py` | 16 |
| `test_stock.py` | 14 |
| `test_arranque.py` | 13 |
| **Total** | **345** |

## A-19 — ALTO · La suite está en rojo

```
1 failed, 414 passed in 222.46s
FAILED tests/test_arranque.py::test_crea_los_tres_puestos_en_una_base_vacia
    AssertionError: {'marcos': 'admin'} != {'marcos': 'encargado'}
```

Causa directa: **A-02** (la promoción hardcodeada en `arranque.py`). Lo anoto aparte
porque el costo va más allá del hallazgo original: **una suite en rojo deja de ser
una señal**. Cuando el próximo cambio rompa algo de verdad, la salida va a seguir
diciendo "1 failed" y nadie va a mirar cuál.

Resolver A-02 pone la suite en verde sin tocar el test.

## A-20 — ALTO · Los tests de concurrencia dan una falsa sensación de cobertura

**Dónde:** `tests/test_trabajos.py:291,753,771`, `tests/test_entregas.py:167`.

Los cuatro tests concurrentes existentes prueban **el doble clic sobre el mismo
recurso**:

- `test_doble_clic_simultaneo_descuenta_una_sola_vez` — dos impresiones del **mismo**
  trabajo;
- `test_doble_clic_simultaneo_no_duplica_numero` — dos entregas del **mismo** pedido;
- `test_doble_submit_concurrente_no_descuadra_la_caja` — dos aplicaciones de saldo
  a favor sobre el **mismo** trabajo.

Los tres pasan, y **con razón**: ése es justamente el caso que los `UPDATE`
condicionales resuelven bien.

Lo que ningún test cubre es **dos recursos distintos compitiendo por el mismo
número correlativo**, que es donde están C-04 y A-13. Por eso el defecto sobrevivió
a una suite que sí piensa en concurrencia: el modelo mental fue "idempotencia del
mismo recurso" y el agujero está en "unicidad entre recursos distintos".

**Tests que faltan** (reproducen exactamente lo que se verificó en la Fase 5):

```python
# tests/test_trabajos.py

class TestNumeracionDeOrdenes:
    """Números de orden únicos entre trabajos DISTINTOS (ver C-04).

    Los tests de doble clic de más arriba cubren el MISMO trabajo impreso dos
    veces, que es lo que resuelve el UPDATE condicional. Éste cubre el otro
    caso: dos trabajos distintos imprimiendo a la vez leen el mismo máximo y se
    llevan el mismo número, y ahí el guard de idempotencia no interviene.
    """

    def test_impresiones_simultaneas_no_repiten_numero(self, client, db):
        import threading

        cliente = crear_cliente(db)
        ids = [crear_trabajo(db, cliente).id for _ in range(10)]

        def imprimir(trabajo_id):
            client.post(f"/api/trabajos/{trabajo_id}/imprimir-orden")

        hilos = [threading.Thread(target=imprimir, args=(i,)) for i in ids]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        numeros = [
            n for (n,) in db.query(models.Trabajo.numero_orden)
            .filter(models.Trabajo.numero_orden.isnot(None)).all()
        ]
        assert len(set(numeros)) == len(numeros), f"números repetidos: {numeros}"


class TestNumeroDeOrdenCorrupto:
    """Un numero_orden con otro formato no debe tumbar la emisión (ver M-16)."""

    def test_no_revienta_con_un_numero_de_otro_formato(self, client, db):
        cliente = crear_cliente(db)
        crear_trabajo(db, cliente, numero_orden="OP-XXXXXX", orden_impresa=True)
        nuevo = crear_trabajo(db, cliente)

        respuesta = client.post(f"/api/trabajos/{nuevo.id}/imprimir-orden")

        assert respuesta.status_code == 200
```

```python
# tests/test_entregas.py

class TestRemitoLegadoConSufijo:
    """El módulo tiene que seguir numerando con un remito legado en la base.

    arranque.py escribe "RE-000001-DUP-xxxxxxxx" al migrar duplicados
    históricos. Con el orden alfabético, ese número ganaba sobre todos los
    demás, el split daba 4 partes y la numeración caía al fallback "RE-000001",
    que ya existía: 409 permanente en todo el módulo (ver C-02).
    """

    def test_emite_remito_con_un_numero_legado_presente(self, client, db):
        cliente = crear_cliente(db)
        trabajo = crear_trabajo(db, cliente, cantidad=100)
        crear_entrega(db, trabajo, numero_remito="RE-000001", cantidad=1)
        db.add(models.Entrega(
            cliente_id=cliente.id,
            numero_remito="RE-000001-DUP-abcd1234",
            fecha=datetime.now(timezone.utc),
        ))
        db.commit()

        respuesta = client.post("/api/entregas", json={
            "cliente_id": cliente.id,
            "items": [{"trabajo_id": trabajo.id, "cantidad": 1}],
        })

        assert respuesta.status_code == 200
```

```python
# tests/test_presupuestos.py

class TestConversionConcurrente:
    """Convertir dos veces a la vez no puede duplicar los trabajos (ver C-01)."""

    def test_conversiones_simultaneas_crean_un_solo_juego_de_trabajos(self, client, db):
        import threading

        cliente = crear_cliente(db)
        presupuesto = crear_presupuesto(db, cliente, items=[
            dict(descripcion="Volantes", cantidad=1000, precio_unitario=Decimal("30")),
        ])

        def convertir():
            client.post(f"/api/presupuestos/{presupuesto.id}/convertir")

        hilos = [threading.Thread(target=convertir) for _ in range(4)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        creados = db.query(models.Trabajo).filter(
            models.Trabajo.descripcion_producto == "Volantes"
        ).count()
        assert creados == 1
```

---

## M-24 — MEDIO · Siete routers no tienen archivo de test propio

Sin `tests/test_<router>.py`: `cheques.py`, `clientes.py`, `empleados.py`,
`gastos.py`, `movimientos.py`, `notas.py`, `reportes.py`.

Parte de su lógica se cubre indirectamente (`test_calculos.py` cubre bien la
matemática que consume `reportes.py`, y `test_permisos.py` toca varios), pero
**ninguno de los cinco endpoints de A-08** —los que devuelven 500 ante una FK
inexistente— vive en un router con test propio. No es casualidad: es exactamente
el hueco de cobertura que dejó pasar esos defectos.

Prioridad sugerida por riesgo: `movimientos.py` (mueve plata y es donde está A-09),
`cheques.py` (FSM, A-11), `gastos.py`.

---

## M-25 — MEDIO · Los tests corren contra versiones distintas de las que se despliegan

Ver **A-01**. Los 345 tests validan Pydantic 2.9.2 y SQLAlchemy 2.0.35; el
`requirements.txt` declara 2.12.4 y 2.0.50. La suite verde no dice nada sobre lo
que va a producción.

---

## M-26 — MEDIO · La suite tarda 3 minutos y 42 segundos

`222.46s` para 345 tests son ~0,64 s por test. La causa es `bcrypt`: cada
`crear_usuario()` del `conftest` hashea de verdad, y el `client` fixture crea uno
por test. Una suite que tarda casi cuatro minutos se corre menos seguido, y una
suite que se corre menos seguido protege menos.

**Solución.** Bajar el coste del hash sólo en los tests:

```python
# tests/conftest.py

@pytest.fixture(autouse=True)
def _bcrypt_rapido(monkeypatch):
    """Baja el coste de bcrypt en los tests.

    El default (12 rondas) es correcto y NO se toca en producción: es lo que hace
    cara la fuerza bruta. Pero acá cada test crea al menos un usuario y eso solo
    explicaba la mayor parte de los 3'42" que tardaba la suite. Con 4 rondas el
    algoritmo es el mismo y los tests siguen probando lo mismo.
    """
    import bcrypt
    original = bcrypt.gensalt
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=4: original(4))
```

Complementario: `pytest -n auto` con `pytest-xdist` (las bases son temporales por
test, así que se paralelizan sin conflicto).

---

## B-16 — BAJO · Imports y variables sin usar

Barrido con `pyflakes` sobre los 60 módulos. Descontando los re-exports
intencionales de `schemas/__init__.py` y `pdf/__init__.py`, queda muy poco:

| Archivo:línea | Qué |
|---|---|
| `routers/clientes.py:3` | `from fastapi import ..., status` — nunca se usa |
| `routers/clientes.py:11` | `import uuid` — nunca se usa |
| `routers/cheques.py:171` | `db_cheque = obtener_o_404(...)` asignado y no usado |

El de `cheques.py:171` **no es un error**: la llamada existe por su efecto (cortar
con 404 si el cheque no existe antes de devolver el historial). Lo que falta es que
se lea así:

```diff
  @router.get("/{cheque_id}/historial", response_model=list[schemas.HistorialChequeResponse])
  def historial_cheque(cheque_id: str, db: Session = Depends(get_db)):
-     db_cheque = obtener_o_404(db, models.Cheque, cheque_id, "Cheque no encontrado")
+     # Por el efecto, no por el valor: sin esto, el historial de un cheque
+     # inexistente devuelve [] en vez de 404.
+     obtener_o_404(db, models.Cheque, cheque_id, "Cheque no encontrado")
```

**Es notable que sea todo.** En 60 módulos y ~7.500 líneas de Python, tres imports
muertos es una tasa de higiene muy buena.

---

## B-17 — BAJO · Los re-exports no declaran `__all__`

`schemas/__init__.py` y `pdf/__init__.py` re-exportan a propósito (el docstring lo
explica), pero sin `__all__` cualquier linter los marca como imports sin usar — 51
falsos positivos que ahogan los 3 hallazgos reales de B-16. Agregar `__all__` (o
`# noqa: F401`) deja el linter utilizable.

---

## MJ-08 — MEJORA · Duplicación de la lógica de migración entre `arranque.py` y `migraciones/`

`_migrar_columna_archivado` y `_migrar_entregas_legado` (`arranque.py`) reimplementan
lo mismo que `migracion_archivo_kanban.py` y `migracion_entregas_parciales.py`. Los
docstrings explican por qué (el servidor no tiene consola) y el README lo documenta,
así que es una **duplicación consciente y justificada**.

Aun así, es duplicación real: **C-02 existe justamente porque el sufijo `-DUP-` vive
en la copia de `arranque.py`**, y quien lea sólo `migraciones/` no se entera de que
ese formato se genera. A futuro conviene que el script de `migraciones/` importe la
función de `arranque.py` en lugar de repetirla, quedando como el envoltorio que
resuelve la ruta de la base y hace el backup.

---

## MJ-09 — MEJORA · No hay un archivo de configuración de linter

No hay `ruff.toml`, `.flake8` ni `pyproject.toml` con reglas. Dado el nivel de
prolijidad del código, agregar `ruff` costaría poco y evitaría que la deuda vuelva
a acumularse:

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]

[tool.ruff.lint.per-file-ignores]
# Re-exports a propósito: ver el docstring de cada uno.
"schemas/__init__.py" = ["F401"]
"pdf/__init__.py" = ["F401"]
```

---

## MJ-10 — MEJORA · `frontend/js/trabajos.js` con 938 líneas

Es el archivo más grande del frontend y mezcla el Kanban, el drawer de alta, el
drawer de la orden de producción, la impresión y las entregas. Partirlo en
`trabajos-tablero.js` / `trabajos-orden.js` / `trabajos-entrega.js` seguiría el
mismo criterio que ya se aplicó con éxito al `schemas.py` monolítico (583 líneas →
14 módulos, según el docstring de `schemas/__init__.py`).

---

## MJ-11 — MEJORA · Documentar la política de respaldos

`/api/backup` existe y funciona, pero no hay nada escrito sobre cada cuánto se
descarga, dónde se guarda ni cuánto se retiene. Con siete `.db` sueltos en la raíz y
en `backups/` (**B-02**), parece que la práctica es "cuando me acuerdo". Media
página en `docs/` (o en el manual de usuario, que ya se sirve dentro del CRM)
cerraría el tema.

---
---

# Plan de acción sugerido

Ordenado por riesgo sobre el negocio, no por esfuerzo.

### Bloque 1 — Antes del próximo deploy

| # | Hallazgo | Por qué primero |
|---|---|---|
| 1 | **C-02** · Remito `-DUP-` | Puede tener el módulo de remitos **ya caído** en producción. Verificar con el `SELECT` de la Fase 5 antes que nada. |
| 2 | **C-04** · Números de orden duplicados | Ocho boletas con el mismo número. Es la identidad del trabajo en el taller. |
| 3 | **C-01** · Conversión duplicada | Factura al cliente dos y tres veces, y el desastre se limpia a mano. |
| 4 | **C-05** · XSS almacenado | 25 puntos; escalada de `mostrador` a `admin`. El arreglo es mecánico: envolver en `esc()`. |
| 5 | **C-03** · CDNs sin SRI | Además, hoy el sistema **no funciona sin internet**. |

### Bloque 2 — Esta semana

| # | Hallazgo |
|---|---|
| 6 | **A-08** + manejador global de `IntegrityError` — elimina cinco 500 de una |
| 7 | **A-09** · Pago imputado a trabajo de otro cliente |
| 8 | **A-02** · Promoción hardcodeada (y con eso, **A-19**: la suite en verde) |
| 9 | **A-03** + **A-04** · Rate limiting y timing del login |
| 10 | **A-10**, **A-11**, **A-12** · Validaciones de estado y de motivo |
| 11 | **A-13**, **A-14**, **A-15**, **A-16** · El resto de las carreras |
| 12 | **A-01** · Alinear `requirements.txt` y volver a correr la suite |

### Bloque 3 — Cuando haya aire

| # | Hallazgo |
|---|---|
| 13 | **A-06** + **A-07** · `selectinload` e índices (el Kanban es la pantalla más usada) |
| 14 | **A-17** + **A-18** · Los dos problemas de la hoja de costos |
| 15 | **A-05** · Revocación de tokens |
| 16 | **M-02** · WAL y `timeout` de SQLite |
| 17 | **M-06** · Cabeceras de seguridad (defensa en profundidad de C-05) |
| 18 | **A-20** + **M-24** · Los tests que faltan |
| 19 | El resto de los MEDIO/BAJO |

---

# Conclusión

Este no es un proyecto con problemas de fondo. Es un proyecto **bien construido** al
que le faltan candados en el borde.

Lo que más llama la atención de la auditoría es que **el proyecto ya sabe** cómo
resolver casi todo lo que encontré. El `UPDATE` condicional de `imprimir_orden` es
el patrón exacto que le falta a `convertir_presupuesto`. El `esc()` de `core.js` es
la función exacta que le falta a esas 25 interpolaciones. El `_validar_estado_cheque`
de `schemas/cheques.py` es el validador exacto que le falta a `trabajos`. El
`unique=True` de `Entrega.numero_remito` es la restricción exacta que le falta a
`numero_orden` y a `numero_secuencia`. El `obtener_o_404` de `routers/trabajos.py` es
la validación exacta que le falta a los cinco endpoints de A-08.

Ese es un diagnóstico mucho mejor que el contrario. No hay que rediseñar nada ni
introducir arquitectura nueva —cosa que, además, la filosofía del proyecto pide
explícitamente evitar—: hay que **terminar de aplicar decisiones que ya se tomaron
bien**, en los lugares donde quedaron a mitad de camino. La mayoría de las
correcciones de este informe son de cinco a veinte líneas, y varias son de una.

Tres cosas merecen mención aparte, porque son mejores que el promedio de lo que se
ve en sistemas de este tipo:

1. **El manejo del dinero.** `Decimal` de punta a punta, `TypeDecorator` propio para
   que el error de float no llegue al disco, y toda la matemática financiera en un
   solo módulo con la política de gastos vs. margen explicada en el encabezado. No
   encontré un solo error de cálculo en `calculos.py`.
2. **Los comentarios.** Explican decisiones, no sintaxis, y casi siempre mencionan
   el bug que vinieron a prevenir. Eso es lo que me permitió auditar el sistema en
   profundidad sin preguntar nada: el "por qué" ya estaba escrito. Es también la
   razón por la que varios hallazgos de este informe pudieron redactarse citando la
   intención original del autor.
3. **La tabla de auditoría.** `cambios()` leyendo el historial de atributos de
   SQLAlchemy, con la precondición documentada, es una solución elegante a un
   problema que la mayoría resuelve copiando el objeto veinte veces.

El riesgo real hoy está concentrado y es acotable: **la numeración de comprobantes,
el escapado del frontend y tres validaciones de concurrencia**. Cerrado el Bloque 1,
este CRM queda en muy buena forma para seguir creciendo.

---

## Anexo — Metodología y reproducibilidad

**Qué se hizo:**

1. Lectura completa de los 60 módulos Python, los 13 módulos JavaScript,
   `index.html`, `style.css`, las 11 migraciones y toda la configuración.
2. Levantar `main.app` real contra bases SQLite temporales y disparar 18 payloads
   de borde (`NaN`, `Infinity`, `1e500`, nulls explícitos, FKs inexistentes,
   estados inválidos, cantidades negativas, comodines SQL).
3. Cinco escenarios de concurrencia con `threading` sobre la aplicación real:
   impresión de órdenes, alta de presupuestos, entregas, alta de clientes y ajustes
   de stock.
4. Instrumentación del engine de SQLAlchemy con `before_cursor_execute` para contar
   consultas por request (N+1).
5. Ejecución completa de la suite (`pytest`) y análisis de su cobertura.
6. Barrido con `pyflakes` sobre todo el árbol Python.
7. Análisis de los 65 usos de `innerHTML` del frontend, cruzando cada interpolación
   contra `esc()` y contra el origen del dato.

**Qué NO se hizo:**

- No se modificó ningún archivo del proyecto. El único agregado es este informe.
- No se tocó `viamonte.db` ni ninguno de los respaldos.
- Las únicas dependencias instaladas fueron `pyflakes` (análisis estático), en el
  entorno, no en el proyecto: `requirements.txt` y `requirements-dev.txt` quedaron
  intactos.

**Cómo reproducir los hallazgos de concurrencia.** Cada uno está descrito con el
escenario exacto (cuántos hilos, sobre qué recurso, con qué payload) en su sección.
Los tests propuestos en **A-20** son la versión permanente de esas mismas pruebas.

---

*Fin del informe.*

