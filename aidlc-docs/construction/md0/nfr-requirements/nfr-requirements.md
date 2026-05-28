# NFR Requirements — MD0 Dashboard Web Interno

## Performance

### NFR-MD0-P1 — Tiempo de carga inicial
La primera pantalla útil (P1 o P5 según deep-link) debe renderizar en **< 2 s** en LAN corporativa con backend respondiendo en <100ms. Métrica: Largest Contentful Paint (LCP).

**Razón:** internal tool, usuarios técnicos, expectativa de velocidad alta — un dashboard lento desincentiva uso y empuja al equipo a usar `curl` directo.

### NFR-MD0-P2 — Polling P3
Polling de `/v1/runs/{id}/status` cada **3 s ± 500 ms** (jitter para evitar thundering herd si N usuarios miran el mismo run). Detener polling al recibir estado terminal o al desmontar componente.

### NFR-MD0-P3 — Payload de historial
La response de `GET /v1/runs?page=1` debe procesarse y renderizar tabla en **< 500 ms** para `page_size=25`. Server-side paginación obligatoria — no devolver >100 runs en una sola respuesta (responsabilidad de U4 backend).

### NFR-MD0-P4 — Lazy load de screenshots
Las miniaturas en P4 se cargan **on-demand al entrar al viewport** (IntersectionObserver), no upfront. La galería completa puede tener 30–90 imágenes (5 perfiles × 6-10 pasos × 2 estados); cargar todas upfront mata el rendering inicial.

---

## Security

### NFR-MD0-S1 — SECURITY-01: No credentials en código cliente
Ninguna credencial real (env_access, shopper, AWS keys) debe aparecer en bundle JS, source maps, ni en variables de configuración hardcodeadas. Solo el `X-API-Key` del usuario, vivo en `sessionStorage`.

**Verificación:** scan de bundle JS con `truffleHog` o equivalente en CI antes de deploy del dashboard.

### NFR-MD0-S2 — SECURITY-03: Input validation cliente + servidor
Toda validación en frontend (BR-MD0-04 a BR-MD0-07) es **UX** — la validación autoritativa vive en el backend (Pydantic). El frontend NUNCA confía en sus propias validaciones para decisiones de seguridad.

### NFR-MD0-S3 — SECURITY-05: API key en cada request
Todos los fetch al backend incluyen `X-API-Key` header. Sin excepciones (ni siquiera `/health` si existiera).

### NFR-MD0-S4 — SECURITY-09: Sin stack traces al usuario
Si el backend retorna 500, el dashboard muestra mensaje genérico ("Backend no disponible"). NO renderiza el body de la response — puede contener detalles internos. Solo el `error_code` se loggea en console para debugging del desarrollador.

### NFR-MD0-S5 — SECURITY-10: No persistir info sensible
`localStorage` está prohibido para cualquier dato del backend (BR-MD0-15). `sessionStorage` solo para `X-API-Key`. Cache HTTP estándar (60s) está OK para responses GET inmutables (reportes terminados).

### NFR-MD0-S6 — CSP estricto
El dashboard sirve con header `Content-Security-Policy: default-src 'self'; img-src 'self' data: https://*.s3.amazonaws.com; script-src 'self'; style-src 'self' 'unsafe-inline'`. Bloquea inyección de scripts externos y limita orígenes de imágenes (screenshots S3).

### NFR-MD0-S7 — XSS en renderizado de reportes
`error` (string libre) en `StepResult` puede contener input controlado por la tienda (mensajes de error del SFCC). Renderizar con escape automático del framework (React `{}`, Vue `{{}}`). NUNCA usar `dangerouslySetInnerHTML`.

---

## Reliability

### NFR-MD0-R1 — Manejo de desconexión durante polling
Si el polling de P3 falla 3 veces consecutivas (network error o timeout), pausar polling, mostrar banner *"Conexión interrumpida — reintentando en 30 s"*, reintentar 1 vez tras 30 s. Si vuelve a fallar, banner permanente con botón manual de reintento.

### NFR-MD0-R2 — Idempotencia de submit
El botón "Lanzar Run" en P2 se deshabilita inmediatamente al click hasta recibir response o error. Previene runs duplicados por doble-click.

### NFR-MD0-R3 — Estado consistente tras error
Si una edición de ambiente en P1 falla, el formulario mantiene los valores ingresados (no se limpia). Permite reintento sin re-tipear.

