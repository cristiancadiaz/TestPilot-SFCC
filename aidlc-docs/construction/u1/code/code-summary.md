# Code Summary — U1 Executor Playwright

## Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `src/executor/__init__.py` | Export de `run_profile` |
| `src/executor/_core.py` | `InfrastructureError`, `execute_step`, `take_screenshot` |
| `src/executor/profiles/__init__.py` | `MOBILE_CO`, `DESKTOP_CO`, `MOBILE_MX`, `ALL_PROFILES` |
| `src/executor/profiles/mobile_co.py` | Perfil iPhone 390×844 es-CO |
| `src/executor/profiles/desktop_co.py` | Perfil desktop 1280×800 es-CO |
| `src/executor/profiles/mobile_mx.py` | Perfil iPhone 390×844 es-MX |
| `src/executor/selectors.py` | Todos los selectores CSS y datos de prueba |
| `src/executor/flows/__init__.py` | Exports de flows |
| `src/executor/flows/checkout_full.py` | Flow de 8 pasos, checkout exitoso |
| `src/executor/flows/checkout_card_declined.py` | Flow de 8 pasos, tarjeta declinada |
| `src/executor/runner.py` | Entry point `run_profile()` |
| `tests/test_executor_profiles.py` | 6 tests de perfiles (sin browser) |
| `tests/test_executor_flows.py` | 9 tests de flows con mocks de Page |
| `tests/test_executor_runner.py` | 3 tests de runner con mocks de Playwright |

## Decisiones relevantes

- `_core.py` separa las utilidades compartidas para evitar dependencia circular (flows ← _core → NO runner)
- Patrón `_step()` closure dentro de cada flow: simplifica la firma y mantiene `steps` en scope local
- `InfrastructureError` solo se lanza en `navigate_home` (timeout de red) — pasos posteriores son errores de app
- `orders_created` validado con `assert` en `runner.py` antes de retornar `ProfileResult`
- Screenshots: `take_screenshot` en `_core.py` usa `SCREENSHOT_DIR` env var (default `/tmp/...`)
- `run_profile` usa `async with async_playwright()` para limpieza garantizada del browser

## Reglas aplicadas

- BR-U1-04: screenshots solo en `is_final=True` o step fallido
- BR-U1-05: sin `time.sleep()` — todo usa `wait_for_selector` o `wait_for_load_state`
- BR-U1-07: todos los selectores en `selectors.py`
- BR-U1-08: `InfrastructureError` vs app error diferenciados
- RNF-02: `orders_created=0` invariante con `assert`
