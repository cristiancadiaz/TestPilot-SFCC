# Build Sequence — TestPilot SFCC Construction Phase (actualizado 2026-05-24)

## Propósito

Documentar el orden recomendado de construcción de las 6 unidades (MD0 + U0 a U4), sus dependencias y gates de promoción.

**Estado:** este documento define el plan. La implementación de código está pendiente.

---

## Dependencias entre unidades

```
                    ┌──────────┐
                    │ U0       │  Setup Base (modelos compartidos + Dockerfile)
                    │ Setup    │
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌──────────┐
   │ U1      │     │ U2       │     │ MD0      │
   │ Executor│     │ Baseline │     │ Dashboard│
   └────┬────┘     └────┬─────┘     └────┬─────┘
        │               │                 │
        └───────┬───────┘                 │
                ▼                         │
           ┌─────────┐                    │
           │ U3      │                    │
           │ Reporter│                    │
           └────┬────┘                    │
                │                         │
                ▼                         │
           ┌─────────┐                    │
           │ U4      │◄───────────────────┘  (MD0 consume API de U4)
           │ API     │
           └─────────┘
```

**Lecturas clave:**
- U0 es prerequisito de TODO.
- U1, U2 pueden construirse en paralelo (no dependen entre sí).
- MD0 puede construirse en paralelo (consume API de U4 pero se desarrolla con mocks hasta que U4 esté listo).
- U3 depende de U1 + U2.
- U4 integra todo y depende de U1 + U2 + U3.

---

## Orden recomendado (secuencial conservador)

### Sprint 0 — Fundación
1. **U0 Setup Base** (1-2 días)
   - Crear `src/models.py` con todos los modelos (incluyendo EnvironmentConfig, ResolvedEnvironment, credenciales).
   - Crear `pyproject.toml` con dependencias pinned.
   - Crear `Dockerfile` multi-stage (Node builder + Python runtime).
   - Actualizar `src/agents/translator.py` (modelo Claude + import desde src.models).
   - Tests: `tests/test_models.py` + actualizar `tests/test_schemas.py` y `tests/test_translator.py`.
   - **Gate:** `pytest` pasa, `ruff check` limpio, `mypy --strict` limpio, `docker build` funciona.

### Sprint 1 — Núcleo funcional
2. **U2 Baseline Manager** (1 día)
   - Funciones puras: `calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light`.
   - `InMemoryBaselineStore` con clave compuesta `(environment_id, profile, flow)`.
   - Método `list_runs` paginado.
   - Tests PBT bloqueantes (PBT-02, 03, 07, 09).
   - **Gate:** todos los tests PBT pasan con `hypothesis`.

3. **U1 Executor Playwright** (3-4 días, paralelizable con U2)
   - Submódulo `profiles/` con 3 perfiles (mobile-co, desktop-co, desktop-ec).
   - `selectors.py` con todas las categorías (incluyendo LOGIN_*).
   - Submódulo `auth/shopper_login.py`.
   - Submódulo `flows/` con `checkout_full.py` y `checkout_card_declined.py` (10 pasos cada uno).
   - `runner.py` con `run_profile`.
   - Tests con mocks de Playwright.
   - **Gate:** tests pasan, distinción InfraError vs app error cubierta, invariante `orders_created=0` verificado.

### Sprint 2 — Reporte e integración
4. **U3 Reporter** (1 día — depende de U1 + U2)
   - `generate_report`, `to_json_dict`, `to_markdown` en `src/reporter/report_generator.py`.
   - Validación contra `specs/execution_report.schema.json`.
   - Tests para casos verde/amarillo/rojo/bootstrap + error.
   - **Gate:** JSON valida contra schema, PBT round-trip para Markdown.

5. **U4 API Endpoints** (5-7 días — la unidad más grande)
   - Servicios: EnvironmentRegistry, EnvironmentResolver, SecretsManagerClient, RunOrchestrator, LiveStatusTracker.
   - Routers: health, environments, runs, screenshots.
   - Middlewares: SecurityHeadersMiddleware, RequestLoggingMiddleware.
   - Exception handlers.
   - Tests por endpoint con FastAPI TestClient.
   - **Gate:** todos los endpoints retornan códigos HTTP correctos, sin stack traces, auth obligatoria, healthcheck verifica dependencias.

### Sprint 2-3 — Frontend (paralelo a U4)
6. **MD0 Dashboard** (3-5 días — paralelizable con U4 usando mocks)
   - Setup Vite + React + TS + Tailwind.
   - Componentes core: `<TrafficLight>`, `<ScreenshotThumbnail>`, `usePolling`, `ApiClient`.
   - 5 pantallas: P1 Environments, P2 NewRun, P3 LiveRun, P4 RunDetail, P5 History.
   - Tests con Vitest + React Testing Library.
   - Integración con backend (cuando U4 listo): proxy en dev, mismo origen en prod.
   - **Gate:** dashboard usable end-to-end contra backend real con un ambiente registrado y un run lanzado.

