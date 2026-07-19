# Auditoría integral — julio 2026

Plan de trabajo derivado de la auditoría post-refactor de los 4 módulos
(Presupuestos, Órdenes de Producción, Stock/Kg, Finanzas). Cada archivo es un
documento de trabajo autocontenido (problema, referencias archivo:línea,
escenario de fallo, solución propuesta y checklist) pensado para resolverse
en orden, uno por sesión.

| # | Archivo | Contenido | Gravedad |
|---|---------|-----------|----------|
| 1 | [01-conversion-presupuesto-y-saldo-unificado.md](01-conversion-presupuesto-y-saldo-unificado.md) | C1 conversión transaccional + C4 saldo de cliente unificado | Crítico |
| 2 | [02-aritmetica-strings-frontend.md](02-aritmetica-strings-frontend.md) | C2 suma de pagos NaN + C3 alerta de stock lexicográfica | Crítico |
| 3 | [03-cheques-v2.md](03-cheques-v2.md) | I1 trabajo_id, I2 historial+estados, I3 Emitidos/Endosados (+I4, I5) | Importante |
| 4 | [04-politica-gastos-vs-margen.md](04-politica-gastos-vs-margen.md) | I10 doble descuento, I11 margen congelado, I12 desfase caja (+I9) — **arranca con decisión de negocio** | Importante |
| 5 | [05-stock-y-menores.md](05-stock-y-menores.md) | I6-I8 stock + todos los menores + notas de seguridad | Importante/Menor |

Contexto técnico transversal: **Pydantic v2 serializa `Decimal` como string JSON**
— todo monto que llega al frontend es string; cualquier aritmética en JS debe
pasar por `Number(...)`. Ver detalle en el archivo 02.
