# CRM Gráfica Viamonte

## Objetivo del proyecto

Este proyecto es un CRM desarrollado específicamente para administrar el funcionamiento interno de una gráfica.
Su objetivo NO es solamente almacenar información.
Debe ayudar a administrar:

* Clientes
* Presupuestos
* Trabajos
* Producción
* Pagos
* Movimientos
* Gastos
* Stock
* Cheques
* Historial
El objetivo principal es reducir trabajo manual, mantener trazabilidad y permitir escalar el negocio.

---

# Stack Tecnológico

Backend

* FastAPI
* SQLAlchemy
* Pydantic v2
* SQLite (actualmente)
Frontend
* HTML
* CSS
* JavaScript
Lenguaje
* Python 3

---

# Filosofía del proyecto

La prioridad es la simplicidad.
No introducir arquitectura compleja sin necesidad.
Antes de crear nuevas capas o patrones verificar si realmente aportan valor.
Se privilegia:

* claridad
* mantenibilidad
* consistencia
por encima de la optimización prematura.

---

# Arquitectura actual

Actualmente el proyecto utiliza:
routers/
models.py
schemas.py
database.py
main.py
No existe una carpeta services.
Mientras no exista:

* la lógica pequeña puede vivir en routers
* la lógica mediana puede extraerse a funciones privadas
* si una lógica comienza a crecer demasiado, sugerir moverla a una futura carpeta services, pero NO crearla automáticamente.

---

# Forma correcta de pensar

## SIEMPRE seguir este orden.
1.
Entender el problema.
2.
Entender el módulo afectado.
3.
Leer el modelo SQLAlchemy.
4.
Leer el schema Pydantic.
5.
Leer el router.
6.
Buscar código similar.
7.
Recién después escribir código.
Nunca implementar una solución sin conocer cómo está hecho el resto del sistema.

# Objetivo antes de escribir código

El objetivo NO es solamente que funcione.
Debe además:

* ser consistente
* ser legible
* seguir el estilo existente
* evitar duplicación
* respetar la arquitectura

---

# Principios

## Preferir reutilizar antes que crear.
Preferir funciones pequeñas.
Preferir nombres descriptivos.
Evitar funciones enormes.
Evitar repetir lógica.
No agregar dependencias innecesarias.

# Modelos

Todos los modelos usan UUID.
Nunca reemplazar UUID por enteros.
Las relaciones entre entidades son importantes.
Antes de modificar un modelo revisar:

* Foreign Keys
* relationships
* impacto sobre schemas
* impacto sobre routers

---

# Schemas

## Todos los cambios realizados sobre modelos deben analizar si afectan:
Create
Update
Response
Nunca modificar únicamente el modelo.

# Routers

## Los routers representan la API pública.
No romper endpoints existentes.
No cambiar nombres de rutas sin motivo.
Mantener respuestas consistentes.
Usar siempre:
HTTPException
status codes adecuados
typing

# Convenciones FastAPI

## Siempre utilizar:
APIRouter
Depends
Response Models
Typing
Status Codes
Evitar lógica enorme dentro de endpoints.

# Convenciones SQLAlchemy

## Antes de hacer consultas:
Pensar si existe riesgo de:
N+1 Queries
joins innecesarios
consultas repetidas
objetos huérfanos
Mantener relaciones consistentes.

# Convenciones Pydantic

## Usar model_config.
No duplicar schemas.
Si aparece un schema repetido sugerir unificarlo.
Mantener Create, Update y Response separados.

# Entidades principales

## Cliente
Representa una persona o empresa.
Puede tener:
Trabajos
Movimientos
Presupuestos
Cheques
Notas

## Trabajo
Representa una orden de producción.
Debe mantener:
estado
precio
materiales
pagos
notas

## Movimiento
Representa movimientos económicos.
Debe ser auditable.
No eliminar movimientos históricos.

## Presupuesto
Puede:
crearse
duplicarse
aprobarse
rechazarse
convertirse en Trabajo

## Stock
Debe mantener historial.
Nunca modificar cantidades sin registrar motivo.

## Cheque
Puede pasar por distintos estados.
Nunca perder historial del cambio.

## Gasto
Puede estar asociado a un Trabajo.
Debe afectar reportes futuros.

# Reglas generales

## Nunca romper compatibilidad.
Nunca eliminar campos sin analizar impacto.
Nunca cambiar nombres públicos.
No eliminar endpoints.
No cambiar respuestas JSON sin necesidad.

# Al crear una nueva feature

## Preguntarse:
¿Qué entidades participan?
¿Qué routers participan?
¿Qué schemas participan?
¿Qué relaciones cambian?
¿Qué validaciones nuevas aparecen?
¿Debe actualizar documentación?

# Al modificar código existente

## Antes de tocar cualquier archivo:
Buscar referencias.
Buscar imports.
Buscar routers relacionados.
Buscar schemas relacionados.
Buscar relaciones SQLAlchemy.

# Qué evitar

## No reescribir archivos completos.
No cambiar estilo del proyecto.
No introducir patrones nuevos sin justificar.
No agregar dependencias por comodidad.
No optimizar código que aún no representa un problema.

# Cuando existan varias soluciones

## Elegir la que:
Sea más simple.
Sea consistente con el proyecto.
Sea fácil de mantener.

# Código

## Priorizar:
claridad
legibilidad
consistencia
antes que "código inteligente".

# Si detectás deuda técnica

No modificar automáticamente.
Primero informar:

* problema
* impacto
* propuesta
* ventajas
* desventajas
Luego esperar aprobación.

---

# Documentación

## Cuando se cree una nueva entidad:
Actualizar docs correspondientes.
Cuando cambie una regla de negocio:
Actualizar documentación.

# Objetivo final

Todo cambio realizado debe dejar el proyecto:
Más consistente.
Más mantenible.
Más claro.
Nunca solamente "funcionando".