---

## Orden alternativo (paralelo agresivo, requiere coordinación)

Si hay 4+ devs disponibles:
- **Día 1-2 (en serie):** U0
- **Día 3-7 (en paralelo):** U1, U2, MD0 (mocks)
- **Día 8-9:** U3 (necesita U1+U2)
- **Día 10-15 (en paralelo):** U4 (integra) + MD0 (conecta a U4 real)

**Ahorro:** ~3-5 días vs secuencial. **Riesgo:** más coordinación, más merge conflicts en `src/models.py`.

**Recomendación PO:** secuencial conservador en sprint 0, paralelo en sprint 1+.

---

## Gates de promoción entre unidades

### Gate 1 — Tras U0 (ejecutado 2026-06-06, TASK-006)
- [x] `pip install -e ".[dev]"` sin errores — vía `docker build` (capa `pip install -e .`)
- [x] `ruff check src/` exit 0 — `ruff check .` All checks passed
- [x] `mypy --strict src/` exit 0 — no issues in 2 source files
- [x] `pytest tests/` exit 0 — 20 passed
- [x] `pip-audit` sin HIGH/CRITICAL — No known vulnerabilities found tras el bump de seguridad HITL (starlette→1.2.1, fastapi→0.136.3, pytest→9.0.3); ver `u0/code/code-summary.md`.
- [x] `docker build .` exit 0 — imagen `testpilot-sfcc:local` (985 MB)
- [N/A] Imagen ejecuta y responde `/v1/run` con 422 — sin API en U0 (se valida tras U4)

### Gate 2 — Tras U2 ✅ (2026-06-08)
- [x] Tests PBT pasan (PBT-02, 03, 07, 09) — 37 tests (incl. PBT-02/03/07/08/09) verde
- [x] `InMemoryBaselineStore` separa runs por ambiente correctamente — `test_store_separates_by_environment_id`
- [x] `compute_traffic_light` con bootstrap=True nunca YELLOW — PBT-09 (200 ejemplos)

### Gate 3 — Tras U1 ✅ (2026-06-08)
- [x] Tests pasan con mocks de Playwright — suite executor verde
- [x] `orders_created=0` asserted — `test_checkout_full_orders_created_zero`, `test_checkout_card_declined_orders_created_zero`, assert guard en runner
- [x] Disciplina de screenshots respeta flags — `test_checkout_full_screenshot_policy`
- [x] 3 perfiles instanciados correctamente (incluyendo desktop-ec) — `test_all_profiles_has_exactly_3`, `test_desktop_ec_fields`
- [x] env_access vía http_credentials funciona en test — `test_env_access_passed_as_http_credentials`
- [x] shopper_login form encapsulado y testeable — `tests/test_executor_auth.py`

### Gate 4 — Tras U3 ✅ (2026-06-08)
- [x] JSON output valida contra `specs/execution_report.schema.json` — Draft 2020-12, casos green/yellow/red/bootstrap/failed/error + multi-perfil
- [x] Markdown legible en CLI — `test_markdown_contains_verdict_and_invariant_line`
- [x] Invariante orders_created=0 enforced — assert en `generate_report` + ausente del JSON + línea en Markdown
- [x] Baseline consultado con environment_id (no se mezclan ambientes) — `test_baseline_queried_with_run_environment`
- [x] ruff + mypy --strict exit 0; suite completa 110 tests verde

### Gate 5 — Tras U4 ✅ (2026-06-08)
- [x] Todos los endpoints documentados retornan códigos correctos — `test_api_*` + `test_error_taxonomy`
- [x] Sin stack traces en responses — `test_500_internal_error_no_stack_trace_leak`
- [x] Auth obligatoria — `verify_api_key` en todos los `/v1/*`; tests 401
- [x] `/health` retorna 503 si dependencias caen — `test_health_503_when_probe_fails`
- [x] CRUD de environments funciona contra el store (fake in-memory; **adapter DynamoDB tras el mismo Protocol diferido a infra — D-U4-1**)
- [x] LiveStatusTracker se actualiza durante runs paralelos — `test_run_status_after_run`
- [x] Historial paginado con filtros — `test_list_runs_*`

