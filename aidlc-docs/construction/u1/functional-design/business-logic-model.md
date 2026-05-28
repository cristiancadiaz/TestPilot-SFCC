# Business Logic Model — U1 Executor Playwright (actualizado 2026-05-24)

## Propósito desde la perspectiva del producto

U1 es el **corazón funcional** del producto. Es el módulo que **realmente ejecuta** los flujos de checkout en la tienda SFCC con browsers reales. **Cambio mayor vs versión anterior:** ahora el executor maneja **dos pasos de autenticación separados** (env_access + shopper) antes de ejecutar el flow funcional.

**Outcomes de negocio:**
1. **Cero contaminación** (Principio P1): `orders_created=0` invariante validado por assert al final de cada flow.
2. **Cobertura geográfica:** 3 perfiles × 2 flows = 6 ejecuciones paralelas (mobile-co, desktop-co, desktop-ec).
3. **Disciplina de evidencia:** screenshots en cada módulo del flow según flags configurables del run.
4. **Distinción infraestructura vs tienda** (M17): un timeout de CDN se reporta como YELLOW; un selector roto, como RED.
5. **Soporte al nuevo modelo de credenciales duales:** garantiza que el storefront accede primero al ambiente y luego se loguea como shopper SFCC.

---

## Flujo de ejecución principal (CAMBIO MAYOR)

```
run_profile(profile, flow_name, config, env: ResolvedEnvironment)
    │
    ├── 1. Validar pre-condiciones
    │       assert env.shopper.email.endswith("@testpilot.internal")   # BR-U0-02
    │       assert config.screenshot_on_error is True                  # BR-U0-04
    │
    ├── 2. Lanzar browser con perfil + httpCredentials (env_access)
    │       playwright.chromium.launch(headless=True)
    │       browser.new_context(
    │           locale=profile.locale,
    │           user_agent=profile.user_agent,
    │           viewport={width, height},
    │           is_mobile=profile.is_mobile,
    │           has_touch=profile.is_mobile,
    │           http_credentials={
    │               "username": env.env_access.username,
    │               "password": env.env_access.password,
    │           },  # ★ NUEVO — HTTP Basic Auth automático
    │       )
    │
    ├── 3. Step: env_access_auth
    │       page.goto(env.config.store_url, wait_until="domcontentloaded")
    │       → si 401: InfrastructureError("env_access auth rejected")
    │       → si timeout: InfrastructureError("storefront unreachable")
    │       → si 200: StepResult(name="env_access_auth", status="success", ...)
    │
    ├── 4. Step: shopper_login
    │       page.goto(LOGIN_URL)
    │       page.fill(LOGIN_EMAIL_INPUT, env.shopper.email)
    │       page.fill(LOGIN_PASSWORD_INPUT, env.shopper.password)
    │       page.click(LOGIN_SUBMIT_BUTTON)
    │       page.wait_for_selector(MY_ACCOUNT_INDICATOR)
    │       → si falla: StepResult(status="failed") — bug de la tienda, no infra
    │       → captura screenshot según flags
    │
    ├── 5. Ejecutar flow funcional (recibe page ya autenticada)
    │       if flow_name == "checkout-full":
    │           result = await checkout_full.run(page, config, env)
    │       elif flow_name == "checkout-card-declined":
    │           result = await checkout_card_declined.run(page, config, env)
    │
    ├── 6. Verificar invariantes
    │       assert flow_result.orders_created == 0           # BR-U1-02
    │       if violated: InfrastructureError(...)
    │
    ├── 7. Cleanup
    │       finally: browser.close()
    │
    └── 8. Retornar ProfileResult(profile, flow_result, traffic_light)
```

**Cambio crítico vs versión previa:**
- ANTES: el flow asumía un único storefront accesible sin auth.
- AHORA: dos autenticaciones separadas — **env_access** (HTTP Basic Auth nativo de Playwright via `http_credentials`) y **shopper_login** (form interactivo en la página de login de SFCC).

---

## Modelo de paso de flow (sin cambios estructurales)

