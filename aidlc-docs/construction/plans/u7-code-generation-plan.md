# U7 Captura de Red / Performance — Code Generation Plan

> ★ Realineación 2026-06-03 — ola 2. Prerrequisitos: U1 completo + `specs/execution_report.schema.json` v2 (HECHO). Paralelizable con U5 y U8.

## Unit Context
- **Tipo**: Brownfield — extiende `src/executor/` y `src/reporter/`
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Stories cubiertas**: H8.1, H8.2 — RF-23, RNF-15
- **Restricciones**: user-perceived + network timing, NO APM backend · metadata+timings sin bodies · redacción pre-persistencia · overhead ≤ ~10% (RNF-15)

## Dependencies
Requiere U1 (runner lanza el browser donde se instalan los listeners). U6 consume su output (NetworkSummary).

## Steps

### Step 1: Crear `src/executor/network_capture.py` [ ]
- **Acción**: CREATE
- **Contenido**: clase `NetworkCapture` — listeners `page.on("request"/"response")`; filtro por `DOMAIN_ALLOWLIST` (derivada de `env.store_url`); por request: URL (sin query de credenciales), método, status, resource_type, timings, tamaño; NUNCA bodies; `to_har_dict()` con redacción de headers de auth/cookies (reusa filtro D12)

### Step 2: Crear `src/executor/controller_timings.py` [ ]
- **Acción**: CREATE
- **Contenido**: `SFRA_CONTROLLER_PATTERNS` (regex: `\w+-Show`, `Cart-\w+`, `CheckoutServices-\w+`, `Search-\w+`, `Product-\w+`...); `aggregate_controllers(requests) -> list[ControllerTiming]` con count y p95_ms por patrón

### Step 3: Crear `src/executor/web_vitals.py` [ ]
- **Acción**: CREATE
- **Contenido**: `collect_web_vitals(page) -> WebVitals | None` — LCP/CLS vía PerformanceObserver inyectado, TTFB vía Navigation Timing API; en páginas clave del flow (definidas en FlowCatalog); retorna None sin fallar si no se puede capturar (H8.2 AC + RNF-15)

### Step 4: Modificar `src/models.py` — modelos de red [ ]
- **Acción**: MODIFY
- **Contenido**: `NetworkSummary`, `ControllerTiming`, `WebVitals` (espejo de `$defs` del schema v2); `ProfileResult.network_summary: NetworkSummary | None`

### Step 5: Modificar `src/executor/runner.py` — integrar captura [ ]
- **Acción**: MODIFY
- **Contenido**: `run_profile()` instala `NetworkCapture` al crear el contexto; al finalizar el flow: agrega controllers, captura web vitals de páginas clave, sube HAR filtrado a `{run_id}/{perfil}/{flujo}/network.har.json` (S3 o `SCREENSHOT_DIR` local), adjunta `NetworkSummary` al `ProfileResult`

### Step 6: Modificar `src/reporter/report_generator.py` — resumen de red [ ]
- **Acción**: MODIFY
- **Contenido**: `to_markdown()` agrega sección de red por perfil (requests fallidos, top controllers por p95, CWV); `to_json_dict()` serializa `network_summary` validando contra schema v2

### Step 7: Crear `tests/test_network_capture.py` [ ]
- **Acción**: CREATE
- **Contenido**: con eventos mockeados — allowlist excluye dominios terceros; headers `Authorization`/`Cookie` redactados en `to_har_dict()`; cero bodies en el HAR; query params con patrones de credencial redactados

### Step 8: Crear `tests/test_controller_timings.py` [ ]
- **Acción**: CREATE
- **Contenido**: URLs de controllers SFRA agregan correctamente (count, p95); URLs de assets/no-controller quedan fuera; p95 coherente con `calculate_p95` de U2

### Step 9: Crear `tests/test_web_vitals.py` [ ]
- **Acción**: CREATE
- **Contenido**: page mock con métricas → WebVitals poblado; page mock sin soporte → None sin excepción; flujo completo no falla cuando web vitals es None

## Validation
- `ruff check .` + `mypy src/` sin errores
- Tests de U7 verdes; reporte con `network_summary` valida contra `specs/execution_report.schema.json` v2
- Test de redacción: cero valores tipo credencial en HAR persistido (RNF-15 — blocking)
- Criterio de completitud de unit-of-work.md U7 satisfecho (H8.1–H8.2 AC)
