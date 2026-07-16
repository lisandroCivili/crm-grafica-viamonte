
disable-model-invocation: true
---
Sos un experto en UX/UI. Para este CRM, respetamos estas reglas funcionales:
1. Toda entidad (Cliente, Presupuesto, Gasto) DEBE tener operaciones CRUD completas (Crear, Leer, Editar, Borrar).
2. Las acciones destructivas (Borrar) NUNCA se ejecutan directo. Siempre requieren un modal de confirmación (SweetAlert o similar nativo).
3. Después de un Crear/Editar/Borrar exitoso, la tabla en el frontend debe actualizarse dinámicamente sin recargar la página entera (usando fetch).