```python
async def _execute_step(
    page: Page,
    name: str,
    action: Callable[[], Awaitable[None]],
    config: SyntheticUserConfig,
    is_final: bool = False,
) -> StepResult:
    start = time.monotonic()
    try:
        await action()
        duration_ms = int((time.monotonic() - start) * 1000)
        screenshot_url = None
        screenshot_state = None
        if config.screenshot_on_success or is_final:
            screenshot_url = await _take_screenshot(page, name, state="ok")
            screenshot_state = "ok"
        return StepResult(
            name=name, status="success",
            duration_ms=duration_ms,
            screenshot_url=screenshot_url,
            screenshot_state=screenshot_state,
        )
    except InfrastructureError:
        raise  # propagar al runner
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        screenshot_url = None
        screenshot_state = None
        if config.screenshot_on_error:  # default True por invariante
            screenshot_url = await _take_screenshot(page, name, state="fail")
            screenshot_state = "fail"
        return StepResult(
            name=name, status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_url=screenshot_url,
            screenshot_state=screenshot_state,
        )
```

**Cambio:** la disciplina de screenshots ya no es "solo fallo + final" — ahora se rige por los **flags `screenshot_on_success` y `screenshot_on_error`** del config. Esto refleja que el prompt actualizado del proyecto exige screenshots en **todos los módulos del flow** cuando los flags están activos. La nota de costo (~17 GB/mes con `screenshot_on_success=True`) se documenta en `infrastructure-design.md` de U4 — el usuario es responsable de bajar el flag tras el periodo de validación inicial.

---

## Estructura de módulos (actualizada)

```
src/executor/
├── __init__.py                 # exports: run_profile, InfrastructureError
├── profiles/
│   ├── __init__.py             # exports: MOBILE_CO, DESKTOP_CO, DESKTOP_EC, ALL_PROFILES
│   ├── mobile_co.py
│   ├── desktop_co.py
│   └── desktop_ec.py           # ★ reemplaza mobile_mx
├── selectors.py                # SFCCSelectors (ALL CSS strings)
├── auth/                       # ★ NUEVO submódulo
│   ├── __init__.py
│   └── shopper_login.py        # función shopper_login(page, credentials)
├── flows/
│   ├── __init__.py             # exports: checkout_full, checkout_card_declined
│   ├── checkout_full.py
│   └── checkout_card_declined.py
└── runner.py                   # run_profile() entry point
```

**Cambios:**
- `desktop_ec.py` reemplaza `mobile_mx.py` (alineado con prompt actualizado del proyecto).
- Nuevo submódulo `auth/` con `shopper_login.py` — encapsula el form de login. Se reutiliza en ambos flows.
- `env_access` se maneja vía `http_credentials` en `browser.new_context()` — no requiere módulo dedicado.

---

## Flujos funcionales (actualizados)

### checkout-full — 10 pasos (cambio: +2 pasos vs versión anterior)

| # | Nombre | Acción principal | Source de datos |
|---|--------|-----------------|------------------|
| 1 | `env_access_auth` | `page.goto(store_url)` con HTTP Basic Auth | `env.env_access` |
| 2 | `shopper_login` | Fill email+password, click submit | `env.shopper` |
| 3 | `search_product` | Fill search box + submit | `config.products[i].search_term` |
| 4 | `category_page` | Verificar página de categoría / resultados | — |
| 5 | `pdp_variant_select` | Si `validate_variant=true`: cambiar talla/color | `config.products[i].validate_variant` |
| 6 | `add_to_cart` | Click "Add to Cart" + esperar minicart | — |
| 7 | `mini_cart_validation` | Validar producto y precio en minicart | — |
| 8 | `checkout_shipping` | Llenar shipping form con datos de prueba | constantes embebidas |
| 9 | `checkout_payment` | Llenar payment con tarjeta que falla | constante `TEST_CARD_FAIL` |
| 10 | `payment_failure_validation` | Validar que el pago falla en el paso final | — |

**Invariante del flow:** el paso 10 DEBE confirmar que NO se creó orden. Si la página de confirmación de orden aparece, lanza `InfrastructureError("real order created — invariant violated")`.

### checkout-card-declined — 10 pasos (cambio: +2 pasos vs versión anterior)

| # | Nombre | Acción principal | Notas |
|---|--------|-----------------|-------|
| 1–8 | (igual a checkout-full pasos 1-8) | — | — |
| 9 | `checkout_payment_declined` | Llenar payment con `TEST_CARD_DECLINE` | — |
| 10 | `verify_decline_message` | Validar que mensaje de error aparece | Regex `DECLINE_MESSAGE_PATTERN` |

