# U1 Executor Playwright — Code Generation Plan

> **Reconciliado a specs v2 el 2026-06-06** (era pre-realineacion 2026-05-24). Deltas aplicados:
> workspace root corregido, perfil `mobile_mx` eliminado y reemplazado por `desktop_ec` (catalogo v2),
> todos los checkboxes reseteados a `[ ]` (el plan anterior los marcaba `[x]` sin que existiera codigo),
> submódulo `auth/` agregado (build-sequence Sprint 1 Gate 3), categorias de selectores completadas,
> conteo de pasos de flows alineado al recorrido realista de checkout (~10 pasos), invariantes
> hard-codeados explicitamente (cero contaminacion, ADR-003, Playwright waits). Ruta protegida HITL
> declarada en nota de autorizacion.

---

## Unit Context

- **Tipo**: Brownfield — todos los archivos son NUEVOS (no existe `src/executor/`)
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Requisitos cubiertos**: RF-04, RF-05, RF-06, RF-07, RF-08, RNF-02, RNF-03, RNF-04, RNF-07
- **Ola**: 1 (checkout gate — wave-1 primera entrega funcional)

### Nota de autorizacion HITL — ruta protegida

`src/executor/flows/` es una ruta protegida (corre contra storefronts de staging/produccion).
Su generacion de codigo fue **autorizada por el humano en esta sesion (2026-06-06)** como parte
de la apertura de la fase Construction Code Generation, U1, Sprint 1. Cualquier modificacion
posterior a flows/ requiere nueva aprobacion HITL segun `CLAUDE.md` seccion "Requires Human
Confirmation Before Editing".

---

## Dependencies

- Requiere **U0 completo** (Gate 1 pasado). `src/models.py` debe existir con los modelos:
  `BrowserProfile`, `FlowResult`, `StepResult`, `FlowName`, `ProfileId`, `RunOptions`,
  `SyntheticUserConfig`.
- Importar SIEMPRE desde `src.models` — nunca redefinir modelos en U1.
- `FlowName` v2 usa snake_case: `checkout_full`, `checkout_card_declined`.
- `ProfileId` v2: `mobile_co`, `desktop_co`, `desktop_ec` (exactamente 3 — `mobile_mx` no existe).

---

## Invariantes que el codigo de U1 DEBE respetar

Los siguientes invariantes del proyecto (CLAUDE.md Hard Invariants) deben reflejarse en codigo
y en tests, no solo en convencion:

1. **Cero contaminacion (inv. #1)**: el pago SIEMPRE falla en el paso final de los flows
   `checkout_*`; emails sinteticos SIEMPRE usan `@testpilot.internal`; `orders_created=0`
   aseverado como assert en flows y en runner antes de retornar `ProfileResult`.
2. **Catalogo cerrado (inv. #2)**: el despacho en `runner.py` usa el registro del catalogo —
   nunca un if/else por nombre de flow. `full_journey` NO es un archivo de flow.
3. **Evidencia dirigida por hallazgos (ADR-003)**: captura en fallo de paso + paso final SIEMPRE.
   En modo auditoría, capturas adicionales SOLO por hallazgo (finding) o punto critico declarado
   (critical). `StepResult.screenshot_state` in {`fail`, `final`, `finding`, `critical`} | None.
   Naming: `{run_id}/{perfil}/{flujo}/{paso}-{fail|final|finding-{dimension}|critical}.png`.
   NUNCA capturar un paso OK sin hallazgo.
4. **Playwright waits (RNF-07)**: `wait_for_selector()` / `expect()` exclusivamente.
   CERO `time.sleep()`.
5. **Logging sin secretos (RNF-03)**: los loggers nombrados por modulo (`__name__`) nunca
   registran credenciales, tokens, URLs con auth, ni PII.
6. **Errores seguros (RNF-04)**: distincion explicita `InfrastructureError` (red/DNS/timeout
   de Playwright) vs error funcional de la app. `InfrastructureError` capturado en runner ->
   `ProfileResult(status="error")`.
7. **Credenciales server-side (ADR-001)**: los flows reciben `env: ResolvedEnvironment` ya
   resuelto — nunca strings sueltos de URL/usuario/password. El runner NO resuelve credenciales
   (es responsabilidad del orquestador U4).

---

## Steps

### Step 1: Crear `src/executor/__init__.py` [ ]

- **Accion**: CREATE
- **Contenido**: export publico de `run_profile` desde `runner.py`. Modulo raiz del paquete.

### Step 2: Crear `src/executor/profiles/__init__.py` [ ]

- **Accion**: CREATE
- **Contenido**: instancias `MOBILE_CO`, `DESKTOP_CO`, `DESKTOP_EC` (3 exactamente, catalogo v2)
  + lista `ALL_PROFILES: list[BrowserProfile]` con los 3 elementos en ese orden.
  Importa `BrowserProfile` desde `src.models`.

### Step 3: Crear `src/executor/profiles/mobile_co.py` [ ]

- **Accion**: CREATE
- **Contenido**: instancia `BrowserProfile`:
  - `name="mobile_co"`, `viewport_width=390`, `viewport_height=844`
  - `locale="es-CO"`, `is_mobile=True`
  - `user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"`

### Step 4: Crear `src/executor/profiles/desktop_co.py` [ ]

- **Accion**: CREATE
- **Contenido**: instancia `BrowserProfile`:
  - `name="desktop_co"`, `viewport_width=1440`, `viewport_height=900`
  - `locale="es-CO"`, `is_mobile=False`
  - `user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"`

### Step 5: Crear `src/executor/profiles/desktop_ec.py` [ ]

- **Accion**: CREATE
- **Contenido**: instancia `BrowserProfile` (reemplaza el `mobile_mx` pre-realineacion):
  - `name="desktop_ec"`, `viewport_width=1280`, `viewport_height=800`
  - `locale="es-EC"`, `is_mobile=False`
  - `user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"`
- **Nota**: `mobile_mx` NO existe en specs v2. El archivo se llama `desktop_ec.py`.

### Step 6: Crear `src/executor/selectors.py` [ ]

- **Accion**: CREATE
- **Contenido**: clase `SFCCSelectors` con TODOS los selectores CSS/XPath como constantes de
  clase en `SCREAMING_SNAKE_CASE`. Cada constante lleva un comentario de una linea explicando
  a que elemento del storefront corresponde. Grupos obligatorios para checkout + login:

  ```
  # Grupo LOGIN_* — formulario de login del shopper
  LOGIN_EMAIL_INPUT        # Campo de email del shopper
  LOGIN_PASSWORD_INPUT     # Campo de password del shopper
  LOGIN_SUBMIT_BUTTON      # Boton de submit del formulario de login
  LOGIN_ERROR_MESSAGE      # Mensaje de error de credenciales invalidas
  LOGIN_REGISTERED_USER    # Link/tab de "usuario registrado" si aplica

  # Grupo SEARCH_* — barra de busqueda del header
  SEARCH_INPUT             # Input de busqueda en el header
  SEARCH_SUBMIT            # Boton de busqueda (lupa / submit)
  SEARCH_RESULTS_GRID      # Grid de resultados del PLP

  # Grupo PDP_* — pagina de detalle de producto
  PDP_PRODUCT_NAME         # Nombre del producto en PDP
  PDP_PRICE                # Precio principal visible en PDP
  PDP_VARIANT_SELECT       # Selector de variante (talla/color)
  PDP_ADD_TO_CART          # Boton "Agregar al carrito"

  # Grupo CART_* — mini carrito y pagina de carrito
  CART_MINI_CART           # Contenedor del mini carrito
  CART_ITEM_COUNT          # Indicador de cantidad de items
  CART_CHECKOUT_BUTTON     # Boton "Ir al checkout" en el carrito
  CART_ITEM_PRICE          # Precio por item en el carrito

  # Grupo CHECKOUT_* — flujo de checkout
  CHECKOUT_SHIPPING_FORM   # Formulario de datos de envio
  CHECKOUT_SHIPPING_NEXT   # Boton continuar desde envio a pago
  CHECKOUT_PAYMENT_SECTION # Seccion de pago en checkout

  # Grupo PAYMENT_* — formulario de pago
  PAYMENT_CARD_NUMBER      # Campo de numero de tarjeta
  PAYMENT_EXPIRY           # Campo de fecha de vencimiento
  PAYMENT_CVV              # Campo de CVV
  PAYMENT_SUBMIT           # Boton de submit del pago
  PAYMENT_ERROR_MESSAGE    # Mensaje de error de pago rechazado
  PAYMENT_DECLINE_MESSAGE  # Mensaje especifico de tarjeta declinada
  ```

  Ademas, constantes de datos de prueba (NO selectores CSS, sino valores de test):

  ```python
  # Tarjeta de prueba — SIEMPRE falla en el paso final (invariante #1)
  TEST_CARD_NUMBER: str = "4111111111111111"
  TEST_CARD_EXPIRY: str = "12/26"
  TEST_CARD_CVV: str = "123"

  # Tarjeta declinada — para flow checkout_card_declined
  DECLINED_CARD_NUMBER: str = "4000000000000002"
  DECLINED_CARD_EXPIRY: str = "12/26"
  DECLINED_CARD_CVV: str = "123"

  # Datos de envio de prueba
  TEST_SHIPPING: dict[str, str] = {
      "first_name": "Testpilot",
      "last_name": "Synthetic",
      "address": "Calle Falsa 123",
      "city": "Bogota",
      "phone": "3001234567",
  }
  ```

- **Invariante**: NINGUN selector se define fuera de este archivo en el codebase (C7).

### Step 7: Crear `src/executor/auth/__init__.py` [ ]

- **Accion**: CREATE
- **Contenido**: export de `shopper_login` desde `shopper_login.py`. Paquete del submódulo auth.

### Step 8: Crear `src/executor/auth/shopper_login.py` [ ]

- **Accion**: CREATE
- **Contenido**: funcion asincrona `shopper_login(page: Page, username: str, password: str) -> StepResult`
  que encapsula el formulario de login del shopper SFCC:
  - Navega al formulario si no esta abierto ya (o recibe la pagina ya en el form).
  - Completa `LOGIN_EMAIL_INPUT`, `LOGIN_PASSWORD_INPUT` con los parametros recibidos.
  - Hace click en `LOGIN_SUBMIT_BUTTON` y espera via `wait_for_selector()` / `expect()`.
  - Verifica que el login fue exitoso (ausencia de `LOGIN_ERROR_MESSAGE` o presencia de
    un elemento post-login).
  - Retorna `StepResult(name="shopper_login", status="success"|"failed", duration_ms=...,
    error=None|str)` con `screenshot_state="fail"` si falla.
  - Las credenciales llegan como parametros ya resueltos desde `ResolvedEnvironment.shopper`
    (ADR-001) — este modulo NUNCA accede a Secrets Manager ni a variables de entorno directamente.
  - Logging: usa `logging.getLogger(__name__)` — NUNCA loguea `username` ni `password`.
- **TDD**: los tests del Step 12 (auth) mockean `Page` y verifican que las credenciales
  NO aparecen en logs; que `LOGIN_EMAIL_INPUT` se llena con el username recibido; que
  un `LOGIN_ERROR_MESSAGE` detectable produce `status="failed"`.

### Step 9: Crear `src/executor/flows/__init__.py` [ ]

- **Accion**: CREATE
- **Contenido**: exports de `run` desde `checkout_full` y `checkout_card_declined`.
  El catalogo de flows en runner usa esta referencia.

### Step 10: Crear `src/executor/flows/checkout_full.py` [ ]

- **Accion**: CREATE
- **Contenido**: funcion `async run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult`
  con exactamente **10 pasos** en orden:

  | # | Nombre del paso             | Descripcion                                                   |
  |---|-----------------------------|---------------------------------------------------------------|
  | 1 | `env_access_auth`           | Autenticacion de infraestructura (http_credentials de env_access) |
  | 2 | `shopper_login`             | Login del shopper via `auth.shopper_login()` con credenciales de `env.shopper` |
  | 3 | `search_product`            | Busqueda del producto via `SEARCH_INPUT` / `SEARCH_SUBMIT`    |
  | 4 | `category_page`             | Seleccion de un resultado en el PLP / grid de categoria       |
  | 5 | `pdp_variant_select`        | Seleccion de variante en PDP (si `config.products[0].validate_variant`) |
  | 6 | `add_to_cart`               | Click en `PDP_ADD_TO_CART`, esperar actualizacion de mini carrito |
  | 7 | `mini_cart_validation`      | Verificar que el item esta en `CART_MINI_CART` y precio es consistente |
  | 8 | `checkout_shipping`         | Completar formulario `CHECKOUT_SHIPPING_FORM` con `TEST_SHIPPING` |
  | 9 | `checkout_payment`          | Ingresar datos de `TEST_CARD_*` en formulario de pago         |
  | 10| `payment_failure_validation`| Verificar que el pago FALLA (invariante #1). El paso reporta `status="success"` cuando la falla se confirma correctamente (el storefront muestra el error esperado). |

  Reglas de implementacion:
  - Cada paso es un `await _execute_step(...)` que retorna `StepResult`.
  - Si un paso falla, los pasos siguientes se marcan `status="skipped"`.
  - `orders_created=0` es un assert hard en la funcion antes de retornar `FlowResult`.
  - `FlowResult.flow_name = "checkout_full"` (FlowName v2).
  - Screenshots: `screenshot_state="fail"` en paso fallido, `screenshot_state="final"` en
    el ultimo paso ejecutado. Naming: `{run_id}/{profile_id}/checkout_full/{paso}-{state}.png`.
  - Emails sinteticos del shopper SIEMPRE terminan en `@testpilot.internal` (viene de `env.shopper`).
  - Todos los waits via `wait_for_selector()` / `expect()`. CERO `time.sleep()`.
  - Logger: `logging.getLogger(__name__)` — sin credenciales en logs.
  - Importa modelos desde `src.models`; selectores desde `src.executor.selectors`.

### Step 11: Crear `src/executor/flows/checkout_card_declined.py` [ ]

- **Accion**: CREATE
- **Contenido**: funcion `async run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult`
  con exactamente **10 pasos** (mismo recorrido que `checkout_full` pero el paso 10 difiere):

  | # | Nombre del paso             | Descripcion                                                   |
  |---|-----------------------------|---------------------------------------------------------------|
  | 1 | `env_access_auth`           | Autenticacion de infraestructura                              |
  | 2 | `shopper_login`             | Login del shopper via `auth.shopper_login()`                  |
  | 3 | `search_product`            | Busqueda del producto                                         |
  | 4 | `category_page`             | Seleccion de resultado en PLP                                 |
  | 5 | `pdp_variant_select`        | Seleccion de variante en PDP                                  |
  | 6 | `add_to_cart`               | Click en add-to-cart, verificar mini carrito                  |
  | 7 | `mini_cart_validation`      | Verificar item y precio en mini carrito                       |
  | 8 | `checkout_shipping`         | Completar formulario de envio                                 |
  | 9 | `checkout_payment`          | Ingresar datos de `DECLINED_CARD_*`                           |
  | 10| `verify_decline_message`    | Verificar que el mensaje de tarjeta declinada (`PAYMENT_DECLINE_MESSAGE`) aparece en la UI. El paso reporta `status="success"` cuando el mensaje se confirma. |

  Reglas de implementacion:
  - Mismas que `checkout_full` (invariantes, screenshots, logging, waits).
  - `orders_created=0` aseverado como assert antes de retornar.
  - `FlowResult.flow_name = "checkout_card_declined"` (FlowName v2).
  - Usa `DECLINED_CARD_*` en el paso 9 en lugar de `TEST_CARD_*`.

### Step 12: Crear `tests/test_executor_auth.py` [ ]

- **Accion**: CREATE — TDD para `auth/shopper_login.py`
- **Contenido**:
  - `test_shopper_login_success`: mock de `Page` donde `LOGIN_ERROR_MESSAGE` no aparece ->
    `StepResult.status == "success"`.
  - `test_shopper_login_failure`: mock de `Page` donde `LOGIN_ERROR_MESSAGE` es visible ->
    `StepResult.status == "failed"`, `screenshot_state == "fail"`.
  - `test_credentials_not_logged`: captura logs del modulo con `caplog`; verifica que
    `"testuser@example.com"` y `"secret123"` NO aparecen en ninguna entrada de log.
  - `test_uses_selectors_from_selectors_py`: verifica que `shopper_login` usa
    `SFCCSelectors.LOGIN_EMAIL_INPUT` y no strings hardcodeados.

### Step 13: Crear `tests/test_executor_profiles.py` [ ]

- **Accion**: CREATE — TDD para `profiles/`
- **Contenido**:
  - `test_mobile_co_fields`: verifica `name="mobile_co"`, `is_mobile=True`, `locale="es-CO"`.
  - `test_desktop_co_fields`: verifica `name="desktop_co"`, `is_mobile=False`, `locale="es-CO"`.
  - `test_desktop_ec_fields`: verifica `name="desktop_ec"`, `is_mobile=False`, `locale="es-EC"`,
    `viewport_width=1280`, `viewport_height=800`.
  - `test_all_profiles_has_exactly_3`: `assert len(ALL_PROFILES) == 3`.
  - `test_all_profiles_names`: verifica que los nombres en `ALL_PROFILES` son exactamente
    `{"mobile_co", "desktop_co", "desktop_ec"}` (sin `mobile_mx`).
  - `test_profiles_are_browser_profile_instances`: cada elemento es instancia de `BrowserProfile`
    (importada desde `src.models`).
  - Estos tests NO lanzan browser.

### Step 14: Crear `tests/test_executor_flows.py` [ ]

- **Accion**: CREATE — TDD para `flows/`
- **Contenido** (usa `MagicMock` / `AsyncMock` de `unittest.mock` para `Page`):
  - `test_checkout_full_returns_flow_result`: mock de `Page` donde todos los waits y clicks
    tienen exito -> `FlowResult.status == "success"`, `FlowResult.flow_name == "checkout_full"`.
  - `test_checkout_full_orders_created_zero`: `assert flow_result.orders_created == 0`.
  - `test_checkout_full_has_10_steps`: `assert len(flow_result.steps) == 10`.
  - `test_checkout_full_step_failure_marks_remainder_skipped`: mock donde `add_to_cart` falla
    -> pasos 7-10 tienen `status="skipped"`.
  - `test_checkout_full_screenshot_policy`: paso final tiene `screenshot_state="final"`;
    ningun paso OK intermedio tiene `screenshot_state` distinto de None salvo en fallo.
  - `test_checkout_card_declined_returns_flow_result`: mock donde `verify_decline_message`
    encuentra el mensaje -> `status == "success"`.
  - `test_checkout_card_declined_orders_created_zero`: `assert flow_result.orders_created == 0`.
  - `test_checkout_card_declined_uses_declined_card`: verifica que el step `checkout_payment`
    usa `SFCCSelectors.DECLINED_CARD_NUMBER` (no `TEST_CARD_NUMBER`).
  - `test_no_sleep_calls`: verifica que `time.sleep` no es importado en los modulos de flows
    (inspeccion de AST o grep del modulo).

### Step 15: Crear `src/executor/runner.py` [ ]

- **Accion**: CREATE
- **Contenido**:

  ```python
  # Funciones y clases principales:

  class InfrastructureError(Exception):
      """Error de infraestructura: timeout de red/DNS en Playwright, browser crash."""
      pass

  async def run_profile(
      profile: BrowserProfile,
      flow_name: FlowName,
      config: SyntheticUserConfig,
      env: ResolvedEnvironment,
      run_id: str,
  ) -> ProfileResult:
      """Ejecuta un flow en un perfil. Captura InfrastructureError y lo convierte
      en ProfileResult con status="error". No resuelve credenciales (ADR-001)."""
  ```

  - Lanza el browser con configuracion del perfil (viewport, locale, user_agent, is_mobile).
  - Despacha el flow via el registro del catalogo (no if/else por nombre). En U1 el registro
    contiene: `{"checkout_full": checkout_full.run, "checkout_card_declined": checkout_card_declined.run}`.
    El despacho es generico: `FLOW_REGISTRY[flow_name](page, config, env, run_id, profile.name)`.
  - `InfrastructureError` capturado -> `ProfileResult` con `FlowResult.status="error"`.
  - Retorna `ProfileResult(profile=profile, flow_result=flow_result, traffic_light=TrafficLight.GREEN)`
    (el traffic_light definitivo lo calcula el reporter con baseline; aqui se usa GREEN como
    placeholder que el reporter sobreescribe).
  - `assert profile_result.flow_result.orders_created == 0` antes de retornar.
  - Logger `logging.getLogger(__name__)` — sin credenciales.
  - Funciones internas: `_create_context(browser, profile)`, `_take_screenshot(page, path)`,
    `_execute_step(page, step_name, coro) -> StepResult`.

### Step 16: Crear `tests/test_executor_runner.py` [ ]

- **Accion**: CREATE — TDD para `runner.py`
- **Contenido** (mock completo de Playwright con `AsyncMock`):
  - `test_run_profile_returns_profile_result`: mock de `checkout_full.run` -> retorna
    `FlowResult` exitoso -> `run_profile` retorna `ProfileResult`.
  - `test_infrastructure_error_handled`: mock que lanza `PlaywrightError` en browser launch
    -> `run_profile` retorna `ProfileResult` con `flow_result.status == "error"` en lugar de
    propagar la excepcion.
  - `test_orders_created_assert_zero`: mock donde un flow retorna `FlowResult(orders_created=1)`
    -> `run_profile` lanza `AssertionError` (invariante #1 roto).
  - `test_flow_dispatch_uses_registry`: verifica que `run_profile` con `flow_name="checkout_full"`
    invoca `checkout_full.run` y no una condicion if/else.
  - `test_infrastructure_error_distinct_from_app_error`: `InfrastructureError` y un fallo
    funcional del flow producen `ProfileResult` con `status` diferente (error vs failed).

### Step 17: Crear `aidlc-docs/construction/u1/code/code-summary.md` [ ]

- **Accion**: CREATE
- **Contenido**: resumen de los archivos creados en U1, Gate 3 checklist, trazabilidad RF->archivo,
  y notas sobre selectores pendientes de ajuste cuando se obtenga acceso al storefront real.

---

## Traceability

| RF / RNF | Steps |
|---|---|
| RF-04 (3 perfiles: mobile_co, desktop_co, desktop_ec) | Steps 2, 3, 4, 5, 13 |
| RF-05 (selectores centralizados, todas las categorias: LOGIN_*, SEARCH_*, PDP_*, CART_*, CHECKOUT_*, PAYMENT_*) | Step 6 |
| RF-06 (checkout_full, 10 pasos, firma con ResolvedEnvironment) | Steps 10, 14 |
| RF-07 (checkout_card_declined, 10 pasos, verify_decline_message) | Steps 11, 14 |
| RF-08 (runner, despacho generico via catalogo, InfrastructureError) | Steps 15, 16 |
| RNF-02 (orders_created=0 en flows y runner, assert hard) | Steps 10, 11, 15, 14, 16 |
| RNF-03 (logging sin secretos, logger por modulo) | Steps 8, 10, 11, 15 |
| RNF-04 (InfrastructureError vs error funcional, distincion explicita) | Steps 15, 16 |
| RNF-07 (wait_for_selector/expect, cero time.sleep) | Steps 10, 11, 14 |
| ADR-001 (credenciales via ResolvedEnvironment, no strings sueltos) | Steps 8, 10, 11, 15 |
| ADR-003 (evidence fail+final siempre, finding/critical solo en audit) | Steps 10, 11, 14 |
| Gate 3 (auth encapsulada y testeable, 3 perfiles, InfraError cubierta, orders_created=0) | Steps 7, 8, 12, 13, 16 |

---

## Gate 3 — Checklist de promocion (post-U1)

- [ ] Tests pasan con mocks de Playwright (`uv run pytest tests/test_executor_*.py`)
- [ ] `orders_created=0` aseverado en tests de flows y runner
- [ ] Disciplina de screenshots respeta flags (ADR-003 verificado en tests)
- [ ] 3 perfiles instanciados correctamente — `ALL_PROFILES` tiene exactamente 3 elementos con
  nombres `mobile_co`, `desktop_co`, `desktop_ec`
- [ ] `shopper_login` form encapsulado en `auth/shopper_login.py` y testeable con mock de Page
- [ ] Ningun selector hardcodeado fuera de `selectors.py` (grep en `src/executor/flows/` y
  `src/executor/runner.py`)
- [ ] `InfrastructureError` vs error funcional cubierto en tests del runner
- [ ] `ruff check src/executor/` exit 0
- [ ] `mypy --strict src/executor/` exit 0
