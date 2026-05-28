# Domain Entities — U1 Executor Playwright (actualizado 2026-05-24)

## Módulo: `src/executor/`

Todos los modelos de entrada/salida del Executor están definidos en `src/models.py` (U0). U1 **consume** y **produce** entidades del contrato compartido. **Cambio vs versión anterior:** consume `ResolvedEnvironment` (nuevo) y produce el resultado tomando en cuenta las dos autenticaciones.

---

## Entidades consumidas (input de U1)

### ResolvedEnvironment (NUEVO — input principal)
Definido en U0 `src/models.py`. Agrupa `EnvironmentConfig` + `EnvironmentAccessCredentials` + `ShopperCredentials`. U1 lo recibe ya resuelto desde U4 (que consulta DynamoDB + Secrets Manager).

```python
class ResolvedEnvironment(BaseModel):
    config: EnvironmentConfig          # tiene store_url
    env_access: EnvironmentAccessCredentials  # username + password redactado
    shopper: ShopperCredentials        # email + password redactado
```

**Uso en U1:**
- `env.config.store_url` → primer `page.goto`
- `env.env_access.username/password` → `http_credentials` en `browser.new_context`
- `env.shopper.email/password` → form de login en paso `shopper_login`

### SyntheticUserConfig (consume desde src.models)
Sin credenciales (cambio vs versión previa). Contiene `environment_id`, `products`, `flows`, `profiles`, `screenshot_on_*`.

### BrowserProfile (consume desde src.models)
Instancias en U1 — constantes de módulo:

| Constante | name | viewport | locale | UA family | is_mobile |
|-----------|------|----------|--------|-----------|-----------|
| `MOBILE_CO` | "mobile-co" | 390×844 | es-CO | Chrome mobile | True |
| `DESKTOP_CO` | "desktop-co" | 1440×900 | es-CO | Chrome desktop | False |
| `DESKTOP_EC` | "desktop-ec" | 1280×800 | es-EC | Chrome desktop | False |

`ALL_PROFILES = [MOBILE_CO, DESKTOP_CO, DESKTOP_EC]`. **Cambio:** `desktop-ec` (Ecuador) reemplaza `mobile-mx` de la versión anterior — alineado con el prompt actualizado del proyecto.

---

## Entidades producidas (output de U1)

### StepResult (produce hacia src.models)
Resultado de cada paso del flow. Llenado según disciplina de BR-U1-04.

- `screenshot_url`: ruta relativa S3, ej. `{run_id}/{profile_id}/{flow_name}/{step_name}-{ok|fail}.png`.
- `screenshot_state`: `"ok"` | `"fail"` | `None`.

### FlowResult (produce hacia src.models)
- `flow_name`: nombre canónico (checkout-full | checkout-card-declined).
- `status`: derivado de los steps (success si todos OK; failed si ≥1 failed sin InfraError; error si InfraError).
- `orders_created`: siempre 0 — invariante. El runner verifica antes de retornar.

### ProfileResult (produce hacia src.models)
Agrupa `BrowserProfile` + `FlowResult` + `TrafficLight` (parcial — el TrafficLight definitivo lo asigna U3 al consolidar con baseline). En U1, el TrafficLight inicial es:
- GREEN si flow.status == "success"
- YELLOW si flow.status == "error" (InfraError)
- RED si flow.status == "failed"

(U3 puede degradar GREEN a YELLOW por exceder baseline p95.)

---

## Entidades internas de U1 (no exportadas)

### InfrastructureError
Excepción interna. Se lanza en condiciones de BR-U1-08. El runner la captura y la convierte en `FlowResult(status="error")`.

```python
class InfrastructureError(Exception):
    """Raised when the failure is infrastructure/auth/network, not a store bug."""
    pass
```

### SFCCSelectors (solo en `src/executor/selectors.py`)
Clase de datos (no instanciable) que centraliza **todos** los selectores CSS/XPath. Regla no negociable (BR-U1-07): ningún selector aparece fuera de este archivo.

**Categorías ACTUALIZADAS:**
- `LOGIN_*` — ★ nueva categoría (login form del shopper)
- `SEARCH_*`
- `CATEGORY_*`
- `PDP_*` (incluye `PDP_VARIANT_SELECTOR`)
- `CART_*` (minicart + cart page)
- `CHECKOUT_*` (shipping + payment)
- `CONFIRMATION_*` (heading — usado para detectar orden accidental)
- `DECLINE_*` (con regex `DECLINE_MESSAGE_PATTERN`)

**Constantes de datos (no son selectores):**
- `TEST_CARD_FAIL` — número de tarjeta de prueba que falla en checkout-full
- `TEST_CARD_DECLINE` — número de tarjeta que dispara mensaje de decline
- `TEST_SHIPPING` — dict con datos de shipping ficticios

---

## Entidades del nuevo submódulo auth/

### shopper_login(page, credentials, selectors) → StepResult
Función pura que encapsula el form de login. Recibe la `Page` ya autenticada a nivel ambiente.

```python
async def shopper_login(
    page: Page,
    credentials: ShopperCredentials,
    config: SyntheticUserConfig,
) -> StepResult:
    """
    1. page.goto(LOGIN_URL_RELATIVE_PATH)
    2. page.fill(LOGIN_EMAIL_INPUT, credentials.email)
    3. page.fill(LOGIN_PASSWORD_INPUT, credentials.password)
    4. page.click(LOGIN_SUBMIT_BUTTON)
    5. page.wait_for_selector(LOGIN_MY_ACCOUNT_INDICATOR)
    6. retorna StepResult(name="shopper_login", status="success", ...)
    """
```

**Razón de extracción:** ambos flows necesitan este paso. Vivir en `auth/` lo hace explícito y testeable independientemente.

---

## Relaciones entre entidades

```
ResolvedEnvironment              SyntheticUserConfig
        │                                │
        └──────────┬─────────────────────┘
                   ▼
         run_profile(profile, flow_name, config, env)
                   │
                   ├─→ BrowserProfile (de profiles/)
                   ├─→ SFCCSelectors (de selectors.py)
                   ├─→ shopper_login() (de auth/)
                   └─→ flows.checkout_full.run() OR flows.checkout_card_declined.run()
                                │
                                ▼
                       FlowResult (orders_created=0)
                                │
                                ▼
                       ProfileResult (profile, flow_result, traffic_light)
                                │
                                ▼
                          consumido por U3 (Reporter)
```

---

## Comparación con versión anterior

| Aspecto | Antes | Ahora |
|---|---|---|
| Input principal | `SyntheticUserConfig` con `storefront_url + email + password` | `SyntheticUserConfig` (sin credenciales) + `ResolvedEnvironment` |
| Perfiles | mobile-co, desktop-co, mobile-mx | mobile-co, desktop-co, desktop-ec |
| Steps por flow | 8 | 10 (+2 por autenticación dual) |
| Auth | Implícita (storefront accesible) | Explícita: env_access (HTTP Basic) + shopper_login (form) |
| Submódulo auth/ | No existía | Nuevo |
| Screenshots | Solo en fallo + final | En cada paso según flags |
| Selectores nuevos | — | `LOGIN_*` (familia completa) |
