"""Scripts de migración de la base, ordenados cronológicamente en el README.

Existe para que las migraciones se puedan correr como módulo desde la raíz del
proyecto (`python -m migraciones.migracion_X`). Esa forma de invocación deja la
raíz en sys.path, que es lo que necesita migracion_decimal para resolver sus
imports de `money`, `models` y `database`.
"""
