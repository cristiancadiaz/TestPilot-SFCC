# Business Rules — U1 Executor Playwright (actualizado 2026-05-24)

## Reglas de ejecución de flows

### BR-U1-01: Catálogo cerrado de flows
Solo `checkout-full` y `checkout-card-declined` son flows válidos. Cualquier otro valor en `SyntheticUserConfig.flows` es rechazado por Pydantic antes de llegar al runner.

### BR-U1-02: Invariante orders_created = 0
`FlowResult.orders_created` debe ser siempre 0. El runner verifica `assert flow_result.orders_created == 0` antes de retornar `ProfileResult`. Si fuera > 0, lanza `InfrastructureError("orders_created invariant violated")`.

**Adicional:** el paso `payment_failure_validation` del flow `checkout-full` valida explícitamente que la página de confirmación de orden **NO** aparezca. Si aparece, lanza `InfrastructureError("real order created — invariant violated")`.

### BR-U1-03: Email del shopper restringido (ENFORCEMENT POINT)
Validación obligatoria al inicio de `run_profile`:
```python
assert env.shopper.email.endswith("@testpilot.internal"), \
    "Shopper email must be @testpilot.internal — invariant P1 (zero contamination)"
```
Razón: protección contra Secrets Manager mal configurado que pudiera apuntar a un email real → riesgo de generar mailings/órdenes contaminantes.

### BR-U1-04: Disciplina de screenshots (ACTUALIZADA)
`StepResult.screenshot_url` se llena según los flags del config:
1. `screenshot_on_success=True` + step success → screenshot con `screenshot_state="ok"`.
2. `screenshot_on_error=True` + step failed → screenshot con `screenshot_state="fail"` (siempre True por BR-U0-04).
3. `is_final_step=True` siempre captura, sin importar flags.

Cambio vs versión anterior: ya no es "solo fallo + final" — el prompt actualizado del proyecto exige screenshots en **todos los módulos del flow** cuando los flags están activos. Costo documentado y aceptado (ver `infrastructure-design.md` U4).

### BR-U1-05: Sin time.sleep()
No usar `time.sleep()` ni `asyncio.sleep()` en flows. Usar exclusivamente:
- `page.wait_for_selector(selector, state="visible")`
- `expect(locator).to_be_visible()`
- `page.wait_for_load_state("networkidle")`

### BR-U1-06: Timeouts configurables, sin literales en flows
Timeouts derivan de `env-vars-catalog.md`: `STEP_TIMEOUT_MS` (default 60000), `NAVIGATION_TIMEOUT_MS` (default 30000). Se aplican via `browser_context.set_default_timeout()`. Ningún `page.wait_for_*(timeout=NUMBER)` con literal en flows.

### BR-U1-07: Selectores solo en selectors.py
Ningún string CSS/XPath puede aparecer en `flows/`, `auth/`, ni `runner.py`. Solo se importan desde `src.executor.selectors`.

**Categorías obligatorias en selectors.py:**
- `LOGIN_*` (input email, input password, submit button, my-account indicator)
- `SEARCH_*` (input, submit, results container)
- `CATEGORY_*` (product tile, results count)
- `PDP_*` (title, price, variant selector, add-to-cart button)
- `CART_*` (minicart container, product name, product price, checkout button)
- `CHECKOUT_*` (shipping form fields, payment form fields, continue button)
- `CONFIRMATION_*` (heading — usado para detectar orden creada accidentalmente)
- `DECLINE_*` (decline message container, `DECLINE_MESSAGE_PATTERN` regex)

### BR-U1-08: Distinción infrastructure_error vs app error
**`InfrastructureError`** (run → YELLOW):
- Storefront unreachable (timeout TLS/DNS, conexión rechazada en `env_access_auth`)
- HTTP 401 en env_access (credenciales mal configuradas en Secrets Manager)
- Browser crash (`browser.is_connected() == False`)
- Invariante `orders_created` violado

