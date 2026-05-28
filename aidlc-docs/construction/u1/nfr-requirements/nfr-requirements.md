# NFR Requirements — U1 Executor Playwright (actualizado 2026-05-24)

## Performance (RNF-07)

### NFR-P1: Sin timeouts hardcodeados
Todos los timeouts derivan de env vars (`STEP_TIMEOUT_MS`, `NAVIGATION_TIMEOUT_MS`). `browser_context.set_default_timeout()` aplica en cada context. Sin literales numéricos en flows.

### NFR-P2: Sin time.sleep()
Prohibido `time.sleep()` y `asyncio.sleep()` en cualquier archivo de U1. Excepción: `auth/shopper_login.py` puede usar `asyncio.sleep(0)` para yield del event loop si se requiere — pero debe documentarse el "por qué".

### NFR-P3: Duración por paso en milisegundos
`StepResult.duration_ms` medido con `time.monotonic()` (no wall clock). Permite detectar regresiones de performance por paso individual.

### NFR-P4: Paralelización a nivel perfil
3 perfiles ejecutándose en paralelo en el mismo proceso vía `asyncio.gather`. `MAX_CONCURRENT_PROFILES=3` por env var. Cada perfil = browser independiente.

### NFR-P5: Tiempo total objetivo
Un run completo (3 perfiles × 2 flows × 10 pasos) debe terminar en **< 12 min** en condiciones normales. Si supera 30 min, el watchdog en U4 cancela.

---

## Security

### NFR-S1: SECURITY-01 — No secrets in code
Credenciales (env_access, shopper) viajan en memoria como instancias Pydantic frozen. NUNCA en logs, NUNCA escritos a disco, NUNCA serializados como strings completos.

### NFR-S2: SECURITY-03 — Input validation
- `env.shopper.email.endswith("@testpilot.internal")` validado por assertion al inicio (BR-U1-03).
- `env.config.store_url` ya validado por Pydantic en U0 (HttpUrl + https-only).
- No interpolar `store_url` en queries SQL ni otros sistemas (N/A aquí).

### NFR-S3: SECURITY-09/15 — Error handling seguro
Los errores de Playwright no exponen rutas internas del sistema. `StepResult.error = str(e)` — solo el mensaje, nunca `traceback.format_exc()`. `InfrastructureError` se propaga hasta runner, que la convierte en status="error" sin exponer detalles.

### NFR-S4: SECURITY-10 — No log secrets
- No loggear `env.shopper.email` a nivel DEBUG sin redacción.
- No loggear `env.env_access.username` sin redacción (aunque el username no es tan sensible, política de redacción uniforme).
- `__str__` de las clases credenciales redacta automáticamente passwords (BR-U0-03).
- Logs estructurados usan `RedactingJsonFormatter` (D-U0-06) — cualquier campo con key `password`, `secret`, `token` se reemplaza con `***REDACTED***`.

### NFR-S5: SECURITY-14 — Network isolation
El executor SOLO hace requests a `env.config.store_url` y dominios servidos por el storefront (CDN, assets). NO debe contactar dominios externos arbitrarios. **Implementación:** middleware de Playwright que bloquea requests fuera de un allowlist:
```python
context.route("**/*", lambda route: 
    route.continue_() if is_allowed(route.request.url, allowed_domains)
    else route.abort()
)
```
**MVP:** allowlist permisivo (mismo dominio + CDN comunes de SFCC). Refinar en sprint 3+.

---

## Reliability

### NFR-R1: Distinción infra vs app error
Implementado por BR-U1-08. Tests dedicados verifican cada categoría.

### NFR-R2: Cierre del browser en cualquier caso
`browser.close()` en bloque `finally` del runner. Si el flow falla en cualquier step, el browser cierra correctamente — previene leaks de procesos zombi en ECS.

### NFR-R3: Invariante orders_created
`assert flow_result.orders_created == 0` antes de retornar `ProfileResult`. Violación = `InfrastructureError` con mensaje explícito.

### NFR-R4: Browser context aislado por perfil
Cada perfil usa su propio `BrowserContext` — sin cookies, storage, ni cache compartido entre perfiles. Garantiza que un perfil no contamine otro.

---

## Aplicabilidad Security Baseline a U1

| Regla | Aplica | Implementación |
|---|---|---|
| SECURITY-01 | ✅ | Credenciales solo en memoria, nunca en código (NFR-S1) |
| SECURITY-02 | ✅ | env_access/shopper vienen de Secrets Manager (resuelto en U4, consumido en U1) |
| SECURITY-03 | ✅ | NFR-S2 (assertions + Pydantic) |
| SECURITY-04 | N/A | No hay SQL en U1 |
| SECURITY-05 | N/A | U4 maneja auth de API |
| SECURITY-06 | N/A | No hay RBAC en MVP |
| SECURITY-07 | ✅ | env.config.store_url forzado a HTTPS por Pydantic |
| SECURITY-08 | ✅ | Sin dependencias nuevas en U1 — boto3/playwright auditados en U0 |
| SECURITY-09 | ✅ | NFR-S3 |
| SECURITY-10 | ✅ | NFR-S4 (no log de credenciales) |
| SECURITY-11 | N/A | Rate limiting en U4 |
| SECURITY-12 | N/A | Imagen Docker en U0 |
| SECURITY-13 | N/A | Idem U0 |
| SECURITY-14 | ✅ | NFR-S5 (network allowlist) |
| SECURITY-15 | ✅ | NFR-S3 |

**Resumen U1:** 10/15 aplican y se cumplen. 5/15 son N/A — corresponden a U0/U4.

---

## Aplicabilidad PBT a U1

PBT aplica de forma limitada a U1:
- **PBT-07 (test de timing):** ✅ propiedad "duration_ms ≥ 0 para cualquier step OK o failed". Test en `tests/test_executor_pbt.py`.
- **PBT-08 (round-trip):** N/A (se cubre en U0).
- **PBT-02, PBT-03, PBT-09:** N/A (aplican a U2 baseline).

---

## Performance budgets por paso (para baseline U2)

Documentados aquí para que U2 sepa qué thresholds esperar. Son **valores típicos**, no SLAs estrictos — el baseline real lo calcula U2 a partir de runs reales.

| Step | Budget esperado (ms) | Comentario |
|---|---|---|
| env_access_auth | ~1500 | HTTP Basic + first paint |
| shopper_login | ~3000 | Form submit + redirect + my-account check |
| search_product | ~2000 | Query + render results |
| category_page | ~1500 | Wait for tiles |
| pdp_variant_select | ~2500 | Click + AJAX variant load |
| add_to_cart | ~2000 | Click + minicart open |
| mini_cart_validation | ~500 | Lectura de DOM |
| checkout_shipping | ~3000 | Fill 7 fields + validation + continue |
| checkout_payment | ~3000 | Fill 4 fields + tokenize |
| payment_failure_validation | ~3000 | Wait for error message |
| **Total checkout-full** | **~22 s** | Sin red lenta |

Bootstrap real: 14 runs determinan el p95 efectivo (U2 BR).
