# Units of Work — TestPilot SFCC

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
- **Storage**: screenshots a `SCREENSHOT_DIR` (ver `env-vars-catalog.md`)

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
Tests pasan con mocks; `orders_created=0` en todos los flows; screenshots en todos los módulos según flags `screenshot_on_success`/`screenshot_on_error`; perfiles: mobile/CO, desktop/CO, desktop/EC (Ecuador); H1.1–H1.5 AC satisfechos.

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
- Habilita el UC4 (agente CI/CD): el JSON sigue `specs/execution_report.json` (additionalProperties: false) — contrato estable que el agente puede parsear sin sorpresas.
- Materializa **M7** (reporte dual JSON+Markdown) y **M8** (semáforo 3 estados visible).

### Stack tecnológico
- **Lenguaje**: Python 3.12+ síncrono
- **Serialización**: Pydantic → `model_dump(by_alias=True)` para camelCase
- **Patrón**: `traffic_light` del reporte = **peor** semáforo entre los 3 perfiles
- **Validación**: el dict producido se valida contra `specs/execution_report.json` en tests (jsonschema lib)
- **PBT**: round-trip — para cualquier `ExecutionReport` válido, `to_markdown()` no lanza y `to_json_dict()` valida (PBT-08)

### Historias de usuario que cubre
- **H3.1** — Reporte Markdown legible en 30 segundos
- **H3.2** — JSON estable para agentes CI/CD
- **H3.3** — Auditabilidad de `orders_created=0` (renumerada desde H3.4)

**Nota**: la historia original H3.3 (clasificador LLM con `confidence`/`requires_human_review`, Journey 4 del PRD) fue **descartada del MVP** por decisión D7 — ver `inception/user-stories/coverage-matrix.md`.

### Componentes
- C3-A ReportGenerator
- C3-B MarkdownFormatter

### Archivos a crear
- [CREAR] `src/reporter/__init__.py`
- [CREAR] `src/reporter/report_generator.py`

### Tests
- `tests/test_reporter.py` — tests de ejemplo para reportes verde/amarillo/rojo/bootstrap
- Verificar que `ExecutionReport` pasa validación contra `specs/execution_report.json`
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

## Referencias cruzadas

| Tema | Documento |
|---|---|
| Historias de usuario completas (21 historias, 83 ACs) | `inception/user-stories/user-stories.md` |
| Cobertura MoSCoW + Journeys + UCs | `inception/user-stories/coverage-matrix.md` |
| Catálogo de env vars | `inception/application-design/env-vars-catalog.md` |
| Taxonomía de errores (HTTP codes + status enums + TrafficLight) | `inception/application-design/error-taxonomy.md` |
| Estrategia de logging + redacción de secretos | `inception/application-design/logging-strategy.md` |
| Dependencias entre componentes | `inception/application-design/component-dependency.md` |
| Dependencias entre unidades | `inception/application-design/unit-of-work-dependency.md` |
| Mapa RF/RNF → Unidad | `inception/application-design/unit-of-work-story-map.md` |