---

## Usability / Accesibilidad

### NFR-MD0-U1 — Navegación por teclado completa (WCAG 2.1 AA)
Tab/Shift+Tab navega controles en orden lógico. Enter submite formularios. Esc cierra modales. Foco visible siempre.

### NFR-MD0-U2 — Contraste WCAG AA
Texto sobre fondo ≥4.5:1 en todos los componentes. Semáforos cumplen además con triple codificación (color + texto + ícono) — BR-MD0-17.

### NFR-MD0-U3 — Browsers soportados
Chrome ≥120, Firefox ≥120, Edge ≥120. NO soporte explícito para Safari o IE/legacy (uso interno, equipo controla su stack).

### NFR-MD0-U4 — Responsive básico
Dashboard usable en pantallas ≥1280×800. Mobile NO es target (es herramienta de desk work). Mínimo: no se rompe el layout, pero tablas pueden requerir scroll horizontal.

---

## Maintainability

### NFR-MD0-M1 — Sin estado global complejo
Para MVP, sin Redux/Zustand/MobX. Estado local por pantalla con hooks/composables. Justificación: 5 pantallas independientes con poca data compartida — overhead de state mgmt no aporta valor.

### NFR-MD0-M2 — Sin tests E2E en MVP del dashboard
Los tests E2E del flujo completo viven en el sistema general (U1 ya cubre Playwright). El dashboard solo tiene **unit tests de componentes** (validación de formularios, renderizado de semáforo) — esto baja el costo de mantenimiento al cambiar UI.

### NFR-MD0-M3 — Versionado de cliente
Cada build del dashboard se etiqueta con commit SHA visible en el footer. Permite correlacionar bugs reportados con versión exacta.

---

## Observability

### NFR-MD0-O1 — Console logs estructurados
Errores de fetch se loggean con: `console.error({ endpoint, method, status, error_code })`. No `console.log` libres en código de producción (lint rule).

### NFR-MD0-O2 — Sin tracking de usuario
No se incluye Google Analytics, Hotjar, Sentry-de-producción ni similares en MVP. Si se necesita observabilidad post-MVP, debe revisarse con compliance interno antes (es internal tool, no producto público).

---

## Aplicabilidad Security Baseline a MD0

| Regla SB | Aplica | Implementación en MD0 |
|---|---|---|
| SECURITY-01 No secrets in code | ✅ | NFR-MD0-S1: scan en CI |
| SECURITY-02 Env vars para secrets | ✅ | API key en sessionStorage; valores Secrets resueltos en backend |
| SECURITY-03 Input validation | ✅ | NFR-MD0-S2: BR-MD0-04 a BR-MD0-07 |
| SECURITY-04 SQL injection | N/A | Sin SQL en frontend |
| SECURITY-05 Auth en cada request | ✅ | NFR-MD0-S3 |
| SECURITY-06 Authorization | N/A | Sin RBAC en MVP; API key da acceso total |
| SECURITY-07 Crypto | N/A | TLS handled by browser/backend |
| SECURITY-08 Dependencias auditadas | ✅ | `npm audit` o `pnpm audit` en CI |
| SECURITY-09 Sin stack traces | ✅ | NFR-MD0-S4 |
| SECURITY-10 No log de sensitive data | ✅ | NFR-MD0-O1: solo error_code, no body |
| SECURITY-11 Rate limiting | N/A | Aplica al backend, no al cliente |
| SECURITY-12 Container images | N/A | Sin contenedores en MD0 si se sirve estático |
| SECURITY-13 Non-root containers | N/A | Idem |
| SECURITY-14 Network policies | N/A | Idem |
| SECURITY-15 Error handling seguro | ✅ | NFR-MD0-S4 |

**Resumen:** 9/15 reglas aplican y se cumplen. 6/15 son N/A por la naturaleza frontend-only (sin DB, sin contenedores propios, sin lógica de auth/authz delegada al backend).

---

## Aplicabilidad PBT a MD0

PBT (Property-Based Testing) NO aplica al frontend del dashboard porque:
- No hay funciones puras de cálculo crítico (el cálculo de p95 vive en U2 backend)
- Los tests de componente UI son mejor cubiertos por React Testing Library / equivalent con casos específicos
- El costo/beneficio de hypothesis-style testing en UI es bajo

**Decisión documentada:** PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 → **N/A para MD0**, todas aplican a U2/U3 backend.
