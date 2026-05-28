# U1 Executor Playwright — Code Generation Plan

## Unit Context
- **Tipo**: Brownfield — todos los archivos son NUEVOS (no existe src/executor/)
- **Workspace root**: `F:\Development_Projects\IA\06_testing_sintetico`
- **Stories cubiertas**: RF-04, RF-05, RF-06, RF-07, RF-08, RNF-02, RNF-03, RNF-04, RNF-07

## Dependencies
Requiere U0 completo (src/models.py debe existir).

## Steps

### Step 1: Crear `src/executor/__init__.py` [x]
- **Acción**: CREATE
- **Contenido**: export de `run_profile`

### Step 2: Crear `src/executor/profiles/__init__.py` [x]
- **Acción**: CREATE
- **Contenido**: instancias MOBILE_CO, DESKTOP_CO, MOBILE_MX + lista ALL_PROFILES

### Step 3: Crear `src/executor/profiles/mobile_co.py` [x]
- **Acción**: CREATE
- **Contenido**: `BrowserProfile(name="mobile_co", viewport_width=390, viewport_height=844, locale="es-CO", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15", is_mobile=True)`

### Step 4: Crear `src/executor/profiles/desktop_co.py` [x]
- **Acción**: CREATE
- **Contenido**: `BrowserProfile(name="desktop_co", viewport_width=1280, viewport_height=800, locale="es-CO", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", is_mobile=False)`

### Step 5: Crear `src/executor/profiles/mobile_mx.py` [x]
- **Acción**: CREATE
- **Contenido**: `BrowserProfile(name="mobile_mx", viewport_width=390, viewport_height=844, locale="es-MX", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15", is_mobile=True)`

### Step 6: Crear `src/executor/selectors.py` [x]
- **Acción**: CREATE
- **Contenido**: clase `SFCCSelectors` con todos los selectores CSS como constantes de clase; constantes TEST_CARD_* y DECLINED_CARD_*; TEST_SHIPPING dict

### Step 7: Crear `src/executor/flows/__init__.py` [x]
- **Acción**: CREATE
- **Contenido**: exports de `checkout_full_flow`, `checkout_card_declined_flow`

### Step 8: Crear `src/executor/flows/checkout_full.py` [x]
- **Acción**: CREATE
- **Contenido**: función `async checkout_full_flow(page, config) -> FlowResult` con 8 pasos usando `_execute_step`

### Step 9: Crear `src/executor/flows/checkout_card_declined.py` [x]
- **Acción**: CREATE
- **Contenido**: función `async checkout_card_declined_flow(page, config) -> FlowResult` con 7 pasos + verify_decline

### Step 10: Crear `src/executor/runner.py` [x]
- **Acción**: CREATE
- **Contenido**: `run_profile()`, `_create_context()`, `_take_screenshot()`, `_execute_step()`, `InfrastructureError`

### Step 11: Crear `tests/test_executor_profiles.py` [x]
- **Acción**: CREATE
- **Contenido**: tests que verifican campos de BrowserProfile sin lanzar browser; test ALL_PROFILES tiene 3 elementos

### Step 12: Crear `tests/test_executor_flows.py` [x]
- **Acción**: CREATE
- **Contenido**: tests con MagicMock de `Page` de Playwright; verifica que flows retornan FlowResult con orders_created=0; verifica que checkout_card_declined retorna success en verify_decline

### Step 13: Crear `tests/test_executor_runner.py` [x]
- **Acción**: CREATE
- **Contenido**: tests con mock de Playwright completo; verifica `run_profile` retorna ProfileResult; verifica que InfrastructureError se maneja correctamente

### Step 14: Crear `aidlc-docs/construction/u1/code/code-summary.md` [x]
- **Acción**: CREATE
- **Contenido**: Resumen de archivos creados

## Traceability

| RF/RNF | Steps |
|--------|-------|
| RF-04 (3 perfiles) | Steps 2–5 |
| RF-05 (selectores centralizados) | Step 6 |
| RF-06 (checkout_full) | Step 8 |
| RF-07 (checkout_card_declined) | Step 9 |
| RF-08 (FlowRunner + infrastructure_error) | Step 10 |
| RNF-02 (orders_created=0) | Steps 8, 9, 10 |
| RNF-03 (logging sin secretos) | Steps 8, 9, 10 |
| RNF-04 (manejo de errores seguro) | Step 10 |
| RNF-07 (timeout configurable, sin sleep) | Steps 8, 9, 10 |