### Gate 6 — Tras MD0 ⟳ (código completo 2026-06-08; cierre pleno tras integración U4)
- [x] Dashboard accesible en `/` — SPA con 5 rutas; `pnpm build` (tsc strict + vite) verde
- [ ] CSP headers presentes — **pendiente**: capa de servido (no hay meta CSP en index.html); se define al desplegar/integrar U4
- [~] 5 pantallas funcionales contra backend — 5 pantallas funcionan contra `mock-server.ts`; "contra backend real" pendiente de U4
- [x] Polling 3s funcionando en P3 — `usePolling.test.tsx`
- [x] Sin credenciales en console/network del browser — `ApiClient` redacta; cubierto en tests
- [ ] Lighthouse score básico ≥80 — **pendiente**: requiere pasada de performance (post-integración)

> Nota: MD0 generación de código COMPLETA (build+tsc+lint+37 tests verde, 2026-06-08). Gate 6 cierra plenamente cuando MD0 conecta a la API real de U4 (CSP + 5 pantallas contra backend) y se corre Lighthouse.

### Gate Final — Sistema completo
- [ ] Un ingeniero puede registrar un ambiente desde el dashboard
- [ ] Un ingeniero puede lanzar un run desde el dashboard
- [ ] El dashboard muestra estado en vivo
- [ ] Al completar, dashboard navega a detalle con semáforo
- [ ] Historial muestra el run
- [ ] `orders_created=0` verificado end-to-end

---

## Build and Test (placeholder)

El detalle de instrucciones de build y test se generará en una fase separada (Build and Test stage del workflow AI-DLC) tras aprobar este plan de Construction. Por ahora solo se documenta el plan; las instrucciones de cómo ejecutar tests en cada gate se generan junto con el código.

---

## Resumen

| Sprint | Unidades | Días estimados | Dependencias |
|---|---|---|---|
| 0 | U0 | 1-2 | — |
| 1 | U1 + U2 (paralelo) | 4-5 | U0 |
| 2 | U3 + U4 (U3 primero) | 6-8 | U1, U2 |
| 2-3 | MD0 | 3-5 | (paralelo con U4, integración con U4 real) |
| **Total** | 6 unidades | **~14-20 días-persona** | — |

Con 2-3 devs trabajando en paralelo en sprints 1-2: **~3-4 semanas calendario** hasta sistema completo end-to-end.

---

## Ola 2 — Realineación de alcance (agregado 2026-06-03)

> Origen: `inception/scope-realignment-brief.md`. Prerrequisito CUMPLIDO: `specs/` v2 (HITL aprobado 2026-06-03).
> Alcance fijo — estas unidades NO son recortables; el tiempo es la variable de ajuste.

### Dependencias ola 2

```
   (ola 1 completa: U0..U4 + MD0)
                │
   ═══ PUERTA HITL specs/ v2 — ✅ APROBADA 2026-06-03 ═══
                │
   ┌────────────┼──────────────┐
   ▼            ▼              ▼
┌──────┐   ┌──────────┐   ┌──────────┐
│ U5   │   │ U7       │   │ U8       │   (paralelo)
│ Flows│   │ Red/Perf │   │ NL+Modos │
└──┬───┘   └────┬─────┘   └────┬─────┘
   └─────┬──────┘              │
         ▼                     │
   ┌───────────┐               │
   │ U6        │               │
   │ Auditoría │               │
   └─────┬─────┘               │
         └──── integración ────┘   (documento de auditoría en MD0 — checkpoint 6)
```

### Gates de promoción ola 2

**Gate U5 → listo:** despacho genérico (cero if/else por flow) · `full_journey` sin archivo propio · ningún flow de recorrido toca pago (test estático) · tests de composición verdes.

**Gate U7 → listo:** HAR sin credenciales ni bodies (test de redacción) · overhead ≤ ~10% · `network_summary` valida contra schema v2.

**Gate U8 → listo:** suite RT1 100% bloqueada (Q8=0) · executor sin import del translator (C12, grep) · exploratorios fuera del baseline y de latest-gate (C11) · gates D-NL (Q1≥90%, Q2=100%).

**Gate U6 → listo:** test de independencia del semáforo (C10 — el agente no puede mover el veredicto) · degradación con gracia (Claude mockeado a excepción → reporte válido) · run limpio = solo fail+final (ADR-003) · documento legible para no-técnico (revisión humana).

**Checkpoint 6 (e2e final):** Valentina describe la prueba en NL → preview → confirma → matriz genérica en vivo → documento de auditoría con evidencia enlazada → run exploratorio ausente del baseline.

### Resumen ola 2

| Sprint | Unidades | Días estimados | Dependencias |
|---|---|---|---|
| 4 | U5 + U7 + U8 (paralelo) | 4-6 | ola 1 + specs v2 ✅ |
| 5 | U6 | 3-4 | U5, U7 |
| 5 | Integración + checkpoint 6 | 1-2 | U6, U8 |
| **Total ola 2** | 4 unidades | **~8-12 días-persona** | — |
