# Units of Work — TestPilot SFCC

> ⚠️ **Realineado 2026-06-03** (branch `rework/storefront-audit-scope`): se agregan las unidades **U5–U8**
> (flows de recorrido, auditoría, captura de red, ventana NL + modos) del alcance realineado — entrega en
> **ola 2**, detrás de la **puerta HITL de `specs/`** (cascade #6). Ver `../scope-realignment-brief.md` y
> `../requirements/requirements.md` (RF-21..RF-29). Las unidades U0–U4 y MD0 NO cambian su semántica.

## Modelo de descomposición

El sistema es un **monolito Python modular** (un único proceso FastAPI). Las "unidades de trabajo" son agrupaciones lógicas de módulos que pueden construirse y testearse de forma incremental. No son microservicios independientes.

**Versión enriquecida 2026-05-22**: cada unidad incluye Propósito de negocio, Stack tecnológico y referencias a las historias de usuario que la justifican (`inception/user-stories/user-stories.md`). Para gaps de diseño transversales ver: `env-vars-catalog.md`, `error-taxonomy.md`, `logging-strategy.md`.

---

## MD0 — Dashboard Web Interno

### Propósito de negocio
Interfaz web interna que permite al equipo de ingeniería **operar el sistema sin CLI**: registrar ambientes, configurar y lanzar runs, ver resultados en tiempo real e historial. Sin MD0, el sistema solo es accesible vía API — no cumple el objetivo de adopción del equipo no-técnico.

**Por qué importa**: materializa el **M19** del PRD (Dashboard Must Have) y el **MD0 módulo**. Es la superficie de acceso principal para Carolina y Andrés. El semáforo en pantalla reemplaza los 4–8h de QA manual con una vista de 30 segundos.

### Stack tecnológico
- **Frontend**: React (o HTML/JS + Fetch API — decisión pendiente de sprint 0)
- **Estilo**: Tailwind CSS o similar — no es prioridad visual, sí funcional
- **Backend**: Consume la API REST existente (`/v1/run`, `/v1/runs`)
- **Hosting**: Misma instancia FastAPI (archivos estáticos) o servidor separado — TBD

### Historias de usuario que cubre
- **H5.1** — Registro de ambientes con credenciales (solo paths en Secrets Manager, no valores)
- **H5.2** — Lanzamiento de run desde dashboard
- **H5.3** — Vista en tiempo real de agentes activos
- **H5.4** — Historial de ejecuciones con semáforo
- **H5.5** — *(★ 2026-06-03)* Matriz de ejecución **genérica** perfiles × flows (RF-29): derivada de los datos del run, sin hardcodear "checkout" ni asumir 2 flows; enlaza el documento de auditoría (U6) y distingue runs gate/exploratory; muestra runs restantes del día

### Componentes
- C-D0 DashboardApp (`src/dashboard/`)

### Archivos a crear
- [CREAR] `src/dashboard/index.html` (o React app)
- [CREAR] `src/dashboard/app.js` (lógica de frontend)

### Criterio de completitud
Un ingeniero puede registrar un ambiente, lanzar un run y ver el semáforo desde el browser sin tocar la CLI. H5.1–H5.4 AC satisfechos.

---

## U0 — Setup Base

### Propósito de negocio
Resolver la **deuda técnica heredada** (TD1, TD2, TD5) antes de construir lo nuevo: el repo tiene `SyntheticUserConfig` duplicada en dos módulos, no hay `pyproject.toml`, no hay imagen Docker, el modelo Claude está hardcoded a una versión obsoleta. Sin U0, U1–U4 no compilan de forma consistente ni se pueden empaquetar.

**Por qué importa**: habilita la **reproducibilidad del build** (RNF-10) y la **supply chain segura** (RNF-08): versiones pinned, imagen base verificada, modelo LLM actualizado. Sin esto, el equipo no puede garantizar que el reporte del miércoles use el mismo binario que el del lunes.

### Stack tecnológico
- **Lenguaje**: Python 3.12+
- **Validación**: Pydantic 2.9.2
- **Empaquetado**: `pyproject.toml` (PEP 621)
- **Calidad**: ruff (lint+format), mypy strict
- **Contenedor**: Docker, base `mcr.microsoft.com/playwright/python:v1.48.0-jammy`

### Historias de usuario que cubre
- **H0.1** — `SyntheticUserConfig` único punto de definición
- **H0.2** — Build reproducible y supply chain segura
- **H0.3** — Lint y type checking desde día 1

### Componentes
- `pyproject.toml` — dependencias pinned, ruff, mypy
- `src/models.py` — SyntheticUserConfig unificada + todos los modelos compartidos
- `src/agents/translator.py` — actualizar CLAUDE_MODEL + importar SyntheticUserConfig de src/models
- `src/api/main.py` — eliminar SyntheticUserConfig local, importar de src/models
- `Dockerfile` — imagen base Playwright

### Archivos a crear/modificar
- [CREAR] `pyproject.toml`
- [CREAR] `src/models.py`
- [CREAR] `Dockerfile`
- [MODIFICAR] `src/agents/translator.py`
- [MODIFICAR] `src/api/main.py`
- [MODIFICAR] `src/agents/__init__.py` (si cambia el import)

### Tests
- `tests/test_models.py` — validar que todos los modelos Pydantic crean correctamente
- Los tests existentes (`test_schemas.py`, `test_translator.py`) deben seguir pasando

### Criterio de completitud
`ruff check .` + `mypy src/` sin errores; todos los tests existentes pasan; AC1–AC4 de H0.1, AC1–AC4 de H0.2, AC1–AC3 de H0.3 satisfechos.

---

## U1 — Executor Playwright

### Propósito de negocio
Es **el corazón funcional** del producto: el módulo que **realmente ejecuta** los flujos de checkout en la tienda SFCC con browsers reales. Sin U1 no hay producto — todo lo demás (baseline, reporter, API) opera sobre los datos que U1 produce.

**Por qué importa**:
- Materializa el **Principio P1** (cero contaminación): `orders_created=0` invariante validado por `assert`.
- Materializa la **distinción infra-vs-tienda** (M17): un timeout de CDN es `YELLOW`, un selector roto es `RED`.
- Soporta el **caso central UC1** (validación pre-deploy de Carolina) y el **UC3** (flujo de tarjeta declinada).
- Cubre **3 perfiles × 2 flows = 6 ejecuciones paralelas** (M3, M4).

### Stack tecnológico
- **Lenguaje**: Python 3.12+ (async/await)
- **Browser automation**: Playwright 1.48.0 (`async_playwright()`)
- **Patrón**: closure `_step()` dentro de cada flow para mantener `steps` en scope local
- **Concurrencia**: paralelización a nivel de perfil — `asyncio.gather` con cap `MAX_CONCURRENT_PROFILES=3` (ver `env-vars-catalog.md`); orquestación final en U4
- **Anti-flake**: `wait_for_selector` / `wait_for_load_state` — prohibido `time.sleep` (BR-U1-05)
- **Storage**: screenshots a `SCREENSHOT_DIR` o S3, solo en fallo + paso final (ver `env-vars-catalog.md` y ADR-002)

### Historias de usuario que cubre
- **H1.1** — Ejecución paralela en 3 perfiles críticos
- **H1.2** — Cero contaminación de órdenes reales
- **H1.3** — Verificación explícita de mensaje de declinación
- **H1.4** — Distinción entre error de infra y bug de tienda
- **H1.5** — Disciplina de screenshots

### Componentes
- C1-A BrowserProfiles (`src/executor/profiles/`)
- C1-B SFCCSelectors (`src/executor/selectors.py`) — incluye `DECLINE_MESSAGE_PATTERN` regex (H1.3 AC2)
- C1-C CheckoutFullFlow (`src/executor/flows/checkout_full.py`)
- C1-D CheckoutCardDeclinedFlow (`src/executor/flows/checkout_card_declined.py`)
- C1-E FlowRunner (`src/executor/runner.py`)

### Archivos a crear
- [CREAR] `src/executor/__init__.py`
- [CREAR] `src/executor/profiles/__init__.py`
- [CREAR] `src/executor/profiles/mobile_co.py`
- [CREAR] `src/executor/profiles/desktop_co.py`
- [CREAR] `src/executor/profiles/desktop_ec.py`
- [CREAR] `src/executor/selectors.py`
- [CREAR] `src/executor/flows/__init__.py`
- [CREAR] `src/executor/flows/checkout_full.py`
- [CREAR] `src/executor/flows/checkout_card_declined.py`
- [CREAR] `src/executor/runner.py`

### Tests
- `tests/test_executor_profiles.py` — BrowserProfile fields correctos, sin lógica de ejecución
- `tests/test_executor_flows.py` — con mocks de Playwright Page
- `tests/test_executor_runner.py` — con mocks de Playwright, verifica `InfrastructureError` (ver `error-taxonomy.md`)

### Criterio de completitud
Tests pasan con mocks; `orders_created=0` en todos los flows; screenshots solo en fallo + paso final; perfiles: mobile/CO, desktop/CO, desktop/EC (Ecuador); H1.1–H1.5 AC satisfechos.

---

## U2 — Baseline Manager

### Propósito de negocio
Decide **cuándo un número es "lento"**. El producto tiene que distinguir un deploy que tarda 4.2 s en cargar la PDP (normal) de uno que tarda 6.8 s (regresión). Para eso necesita historia: U2 mantiene la ventana móvil de últimas 10 ejecuciones exitosas, calcula p95 y emite el **semáforo**.

**Por qué importa**:
- Es el corazón del **Principio P4** (honestidad del semáforo): nada de "verde por defecto" ni "rojo paranoico".
- Implementa el **bootstrap honesto**: durante las primeras 14 runs success NO se emiten alertas amarillas (M12).
- Sin U2, el **UC2** (detección de regresión de performance) no es posible.
- Soporta el **Journey 2** de Andrés (Tech Lead).

### Stack tecnológico
- **Lenguaje**: Python 3.12+ puro (sin async)
- **Patrón**: Protocol + implementación concreta (Strategy) — permite swap futuro a DynamoDB sin tocar U3/U4
- **Funciones puras**: `calculate_p95` y `compute_traffic_light` sin side effects → fácil de testear con PBT
- **Constantes**: `BOOTSTRAP_MIN_RUNS = 14`, `BASELINE_WINDOW = 10`, `YELLOW_THRESHOLD = 1.2`, `RED_THRESHOLD = 1.5`
- **Testing**: `hypothesis` para propiedades (monotonicidad de p95, idempotencia del bootstrap check)

### Historias de usuario que cubre
- **H2.1** — Alerta por regresión de performance
- **H2.2** — Bootstrap honesto (cero amarillos en primeras 14 corridas)
- **H2.3** — Consulta de histórico para tendencias (alcance MVP)
- **H2.4** — Solo runs success entran al p95
- **H2.5** — Baseline store swappable (Protocol pattern)

### Componentes
- C2-A BaselineStore (Protocol)
- C2-B InMemoryBaselineStore
- C2-C BaselineCalculator (funciones puras: `calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light`)

### Archivos a crear
- [CREAR] `src/baseline/__init__.py`
- [CREAR] `src/baseline/baseline_manager.py`

### Tests
- `tests/test_baseline_manager.py` — tests de ejemplo para casos específicos
- `tests/test_baseline_pbt.py` — tests de propiedad con hypothesis para `calculate_p95` y `compute_traffic_light`

### Criterio de completitud
Tests pasan; `bootstrap_mode=True` con <14 runs; semáforo never `YELLOW` en bootstrap; hypothesis tests pasan (PBT-02, PBT-03, PBT-07, PBT-09); H2.1–H2.5 AC satisfechos.

---

## U3 — Reporter

### Propósito de negocio
Convertir resultados crudos (`ProfileResult[]`) y la decisión del semáforo en **dos artefactos que un humano y un agente pueden leer**: un JSON estructurado (consumido por agentes CI/CD, UC4) y un Markdown con emojis (consumido por Carolina y Andrés en Slack/CLI).

**Por qué importa**:
- Cierra el loop del UC1: el output que Carolina ve en 30 segundos para aprobar el merge.
- Habilita el UC4 (agente CI/CD): el JSON sigue `specs/execution_report.schema.json` (additionalProperties: false) — contrato estable que el agente puede parsear sin sorpresas.
- Materializa **M7** (reporte dual JSON+Markdown) y **M8** (semáforo 3 estados visible).

### Stack tecnológico
- **Lenguaje**: Python 3.12+ síncrono
- **Serialización**: Pydantic → `model_dump(by_alias=True)` para camelCase
- **Patrón**: `traffic_light` del reporte = **peor** semáforo entre los 3 perfiles
- **Validación**: el dict producido se valida contra `specs/execution_report.schema.json` en tests (jsonschema lib)
- **PBT**: round-trip — para cualquier `ExecutionReport` válido, `to_markdown()` no lanza y `to_json_dict()` valida (PBT-08)

### Historias de usuario que cubre
- **H3.1** — Reporte Markdown legible en 30 segundos
- **H3.2** — JSON estable para agentes CI/CD
- **H3.3** — Auditabilidad de `orders_created=0` (renumerada desde H3.4)

**Nota**: la historia original H3.3 (clasificador LLM con `confidence`/`requires_human_review`, Journey 4 del PRD) fue **descartada del MVP** por decisión D7 — ver `inception/user-stories/coverage-matrix.md`. **Actualización 2026-06-03 (D14): D7 supersedida** — la capacidad regresa como agente de auditoría (sintetiza, no juzga — P7) en la unidad **U6**; el reporter integra/enlaza el documento de auditoría cuando existe (RF-10 realineado), pero el semáforo sigue siendo determinista.

### Componentes
- C3-A ReportGenerator
- C3-B MarkdownFormatter

### Archivos a crear
- [CREAR] `src/reporter/__init__.py`
- [CREAR] `src/reporter/report_generator.py`

### Tests
- `tests/test_reporter.py` — tests de ejemplo para reportes verde/amarillo/rojo/bootstrap
- Verificar que `ExecutionReport` pasa validación contra `specs/execution_report.schema.json`
- PBT round-trip: `ExecutionReport → to_markdown()` no lanza excepciones para cualquier input válido

### Criterio de completitud
Tests pasan; `orders_created=0` assertion en `generate_report`; reporte Markdown incluye sección destacada de semáforo y baseline; H3.1–H3.3 AC satisfechos.

---

## U4 — API Endpoints

### Propósito de negocio
Es la **superficie pública del producto**. Todo lo construido en U1–U3 solo es útil si Carolina (o un agente CI/CD) puede invocarlo vía HTTP. U4 integra todo, agrega autenticación, manejo de errores y los 3 endpoints públicos del MVP.

**Por qué importa**:
- Materializa **M1** (POST /v1/run completo, no stub) y **M2** (GET endpoints).
- Cumple **P2** (API versionada desde día 1 con `/v1/`).
- Cumple **P5** (autenticación de credenciales — `X-API-Key`).
- Es el punto donde la **versionabilidad del schema** (RF-13 / M16) se hace real: cualquier cambio en req/res es breaking.

### Stack tecnológico
- **Framework**: FastAPI 0.115.0
- **Async**: handlers async — necesario para coordinar `asyncio.gather` sobre los 3 perfiles (U1)
- **Auth**: API key vía header `X-API-Key`; lookup contra `TESTPILOT_API_KEY` (ver `env-vars-catalog.md`)
- **Validación**: Pydantic en request body — flow inválido → 422 automático
- **Errores**: ver `error-taxonomy.md` para mapeo completo
- **Logging**: ver `logging-strategy.md` (stdlib + JSONFormatter + redacción)
- **Tests**: `fastapi.testclient.TestClient` con `run_profile` mockeado

### Historias de usuario que cubre
- **H4.1** — Invocación con instrucción en lenguaje natural
- **H4.2** — Consulta del último run
- **H4.3** — Consulta por `run_id`
- **H4.4** — Autenticación por API key
- **H4.5** — Errores 500 sin stack traces (logging estructurado con redacción)

### Componentes
- C4-A APIRouter (expansión de `src/api/main.py`)

### Endpoints
| Método | Path | Comportamiento |
|---|---|---|
| POST | `/v1/run` | SyntheticUserConfig → resolve environment (Secrets Manager) → executor (3×2 paralelo) → baseline → reporter → 200 ExecutionReport |
| GET | `/v1/runs/{run_id}` | Recupera ExecutionReport por UUID; 404 si no existe |
| GET | `/v1/runs/latest` | Último report + `ageSeconds` + `ttlOk` (true si <14400s) |

### Archivos a modificar/crear
- [MODIFICAR] `src/api/main.py` — integración executor + baseline + reporter; GET endpoints; auth
- [CREAR] `tests/test_api.py` — tests de todos los endpoints con FastAPI TestClient

### Tests
- POST /v1/run con instrucción NL válida → 200 ExecutionReport completo
- POST /v1/run sin API key → 401
- GET /v1/runs/{run_id} con UUID existente → 200
- GET /v1/runs/{run_id} con UUID inexistente → 404 `run_not_found`
- GET /v1/runs/latest → 200 con `ageSeconds` y `ttlOk`
- GET /v1/runs/latest sin runs → 404 `no_runs_yet`
- Validaciones de input (instrucción inválida → 422 `translation_failed`)
- Run timeout → 504 `run_timeout`
- Unhandled exception → 500 `internal_error` sin stack trace

### Criterio de completitud
Todos los tests de API pasan; ningún endpoint retorna stack traces en errores; auth en todos los endpoints; H4.1–H4.5 AC satisfechos.

---

## U5 — Flows de Recorrido (★ realineación 2026-06-03 — ola 2)

> **Gate previo:** puerta HITL de `specs/` (extensión del enum `flows[]` + representación de `full_journey` — breaking change).

### Propósito de negocio
Restaura la ambición original del PRD: el recorrido de tienda (búsqueda/PLP, descuentos, PDP, carrito) como **pruebas propias**, no como pasos enterrados dentro del checkout. Habilita que el usuario elija el alcance: **un módulo, un subconjunto, o el recorrido completo** (`full_journey`). Sin U5, las 6 dimensiones de auditoría solo verían el camino del checkout.

**Por qué importa**: materializa **M20** y la decisión brief §7-#2. Alimenta con datos (precios por página, URLs) a los colectores de U6. El catálogo **sigue cerrado** (invariante #2): crece curado vía PR, nunca flows arbitrarios.

### Stack tecnológico
- **Lenguaje**: Python 3.12+ (async/await), Playwright 1.48.0 — mismo patrón `_step()` de U1
- **Catálogo**: registro declarativo de flows (`flow_catalog.py` o equivalente) — el despacho del runner pasa de if/else a lookup genérico; `full_journey` se declara aquí como **composición ordenada** (D15), NO como archivo flow
- **Precondiciones**: cada flow expone `setup()` determinista para modo módulo-único; en composición el estado (sesión, carrito) fluye entre flows y los `setup()` se omiten
- **Selectores**: grupos nuevos (`PLP`, `PROMOTIONS`) solo en `selectors.py` (C7)

### Historias de usuario que cubre
- **H6.1** — Catálogo de flows de recorrido (cerrado, modular)
- **H6.2** — Probar solo el módulo que me interesa (setup auto-preparado)
- **H6.3** — Recorrido completo como composición (`full_journey`)
- **H6.4** — Validación de productos con descuento

### Componentes
- C5-A SearchAndFilterFlow (`src/executor/flows/search_and_filter.py`)
- C5-B BrowseDiscountedProductsFlow (`src/executor/flows/browse_discounted_products.py`)
- C5-C PdpValidationFlow (`src/executor/flows/pdp_validation.py`)
- C5-D CartReviewFlow (`src/executor/flows/cart_review.py`)
- C5-E FlowCatalog (registro + composición `full_journey` + puntos críticos declarados por flow)
- [MODIFICAR] C1-E FlowRunner — despacho genérico + ejecución encadenada de composiciones
- [MODIFICAR] C1-B SFCCSelectors — grupos PLP/PROMOTIONS

### Tests
- `tests/test_journey_flows.py` — cada flow con mocks de Page: pasos, `setup()`, datos de precios emitidos
- `tests/test_flow_catalog.py` — composición `full_journey` correcta; flow fuera de catálogo rechazado; estado encadenado; `skipped` aguas abajo al fallar un eslabón
- Verificar que ningún flow de recorrido contiene pasos de pago (H6.1 AC2 — test estático sobre el catálogo)

### Criterio de completitud
H6.1–H6.4 AC satisfechos; despacho genérico en runner (cero if/else por flow); `full_journey` sin archivo propio; selectores solo en `selectors.py`; baseline por par perfil×flow arranca bootstrap propio para flows nuevos.

---

## U6 — Auditoría: Colectores + Agente de Síntesis (★ realineación 2026-06-03 — ola 2)

> **Gate previo:** puerta HITL de `specs/` (campos de auditoría en `execution_report.schema.json`). Depende de U7 (datos de red para la dimensión rendimiento).

### Propósito de negocio
Produce el **segundo entregable** del producto realineado: el documento de auditoría de 6 dimensiones legible para no-técnicos. Arquitectura en dos capas que hace cumplible **P7**: **colectores deterministas** (código, reproducible) generan los hallazgos; el **agente LLM** solo sintetiza y redacta sobre esos hallazgos — **nunca decide el semáforo** (C10).

**Por qué importa**: materializa **M21/MD13** y restaura J4 (D14): anomalías de comercio marcan `requires_human_review` por regla. Sin U6, el producto sigue siendo solo un smoke test de checkout.

### Stack tecnológico
- **Colectores**: Python determinista + listeners de Playwright (consola JS, requests fallidos) + axe-core inyectado en páginas clave (WCAG AA) — sin LLM
- **Agente**: Claude API vía el módulo de agente permitido (hoy `src/classifier/` — las llamadas LLM solo viven en `src/agents/` o `src/classifier/` per boundaries); input sanitizado (RNF-14), presupuesto de tokens acotado, timeout explícito
- **Evidencia**: captura dirigida por hallazgos (D16/RF-26) — naming `{paso}-{finding-{dim}|critical}.png`
- **Degradación**: si el LLM falla → reporte con hallazgos crudos + nota; el run nunca falla por el agente

### Historias de usuario que cubre
- **H7.1** — Colectores deterministas de las 6 dimensiones
- **H7.2** — Documento de auditoría legible para no-técnicos
- **H7.3** — El agente no juzga; anomalías escalan a humano (restaura J4)
- **H7.4** — Evidencia dirigida por hallazgos
- **H7.5** — Degradación con gracia del agente

### Componentes
- C6-A DimensionCollectors (integridad de comercio, locale, accesibilidad, salud del cliente, contenido; rendimiento deriva de U7) — ubicación: captura en `src/executor/`, ensamblaje en módulo de auditoría
- C6-B AuditAgent (`src/classifier/` — síntesis + categorización + `confidence`/`requires_human_review`)
- C6-C EvidencePolicy (captura por hallazgo + puntos críticos declarados en FlowCatalog)
- [MODIFICAR] C3-A ReportGenerator — integra/enlaza documento de auditoría

### Tests
- `tests/test_collectors.py` — cada colector con datos sintéticos: hallazgos estructurados correctos; fallo de colector degrada sin tumbar flow
- `tests/test_audit_agent.py` — con Claude mockeado: documento generado; sanitización del input (sin credenciales/cookies); excepción del LLM → reporte válido igual (H7.5 AC3)
- `tests/test_traffic_light_independence.py` — hallazgos con anomalía → YELLOW determinista; el output del agente no altera el semáforo (H7.3 AC4)
- `tests/test_evidence_policy.py` — capturas solo en fallo/final/hallazgo/punto crítico; nunca en paso OK limpio

### Criterio de completitud
H7.1–H7.5 AC satisfechos; C10 verificado por test (el LLM no puede mover el semáforo); presupuesto de evidencia dentro del KPI C4; documento legible validado con un lector no-técnico (Valentina proxy).

---

## U7 — Captura de Red / Performance (★ realineación 2026-06-03 — ola 2)

> **Gate previo:** puerta HITL de `specs/` (campos de red en `execution_report.schema.json`).

### Propósito de negocio
Da visibilidad de **dónde** se degrada el recorrido: timings de controllers SFRA, requests fallidos y Core Web Vitals por perfil. Es *user-perceived + network timing* — NO APM de backend. Alimenta la dimensión de rendimiento de U6 y responde la pregunta de Carolina: "¿qué endpoint degradó cuando el semáforo dio amarillo?".

**Por qué importa**: materializa **M22/MD14** (brief N1, decisión §7-#4). Las CWV (Google/SOASTA: -4.42% conversión por segundo extra mobile) son el lenguaje que negocio entiende.

### Stack tecnológico
- **Captura**: eventos de red de Playwright (request/response) filtrados por allowlist de dominios del storefront; metadata + timings, **sin bodies**
- **Redacción**: headers de auth y cookies redactados ANTES de persistir (mismo filtro D12)
- **CWV**: LCP/CLS/TTFB por página clave vía CDP/Performance API (INP/TBT solo si no infla el flow — RNF-15)
- **Agregación**: requests que matchean patrones de controllers SFRA (`*-Show`, `Cart-*`, `CheckoutServices-*`) → resumen de timings por controller
- **Storage**: HAR filtrado a S3 `{run_id}/{perfil}/{flujo}/network.har.json` (mismo lifecycle que evidencia); resumen en `ExecutionReport`

### Historias de usuario que cubre
- **H8.1** — Traza de red con timings de controllers SFRA
- **H8.2** — Core Web Vitals por página clave

### Componentes
- C7-A NetworkCapture (`src/executor/` — listeners + filtro allowlist + redacción)
- C7-B ControllerTimingAggregator (patrones SFRA → resumen p95 por controller)
- C7-C WebVitalsCollector (CWV por página clave, por perfil)
- [MODIFICAR] C3-A ReportGenerator — resumen de red en el reporte

### Tests
- `tests/test_network_capture.py` — con eventos mockeados: allowlist aplica; headers/cookies redactados; bodies ausentes
- `tests/test_controller_timings.py` — patrones SFRA agregan correctamente; URLs no-controller quedan fuera del resumen
- `tests/test_web_vitals.py` — métricas presentes por perfil; flujo no falla si una métrica no está disponible

### Criterio de completitud
H8.1–H8.2 AC satisfechos; overhead de captura ≤ ~10% del tiempo del flow (RNF-15); cero credenciales en HAR persistido (verificado por test); baseline sigue sobre `durationMs` (extensión a CWV declarada ola posterior).

---

## U8 — Ventana NL + Modos de Operación (★ realineación 2026-06-03 — ola 2)

> **Gate previo:** puerta HITL de `specs/` (campo `mode` + contrato del endpoint de traducción).

### Propósito de negocio
Abre el producto a **usuarios no-técnicos** (Valentina — QA/PM/negocio): describir la prueba en español, ver el preview de lo que se va a ejecutar, confirmar, y leer el documento de auditoría. Además separa formalmente los modos **gate** (determinista, entra a baseline, veredicto de deploy) y **exploratorio** (descubrimiento, nunca contamina el baseline — C11).

**Por qué importa**: materializa **M23/UC6** (D18). El contrato de `POST /v1/run` NO cambia (D8 intacta): la NL se traduce y valida ANTES, y nunca llega al executor (C12). KPI A5: ≥1 usuario no-técnico lanzando pruebas en semana 4 post-ola.

### Stack tecnológico
- **Traducción**: `src/agents/translator.py` promovido a componente principal de UX — Claude API con validación estricta post-traducción (JSON Schema + catálogo cerrado), `CLAUDE_MODEL` vigente
- **Endpoint**: traducción dedicada (p.ej. `POST /v1/translate`) que retorna config propuesto + explicación legible — **sin ejecutar**; el run requiere confirmación y `POST /v1/run` con payload estructurado
- **Seguridad**: NL ≤2000 chars; resistencia prompt-injection (RT1, Q8=0); intentos rechazados loggeados; gate D-NL (Q1≥90%, Q2=100%) pre-lanzamiento
- **Modos**: `mode: gate|exploratory` en `SyntheticUserConfig` (default `gate`); `save_run` filtra por modo; `/v1/runs/latest` para deploy considera solo gate
- **UI**: campo NL como vía principal en MD0 P2 (JSON queda como vía avanzada)

### Historias de usuario que cubre
- **H9.1** — Valentina lanza una prueba describiéndola en español
- **H9.2** — Traducción estricta: ambigüedad y prompt injection
- **H9.3** — Modo exploratorio sin contaminar el baseline

### Componentes
- C8-A TranslateEndpoint (`src/api/` — traducir + preview, sin ejecutar)
- C8-B NLWindow (MD0 P2 — campo NL + preview + confirmación)
- [MODIFICAR] `src/agents/translator.py` — catálogo extendido, mapeo de alcance (módulo único / subconjunto / `full_journey`), clarificación de ambigüedad
- [MODIFICAR] C2-x BaselineStore — filtro por `mode` en `save_run`
- [MODIFICAR] C4-A APIRouter — campo `mode`; `latest` solo gate

### Tests
- `tests/test_translate_endpoint.py` — con Claude mockeado: config válido + explicación; ambigüedad → clarificación; fuera de catálogo → rechazo con catálogo disponible; NL >2000 chars → 422
- `tests/test_prompt_injection.py` — suite RT1 (5 escenarios): 100% bloqueados
- `tests/test_modes.py` — exploratory nunca en baseline; `latest` ignora exploratory; cap 10/día suma ambos modos

### Criterio de completitud
H9.1–H9.3 AC satisfechos; la NL jamás llega al executor (C12 verificado: el executor no importa el translator); gates de calidad D-NL cumplidos; reporte exploratorio marcado visiblemente.

---

## Referencias cruzadas

| Tema | Documento |
|---|---|
| Historias de usuario completas (40 historias, 157 ACs — iteración 3) | `inception/user-stories/user-stories.md` |
| Requisitos realineados (RF-21..RF-29, RNF-14..RNF-15, C10..C12) | `inception/requirements/requirements.md` |
| Brief de realineación de alcance (decisiones §7) | `inception/scope-realignment-brief.md` |
| Cobertura MoSCoW + Journeys + UCs | `inception/user-stories/coverage-matrix.md` |
| Catálogo de env vars | `inception/application-design/env-vars-catalog.md` |
| Taxonomía de errores (HTTP codes + status enums + TrafficLight) | `inception/application-design/error-taxonomy.md` |
| Estrategia de logging + redacción de secretos | `inception/application-design/logging-strategy.md` |
| Dependencias entre componentes | `inception/application-design/component-dependency.md` |
| Dependencias entre unidades | `inception/application-design/unit-of-work-dependency.md` |
| Mapa RF/RNF → Unidad | `inception/application-design/unit-of-work-story-map.md` |