**`StepResult(status="failed")`** (run → RED si en flow funcional):
- Selector no encontrado (selector roto, página cargó pero le falta el elemento)
- Login form rechaza credenciales válidas (posible cambio en SFCC)
- Checkout no avanza al siguiente paso
- Mensaje de decline no aparece en `checkout-card-declined`

### BR-U1-09: Browser context configurado correctamente
`browser.new_context()` debe incluir:
- `locale=profile.locale`
- `user_agent=profile.user_agent`
- `viewport={width, height}` desde profile
- `is_mobile=profile.is_mobile`
- `has_touch=profile.is_mobile`
- `device_scale_factor=2 if profile.is_mobile else 1`
- `http_credentials={"username": env.env_access.username, "password": env.env_access.password}` ★ NUEVO

### BR-U1-10: Cierre del browser garantizado
`browser.close()` debe ejecutarse en bloque `finally` en `runner.run_profile`. Si el flow falla en cualquier punto, el browser cierra correctamente — previene leaks de procesos zombi en ECS.

### BR-U1-11: env_access nunca se loggea
Las credenciales `EnvironmentAccessCredentials` y `ShopperCredentials` se pasan a Playwright pero NUNCA se loggean. Cualquier `logger.info/debug(env)` debe usar `str(env.env_access)` que retorna versión redactada (BR-U0-03).

**Verificación:** test inspecciona los logs producidos por un run completo y rechaza si encuentra `password=<valor real>`.

### BR-U1-12: Sin emails reales (defensa en profundidad)
Adicional a BR-U1-03, los flows NO deben tener fallback a un email "default" hardcoded. Si `env.shopper.email` no termina en `@testpilot.internal`, el runner falla — no usa un email genérico.

---

## Reglas de los flows individuales

### checkout-full — 10 pasos

| # | Nombre | Acción principal | Datos |
|---|--------|-----------------|-------|
| 1 | env_access_auth | `page.goto(store_url)` con HTTP Basic Auth | env.env_access |
| 2 | shopper_login | Fill form + click submit + esperar MY_ACCOUNT | env.shopper |
| 3 | search_product | Fill SEARCH_INPUT + click SEARCH_SUBMIT | config.products[i].search_term |
| 4 | category_page | Wait for CATEGORY_RESULTS_CONTAINER | — |
| 5 | pdp_variant_select | Click first product → si validate_variant, cambiar PDP_VARIANT_SELECTOR | config.products[i].validate_variant |
| 6 | add_to_cart | Click PDP_ADD_TO_CART_BUTTON → wait CART_MINI_CONTAINER | — |
| 7 | mini_cart_validation | Validar CART_PRODUCT_NAME y CART_PRODUCT_PRICE | — |
| 8 | checkout_shipping | Fill shipping form con TEST_SHIPPING | constantes |
| 9 | checkout_payment | Fill payment form con TEST_CARD_FAIL | constante |
| 10 | payment_failure_validation | Wait for PAYMENT_FAIL_MESSAGE + assert NOT CONFIRMATION_HEADING | invariante |

### checkout-card-declined — 10 pasos

| # | Nombre | Acción principal | Datos |
|---|--------|-----------------|-------|
| 1–8 | (idéntico a checkout-full) | — | — |
| 9 | checkout_payment_declined | Fill payment con TEST_CARD_DECLINE | constante |
| 10 | verify_decline_message | Wait for DECLINE_MESSAGE_CONTAINER + match DECLINE_MESSAGE_PATTERN | regex |

---

## Trazabilidad

| BR | Historia | Security/Principio |
|---|---|---|
| BR-U1-02, BR-U1-03, BR-U1-12 | H1.2 (cero contaminación) | Principio P1 |
| BR-U1-04 | H1.5 (disciplina screenshots) | — |
| BR-U1-08 | H1.4 (infra vs app) | M17 |
| BR-U1-11 | — | SECURITY-10 |
| BR-U1-09 (http_credentials) | H1.1 (3 perfiles) | — |
