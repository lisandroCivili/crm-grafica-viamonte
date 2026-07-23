# Migraciones

Scripts que llevan una base `viamonte.db` ya existente al esquema actual.

Hacen falta porque `models.Base.metadata.create_all()` (en `main.py`) **solo crea
tablas que no existen**: no agrega columnas a una tabla ya creada. Una base con
datos reales del taller necesita el `ALTER TABLE` a mano.

## Cómo correrlas

Con el backend apagado y **desde la raíz del proyecto**, como módulo:

```
python -m migraciones.migracion_stock_pliegos
```

La forma `python migraciones/migracion_X.py` **no sirve**: deja la raíz fuera de
`sys.path` y `migracion_decimal` no puede resolver `money`, `models` ni `database`.

Cada script hace un backup fechado de `viamonte.db` antes de tocar nada, y todos
son idempotentes salvo donde se aclare: correrlos dos veces no rompe.

## Orden cronológico

| # | Script | Fecha | Qué hace |
|---|---|---|---|
| 1 | `migracion_decimal` | 2026-07-16 | Recrea las tablas para que el dinero se guarde como TEXT y no como REAL. **No es idempotente**: se corre una sola vez. |
| 2 | `migracion_modulo4_finanzas` | 2026-07-17 | Columnas nuevas de `cheques` y `gastos`. |
| 3 | `migracion_orden_produccion` | 2026-07-17 | Campos de la boleta física en `trabajos`. |
| 4 | `migracion_presupuesto_flexible` | 2026-07-17 | `presupuestos.cliente_id` pasa a nullable (borradores sin cliente) + `material` y `gramaje`. Recrea la tabla: SQLite no saca un NOT NULL con ALTER. |
| 5 | `migracion_stock_pliegos` | 2026-07-17 | `largo_cm`, `ancho_cm` y `gramaje_grs` en `stock`. |
| 6 | `migracion_cheques_v2` | 2026-07-20 | Clasificación de cheques y tabla `historial_cheques`. |
| 7 | `migracion_devolucion_papel` | 2026-07-20 | `trabajos.papel_devuelto`, para el reingreso de pliegos al cancelar. |
| 8 | `migracion_papel_presupuesto` | 2026-07-21 | El papel viaja del presupuesto al trabajo (`papel_id`, `cantidad_pliegos`). |

Las cuatro del 2026-07-17 entraron en el mismo commit; entre ellas el orden es
indistinto (tocan tablas distintas).

## Nota sobre las rutas

Estos scripts viven en `migraciones/` pero la base está en la raíz, así que cada
uno calcula:

```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

El `dirname()` de más no es decorativo. Sin él, `DB_PATH` apunta a
`migraciones/viamonte.db`, que no existe, y el script sale diciendo *"No existe
viamonte.db, nada para migrar"* sin haber tocado la base real — falla en silencio
aparentando que funcionó.