**Resultado esperado:** paso 10 status="success" si el mensaje aparece. Si el flow termina sin mensaje de decline, status="failed" (bug de la tienda).

---

## Manejo de errores de autenticación

| Escenario | Tipo de error | Acción |
|---|---|---|
| `env_access` rechazado (401 en `page.goto`) | `InfrastructureError` | Run termina YELLOW, alerta a Ops para verificar Secrets Manager |
| Storefront unreachable (timeout DNS/TLS) | `InfrastructureError` | Run termina YELLOW, alerta a Ops |
| `shopper_login` form no aparece | `StepResult(status="failed")` | Run continúa, semáforo RED |
| Login submit rechaza credenciales válidas | `StepResult(status="failed")` | Run continúa, semáforo RED (posible cambio del flujo de login en SFCC) |
| Login OK pero `MY_ACCOUNT_INDICATOR` no aparece | `StepResult(status="failed")` | Run continúa, semáforo RED |

**Razón de la distinción:** problemas de env_access son de configuración/infra (no de la tienda) → no deben generar alarmas falsas de regresión de UX. Problemas de shopper_login pueden ser tanto credenciales rotas (infra) como un cambio en el flujo de SFCC (regresión funcional) — en MVP los tratamos como funcionales y dejamos que el ingeniero diferencie en el debug.

---

## Manejo de screenshots — disciplina y costo

**Disciplina (cambio vs versión anterior):**
- `screenshot_on_success=True` + `screenshot_on_error=True` → screenshot en CADA paso, etiquetado `{run}/{profile}/{flow}/{step}-{ok|fail}.png`.
- `screenshot_on_success=False` + `screenshot_on_error=True` → screenshot solo en fallos. Recomendado tras validar el sistema.
- `screenshot_on_error=False` → rechazado por Pydantic (BR-U0-04).

**Costo estimado (alineado con prompt del proyecto):**
- Con `screenshot_on_success=True`: ~17 GB/mes a escala completa (10 runs/día × 3 perfiles × 2 flows × 10 pasos × 2 estados × ~280 KB).
- Con `screenshot_on_success=False`: ~500 MB/mes (solo fallos + step final).
- **Recomendación PO:** mantener `screenshot_on_success=True` en sprint 0-2 para validar coverage. Después, bajar a `False` por default en el dashboard P2.

**Almacenamiento:**
- MVP local: `/tmp/testpilot-screenshots/{run_id}/...`
- Producción: S3 bucket con lifecycle 90 días (ver `infrastructure-design.md` de U4).

---

## Datos embebidos (no secretos)

Los datos de shipping son ficticios y fijos — no requieren env vars ni secretos:

```python
TEST_SHIPPING = {
    "firstname": "TestPilot",
    "lastname": "User",
    "address": "123 Test Street",
    "city": "Bogota",
    "state": "CUN",
    "zip": "110111",
    "country": "CO",
    "phone": "3000000000",
}
```

Tarjetas de prueba (en `selectors.py` como constantes — no son secretos):
- `TEST_CARD_FAIL`: número que el motor de pago de prueba rechaza al final.
- `TEST_CARD_DECLINE`: número que el motor de pago rechaza con mensaje de decline visible.

---

## Concurrencia

- U1 ejecuta **un solo perfil** por llamada a `run_profile`.
- La paralelización de 3 perfiles ocurre en U4 mediante `asyncio.gather` con cap `MAX_CONCURRENT_PROFILES=3` (env var).
- Cada perfil = un browser independiente — sin estado compartido entre perfiles.

---

## Criterio de completitud (Definition of Done)

- [ ] Tests pasan con mocks de Playwright.
- [ ] `orders_created=0` en todos los flows.
- [ ] Disciplina de screenshots respeta flags `screenshot_on_success`/`screenshot_on_error`.
- [ ] 3 perfiles instanciados: mobile-co, desktop-co, desktop-ec.
- [ ] `env_access_auth` y `shopper_login` ejecutados en orden antes del flow funcional.
- [ ] Distinción `InfrastructureError` vs `StepResult(status="failed")` cubierta por tests.
- [ ] H1.1–H1.5 AC satisfechos (ver `inception/user-stories/user-stories.md`).
