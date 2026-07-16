Revisá el archivo `frontend/app.js`. Buscá todos los botones que ejecuten peticiones `fetch`.
Implementá el patrón "Disable-on-submit":
1. Al hacer click, deshabilitá el botón inmediatamente (`button.disabled = true`).
2. Cambiá el texto del botón a "Procesando...".
3. En el bloque `finally` del fetch o promesa, volvé a habilitar el botón y devolvele su texto original.
Proponé los cambios antes de escribirlos.