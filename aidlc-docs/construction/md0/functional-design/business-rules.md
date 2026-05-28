# Business Rules — MD0 Dashboard Web Interno

Reglas que el frontend DEBE garantizar. Cada una tiene un identificador `BR-MD0-NN` para trazabilidad en tests de UI.

---

## Reglas de seguridad

### BR-MD0-01 — Credenciales nunca en cliente
El dashboard **NUNCA** debe almacenar, transmitir, recibir ni mostrar valores reales de credenciales (`env_access_credentials.username/password`, `shopper.email/password`). Solo gestiona paths de Secrets Manager como strings.

**Verificación:** inspección DevTools Network — ningún response payload debe contener campos con keys `password`, `secret`, `token`, `apiKey` (excepto el header `X-API-Key` del cliente al backend, que es la única credencial que vive en cliente).

**Impacto si se rompe:** SECURITY-01 violado, exposición de credenciales de tienda en logs del browser, console, history, cache HTTP.

---

### BR-MD0-02 — API key del dashboard al backend
El dashboard envía `X-API-Key: ${API_KEY}` en cada request al backend. El valor se obtiene de:
- **MVP:** prompt al usuario al primer acceso → guardado en `sessionStorage` (no `localStorage` — se borra al cerrar tab).
- **Post-MVP:** SSO corporativo.

**Verificación:** sin API key configurada, todas las pantallas muestran modal de "Configurar API key" antes de cualquier fetch.

---

### BR-MD0-03 — No exponer paths de Secrets en logs cliente
Los paths como `testpilot/staging/env-access` son metadata, no secretos — pero por defensa en profundidad, no se loggean en `console.log` ni se incluyen en URLs visibles del browser (deben ir en body del POST, no en query string).

---

## Reglas de validación de inputs

### BR-MD0-04 — Validación de `environment_id`
`environment_id` debe matchear regex `^[a-z][a-z0-9_-]{2,31}$` (solo lowercase, alfanumérico+guiones, 3-32 chars, empieza con letra). Validación inmediata en frontend antes de submit.

### BR-MD0-05 — Validación de `store_url`
`store_url` debe ser HTTPS válido (`^https://[a-z0-9.-]+(/.*)?$`). HTTP plano se rechaza con mensaje explícito: *"Se requiere HTTPS para proteger la sesión del shopper."*

### BR-MD0-06 — Validación de paths de Secrets
Los paths deben matchear `^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$`. Esto evita typos comunes y previene path traversal si el backend hiciera resolución dinámica (aunque no debería).

### BR-MD0-07 — Validación de payload de run
Antes de submit en P2:
- ≥1 producto
- ≥1 flow seleccionado
- ≥1 perfil seleccionado
- Ambiente seleccionado y `active=true`
- `screenshot_on_error` debe ser `true` (no editable — invariante de auditoría)

---

## Reglas de visualización

### BR-MD0-08 — Semáforo destacado en P4
El semáforo (verde/amarillo/rojo) debe ser el primer elemento visible al cargar P4, con tamaño mínimo 96px de alto. No puede estar oculto detrás de tabs ni colapsado.

### BR-MD0-09 — Banner "orders_created: 0" siempre visible
En P4 y en P3 (al finalizar), el banner debe mostrar el contador. Si fuera distinto de 0, debe convertirse en banner ROJO bloqueante con mensaje *"⚠️ INCIDENTE: orden real creada — abrir ticket inmediato"*.

### BR-MD0-10 — Indicador de modo bootstrap
Cuando `bootstrap_mode=true`, todo run muestra un badge azul *"Aprendizaje (X/14)"* en P3, P4 y P5. Las alertas amarillas se renderizan como neutrales (gris) hasta salir de bootstrap.

### BR-MD0-11 — Polling solo cuando hay run activo
P3 hace polling cada 3 s solo mientras `state != "completed" && state != "failed"`. Detiene polling al detectar terminal state. Si usuario navega fuera de P3, polling se cancela (cleanup en componente).

---

## Reglas de manejo de errores

### BR-MD0-12 — 401 desde backend
Si cualquier fetch retorna 401, el dashboard descarta la API key de `sessionStorage`, muestra modal "API key inválida o expirada", y redirige a primera carga.

### BR-MD0-13 — 5xx desde backend
Errores 500/502/503 muestran banner rojo no-bloqueante con mensaje *"Backend no disponible — reintentar"* y botón de reintento. No se reintenta automáticamente para evitar amplificar la carga si el backend está caído.

### BR-MD0-14 — Run timeout en P3
Si polling no detecta finalización tras `2 × max_run_duration` (configurable, default 30 min), banner advierte *"Run tomando más tiempo de lo esperado — revisar logs"* y permite navegación manual a P4.

---

## Reglas de persistencia local

### BR-MD0-15 — No persistir runs en cliente
El dashboard NO cachea reportes completos en `localStorage`. Todo dato viene del backend en cada carga (con cache HTTP estándar de 60 s para responses GET de runs terminados — son inmutables).

### BR-MD0-16 — Configuración de filtros en URL
Los filtros de P5 (fecha, ambiente, semáforo, flow) se reflejan en query string de la URL. Permite compartir vistas filtradas vía link (auditoría) y restaurar al refrescar.

---

## Reglas de accesibilidad

### BR-MD0-17 — Contraste de semáforos
Los chips de semáforo deben cumplir WCAG 2.1 AA (contraste ≥4.5:1). Además del color, usan texto explícito ("OK", "Alerta", "Fallo") y/o iconos diferenciables para usuarios daltónicos.

### BR-MD0-18 — Navegación por teclado
P1 (formulario de ambientes) y P2 (formulario de run) deben ser navegables completamente con Tab/Enter sin mouse. Foco visible en cada control.

---

## Trazabilidad a Security Baseline

| Regla MD0 | Security Baseline rule |
|---|---|
| BR-MD0-01, BR-MD0-03 | SECURITY-01 (No secrets in code/client) |
| BR-MD0-02, BR-MD0-12 | SECURITY-05 (Auth en cada request) |
| BR-MD0-04, BR-MD0-05, BR-MD0-06, BR-MD0-07 | SECURITY-03 (Input validation) |
| BR-MD0-13 | SECURITY-15 (Error handling — no detalles sensibles al cliente) |
| BR-MD0-15 | SECURITY-10 (No persistir info sensible local) |
