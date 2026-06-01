# Requirements Document — TestPilot SFCC

## Intent Analysis Summary

| Campo | Valor |
|-------|-------|
| **User Request** | Construir plataforma interna de testing continuo con usuarios sintéticos para SFCC/SFRA vía Playwright; reemplazar 4–8h de QA manual con gate de deploy automatizado en <30 min |
| **Request Type** | New Project (brownfield expansion — ~30% del MVP ya implementado) |
| **Scope** | System-wide — 4 módulos nuevos + refactor de modelos + setup de proyecto + endpoints GET |
| **Complexity** | Complex — LLM integration, Playwright automation, DynamoDB baseline, multi-profile orchestration |
| **Depth** | Comprehensive |

---

## Alcance de esta sesión (decisiones de implementación)

| Decisión | Elección | Razón |
|----------|----------|-------|
| Módulos a construir | executor + baseline + reporter (+ deuda técnica) | Cubre demo funcional semana 4 sin sobrecargar el sprint |
| Infraestructura AWS | Stubs locales (sin CDK) | Permite validar lógica antes de integrar cloud |
| Entorno Playwright | Docker imagen oficial Playwright | Paridad con producción ECS Fargate desde el inicio |
| Storefront SFCC | Selectores parametrizados sin staging real | Desacopla la arquitectura del acceso a staging |
| Dependencias | pyproject.toml completo | Base para ruff, mypy y build Docker reproducible |
| Modelo Claude | claude-haiku-4-5-20251001 | Versión soportada; evita deprecated model en producción |
| SyntheticUserConfig | Mover a src/models.py | Previene duplicación antes de agregar nuevos módulos |
| Security Extension | Habilitada (blocking) | Herramienta de producción con credenciales y storefront real |
| PBT Extension | Parcial (PBT-02,03,07,08,09) | Lógica p95 y semáforo tienen invariantes verificables |

---

## Requisitos Funcionales

### RF-01: Configuración de Proyecto (pyproject.toml)
- **Descripción**: El proyecto debe tener un `pyproject.toml` con dependencias pinned, configuración de ruff (formato + linting con reglas E,F,I,UP) y mypy (--strict).
- **Criterios de aceptación**:
  - `pyproject.toml` existe en el workspace root con todas las dependencias del proyecto
  - `ruff format .` y `ruff check .` se ejecutan sin errores en el codebase existente
  - `mypy src/` se ejecuta sin errores de tipo en el codebase existente
  - Las dependencias incluyen: fastapi, uvicorn, pydantic, anthropic, jsonschema, playwright, boto3, pytest, hypothesis
- **Módulo**: Workspace root

### RF-02: Modelos Compartidos (src/models.py)
- **Descripción**: `SyntheticUserConfig` y otros modelos Pydantic compartidos deben vivir en un único módulo `src/models.py` para evitar duplicación. Incluye también los modelos del nuevo modelo de credenciales duales y del Environment Registry.
- **Criterios de aceptación**:
  - AC1. `src/models.py` define `SyntheticUserConfig` como la única fuente de verdad
  - AC2. `src/api/main.py` importa `SyntheticUserConfig` desde `src/models`
  - AC3. Los campos de `SyntheticUserConfig` son: `environment_id` (enum: `sandbox|development|staging`), `products[]` (array con `search_term` + `validate_variant`), `flows[]` (array enum closed: `checkout_full`, `checkout_card_declined`), `profiles[]` (array enum closed: `mobile_co`, `desktop_co`, `desktop_ec`) y `capture_intermediate_screenshots` (bool, siempre `false` en MVP). Los campos `storefrontUrl`, `email`, `password`, `screenshot_on_success` y `screenshot_on_error` NO existen en `SyntheticUserConfig`.
  - AC4. `src/agents/translator.py` importa `SyntheticUserConfig` desde `src/models` (translator queda como funcionalidad opcional — no es entrada principal de runs).
  - AC5. `src/models.py` también define: `EnvironmentConfig`, `EnvironmentAccessCredentials`, `ShopperCredentials`, `ResolvedEnvironment`, `RunStatus`, `ProfileLiveStatus`, `RunState`.
  - AC6. Todos los tests existentes pasan sin modificación de lógica (actualizando solo los mocks afectados por el cambio de payload).
- **Módulo**: src/models.py

### RF-03: Actualización de Modelo Claude
- **Descripción**: El translator debe usar `claude-haiku-4-5-20251001` en lugar del modelo deprecated `claude-3-haiku-20240307`.
- **Criterios de aceptación**:
  - El nombre del modelo es una constante `CLAUDE_MODEL` en `src/agents/translator.py`
  - El valor es `claude-haiku-4-5-20251001`
  - Los tests del translator pasan sin cambios de lógica
- **Módulo**: src/agents/translator.py

### RF-04: Perfiles de Usuario Sintético (src/executor/profiles/)
- **Descripción**: Tres perfiles de usuario sintético que configuran el contexto del browser (viewport, locale, user-agent).
- **Criterios de aceptación**:
  - `mobile_co.py`: viewport 390×844, locale `es-CO`, user-agent de Chrome mobile
  - `desktop_co.py`: viewport 1440×900, locale `es-CO`, user-agent de Chrome desktop
  - `desktop_ec.py`: viewport 1280×800, locale `es-EC`, user-agent de Chrome desktop, `is_mobile=False`
  - Cada perfil expone un `BrowserProfile` dataclass con los campos: `name`, `viewport_width`, `viewport_height`, `locale`, `user_agent`, `is_mobile`
  - Los perfiles NO contienen lógica de ejecución — son solo configuración
- **Módulo**: src/executor/profiles/

### RF-05: Selectores SFCC (src/executor/selectors.py)
- **Descripción**: Catálogo centralizado de selectores CSS/data-attributes para los elementos interactivos del storefront SFCC/SFRA.
- **Criterios de aceptación**:
  - AC1. Todos los selectores son constantes nombradas en `SCREAMING_SNAKE_CASE`
  - AC2. Los selectores usan prefijos `data-cmp-` o `data-testid-` donde estén disponibles (per PRD R1)
  - AC3. Están agrupados por sección: `SEARCH`, `PDP`, `CART`, `CHECKOUT`, `PAYMENT`, `LOGIN`
  - AC4. No hay selectores hardcodeados fuera de este archivo en el codebase
  - AC5. Cada constante tiene un comentario de una línea explicando a qué elemento corresponde
- **Módulo**: src/executor/selectors.py

### RF-06: Flow checkout_full (src/executor/flows/checkout_full.py)
- **Descripción**: Flow Playwright que simula el camino completo de compra: autenticación de ambiente → login → búsqueda de producto → PDP → añadir al carrito → checkout → pago que falla en el último paso.
- **Criterios de aceptación**:
  - Pasos del flow en orden: `env_access_auth` → `shopper_login` → `search_product` → `category_page` → `pdp_variant_select` → `add_to_cart` → `mini_cart_validation` → `checkout_shipping` → `checkout_payment` → `payment_failure_validation`
  - Cada paso devuelve un `StepResult` (nombre, status, durationMs, error opcional)
  - El paso `payment_failure_validation` SIEMPRE falla — usa el método de pago de prueba configurado
  - El campo `orders_created` en el resultado final SIEMPRE es 0
  - Screenshots se capturan solo en fallo y en el paso final del flujo (ADR-002). No se capturan pasos OK intermedios.
  - Si un paso falla, los pasos posteriores se marcan como `skipped`
  - La función principal es `run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult` — `env` reemplaza los parámetros `store_url/shopper_email/shopper_password` (ADR-001: credenciales resueltas server-side, nunca como strings sueltos)
- **Módulo**: src/executor/flows/checkout_full.py

### RF-07: Flow checkout_card_declined (src/executor/flows/checkout_card_declined.py)
- **Descripción**: Flow que ejecuta el mismo camino que checkout_full pero verifica explícitamente que el mensaje de error de tarjeta rechazada aparece correctamente en la UI.
- **Criterios de aceptación**:
  - Mismos pasos que checkout_full en orden: `env_access_auth` → `shopper_login` → `search_product` → `category_page` → `pdp_variant_select` → `add_to_cart` → `mini_cart_validation` → `checkout_shipping` → `checkout_payment` → `payment_failure_validation`
  - El paso final es `verify_decline_message`: verifica que el mensaje de error de la UI coincide con el mensaje esperado
  - `orders_created` siempre es 0
  - Screenshots se capturan solo en fallo y en el paso final del flujo (ADR-002). No se capturan pasos OK intermedios.
  - Expone la misma firma: `run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult` — `env` reemplaza los parámetros de credenciales (ADR-001)
- **Módulo**: src/executor/flows/checkout_card_declined.py

### RF-08: Ejecutor de Flows (src/executor/runner.py)
- **Descripción**: Orquestador local (stub de Step Functions) que ejecuta los flows en cada perfil y recolecta los resultados.
- **Criterios de aceptación**:
  - Función `run_profile(profile: BrowserProfile, flow_name: FlowName, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str) -> ProfileResult` — `env` ya contiene credenciales resueltas; runner NO las resuelve (ADR-001: responsabilidad del orquestador)
  - El orquestador (`RunOrchestrator`) resuelve `ResolvedEnvironment` desde Secrets Manager antes de llamar a `run_profile`
  - Lanza el browser con la configuración del perfil (viewport, locale, user-agent)
  - Ejecuta el flow correspondiente (`checkout_full` o `checkout_card_declined`)
  - Retorna `ProfileResult` con: perfil, flow, lista de StepResults, durationMs total
  - Captura cualquier excepción no manejada de Playwright y la convierte en error de tipo `infrastructure_error`
  - Soporta contexto asíncrono (async/await con Playwright Python)
- **Módulo**: src/executor/runner.py

### RF-09: Manager de Baseline (src/baseline/baseline_manager.py)
- **Descripción**: Módulo que gestiona el historial de ejecuciones y calcula umbrales p95 para el semáforo. Usa un stub local (dict en memoria) que implementa la misma interfaz que DynamoDB.
- **Criterios de aceptación**:
  - Interfaz `BaselineStore` (Protocol) con métodos: `save_run(run: RunRecord)`, `get_last_n_runs(profile: str, flow: str, n: int) -> list[RunRecord]`, `get_run(run_id: str) -> RunRecord | None`
  - Implementación `InMemoryBaselineStore` que cumple la interfaz (stub para desarrollo)
  - Función `calculate_p95(runs: list[RunRecord]) -> int` — calcula p95 de `durationMs` de los runs
  - Función `is_bootstrap_mode(runs: list[RunRecord]) -> bool` — True si hay menos de 14 runs
  - Función `compute_traffic_light(current_ms: int, p95_ms: int, bootstrap: bool) -> TrafficLight` — retorna `green/yellow/red` según reglas del PRD
  - `TrafficLight` enum con valores `GREEN`, `YELLOW`, `RED`
- **Módulo**: src/baseline/baseline_manager.py

### RF-10: Generador de Reportes (src/reporter/report_generator.py)
- **Descripción**: Módulo que toma los resultados de ejecución y genera el reporte dual (JSON + Markdown) con semáforo.
- **Criterios de aceptación**:
  - Función `generate_report(profile_results: list[ProfileResult], baseline_store: BaselineStore, config: SyntheticUserConfig) -> ExecutionReport`
  - El `ExecutionReport` cumple con el schema `specs/execution_report.json`
  - Función `to_markdown(report: ExecutionReport) -> str` — genera el reporte en Markdown legible para humanos
  - El reporte Markdown incluye: semáforo (emoji verde/amarillo/rojo), resumen por perfil, tabla de pasos, comparación con baseline p95, sección `orders_created: 0`
  - El campo `baselineComparison.bootstrapMode` es True si hay menos de 14 runs
  - El campo `orders_created` SIEMPRE está presente y SIEMPRE es 0 en todos los flows
- **Módulo**: src/reporter/report_generator.py

### RF-11: Endpoint GET /v1/runs/{run_id}
- **Descripción**: Endpoint REST para recuperar el reporte de una ejecución específica.
- **Criterios de aceptación**:
  - `GET /v1/runs/{run_id}` retorna 200 con `ExecutionReport` completo si el run existe
  - Retorna 404 con mensaje descriptivo si el `run_id` no existe
  - El `run_id` es validado como UUID v4 antes de consultar el store
  - Requiere autenticación vía API key (header `X-API-Key`)
- **Módulo**: src/api/main.py

### RF-12: Endpoint GET /v1/runs/latest
- **Descripción**: Endpoint para que agentes CI/CD consulten el último resultado sin lanzar nuevas ejecuciones.
- **Criterios de aceptación**:
  - `GET /v1/runs/latest` retorna 200 con el `ExecutionReport` más reciente
  - El reporte incluye campo `age_seconds: int` (edad del run en segundos)
  - El reporte incluye campo `ttl_ok: bool` (True si `age_seconds < 14400` = 4 horas)
  - Retorna 404 con `error_code: "no_runs_yet"` si no hay runs guardados
  - Requiere autenticación vía API key
- **OUT of MVP (decisión D6)**: query param `?profile=...` para filtrar por perfil y agregación temporal `?since=...&aggregate=daily`. Aplazados a SHOULD HAVE. Ver `inception/user-stories/coverage-matrix.md`.
- **Módulo**: src/api/main.py
- **Referencia historias**: H4.2 en `inception/user-stories/user-stories.md`

### RF-13: Integración POST /v1/run con Executor
- **Descripción**: El endpoint `POST /v1/run` recibe un `SyntheticUserConfig` estructurado, resuelve el ambiente y ejecuta los flows en paralelo.
- **Criterios de aceptación**:
  - El endpoint recibe directamente un payload `SyntheticUserConfig` (ver `specs/synthetic_user_config.json`) — el translator NL ya NO es la entrada principal
  - El backend resuelve `env_access_credentials` (testpilot/{env}/env-access) y `shopper_credentials` (testpilot/{env}/shopper) desde Secrets Manager usando el `environment_id` del payload
  - Llama a `run_profile()` por cada perfil en paralelo via `asyncio.gather` con cap `MAX_CONCURRENT_PROFILES=3` (D1)
  - Al completar, guarda el `ExecutionReport` en el `BaselineStore`
  - Retorna 200 con el `ExecutionReport` completo (no solo "queued")
  - Si el executor lanza `InfrastructureError` (timeout de red/DNS en navegación, D4), el `runner.py` la CAPTURA y devuelve `ProfileResult` con `status="error"` y semáforo YELLOW — el endpoint retorna **200** con el `ExecutionReport` completo. Solo si `InfrastructureError` escapa al middleware → **503** `infrastructure_error` (ver `application-design/error-taxonomy.md`)
  - Cualquier excepción no esperada retorna **500** con `error_code: "internal_error"`, sin stack traces (H4.5)
  - Si el `environment_id` no está registrado en el Environment Registry → 404 `environment_not_found`
  - Timeout global del run: **1800s** (D10, actualizado 2026-05-24); si lo excede → 504 `run_timeout`. Valor original 480s supersedido por D10.
  - El `orders_created` en la respuesta SIEMPRE es 0
- **Módulo**: src/api/main.py
- **Referencia historias**: H4.1, H4.5 en `inception/user-stories/user-stories.md`

---

## Requisitos No Funcionales

### RNF-01: Seguridad de Credenciales (P5 del PRD / SECURITY-12)
- Ninguna credencial (API keys, URLs de staging, passwords) en código fuente ni en logs
- Las credenciales se inyectan vía variables de entorno (`.env` ignorado en `.gitignore`)
- Los logs del executor pasan por filtro de redacción antes de ser escritos
- Ninguna respuesta de API expone credenciales ni stack traces

### RNF-02: Cero Contaminación (P1 del PRD)
- Invariante global: `orders_created` siempre es 0 en todos los flows
- El paso `decline_payment` nunca puede ser modificado para completar el pago
- Los emails de usuarios sintéticos SIEMPRE usan dominio `@testpilot.internal`
- Este invariante es verificado por assertion en el reporter, no solo por convención

### RNF-03: Logging Estructurado (SECURITY-03)
- Todos los módulos usan Python `logging` con logger nombrado por módulo (`logging.getLogger(__name__)`)
- Los logs incluyen: timestamp, correlation ID (testRunId), log level, módulo, mensaje
- Ningún log contiene secretos, tokens, URLs de staging con credenciales, ni PII real
- En modo test, el nivel de log es WARNING o superior para no contaminar el output de pytest

### RNF-04: Manejo de Errores Seguro (SECURITY-15)
- Todos los calls a Claude API, Playwright y el BaselineStore tienen try/except explícito
- En caso de error del executor, el sistema retorna `infrastructure_error` (no falla abiertamente)
- Los errores de validación retornan mensajes descriptivos sin información del sistema
- Hay un global exception handler en FastAPI que captura excepciones no manejadas

### RNF-05: Validación de Inputs (SECURITY-05)
- Todos los endpoints de la API validan inputs vía JSON Schema + Pydantic antes de procesar
- Los `run_id` recibidos en endpoints GET son validados como UUID v4
- Los query params tienen bounds definidos (máximo 100 resultados por consulta)
- Los prompts NL recibidos por el translator tienen longitud máxima de 2000 caracteres

### RNF-06: Autenticación de API (SECURITY-08)
- Todos los endpoints (GET y POST) requieren header `X-API-Key`
- El API key se valida contra una constante de entorno `TESTPILOT_API_KEY`
- Endpoints sin API key válida retornan 401, no 403 (no revelar si el recurso existe)
- No hay endpoints públicos no autenticados en el MVP

### RNF-07: Performance del Executor
- Un run completo (3 perfiles × 2 flows en secuencia local) debe completar en <15 minutos
- Cada step individual tiene timeout configurable (default 60s per `SyntheticUserConfig.timeout`)
- El executor no usa `time.sleep()` fijo — usa `wait_for_selector()` o `expect()` de Playwright

### RNF-08: Supply Chain (SECURITY-08, SECURITY-12)
- `pyproject.toml` con versiones exactas pinned (no rangos `>=`, no `*`)
- Dockerfile usa imagen base con tag de versión específica (no `latest`)
- Las dependencias son de registros oficiales (PyPI, Docker Hub oficial)

### RNF-09: Property-Based Testing en Lógica de Baseline (PBT parcial)
- `calculate_p95()` tiene PBT verificando: output siempre está en el rango [min, max] de los inputs, es invariante con reordenamiento (PBT-03)
- `compute_traffic_light()` tiene PBT verificando: bootstrap mode siempre retorna GREEN, result es determinístico para mismo input (PBT-03)
- El modelo de datos `ExecutionReport → JSON → ExecutionReport` tiene round-trip PBT (PBT-02)
- Framework: `hypothesis` (PBT-09)

### RNF-10: Reproducibilidad del Build
- `pyproject.toml` es suficiente para instalar el proyecto con `pip install -e ".[dev]"`
- `Dockerfile` construye imagen sin errores con `docker build`
- Hay instrucciones de setup en `README.md` o `AGENTS.md`

---

## Restricciones No Negociables (del PRD)

| ID | Restricción | Impacto |
|----|-------------|---------|
| C1 | Catálogo cerrado de flows: solo `checkout_full` y `checkout_card_declined` | El executor NO acepta flows arbitrarios |
| C2 | Credenciales del shopper (`@testpilot.internal`) en Secrets Manager, nunca en el payload ni en logs. El campo `email` no existe en `SyntheticUserConfig`. | Validado en modelos y en el executor |
| C3 | `orders_created` siempre 0 | Assert en reporter; `payment_failure_validation` step es invariante |
| C4 | Screenshots solo en fallo + paso final. Nombrado: `{run_id}/{perfil}/{flujo}/{paso}-{fail\|final}.png` | El executor no captura pasos OK intermedios y siempre captura fallo + paso final |
| C5 | No alertas amarillas durante bootstrap (<14 runs) | El reporter omite comparación con baseline en modo bootstrap |
| C6 | Credenciales nunca en código ni logs | Variables de entorno + filtro de redacción en logs |
| C7 | Selectores solo en `src/executor/selectors.py` | Ningún selector hardcodeado en flows ni profiles |
| C8 | `environment_id` es el único identificador de ambiente en el payload — nunca `store_url` ni credenciales | El endpoint rechaza payloads con `store_url` o `email` directos |
| C9 | Dos credenciales distintas por ambiente: `env_access` (puerta de infraestructura) y `shopper` (cliente SFCC). Nunca intercambiarlas. | El runner resuelve ambas desde Secrets Manager por separado |

---

## Unidades de Trabajo Identificadas

Basado en el scope acordado (Q1=B), se identifican las siguientes unidades de trabajo para el Construction Phase:

| # | Unidad | Módulos | Dependencias | PRD |
|---|--------|---------|--------------|-----|
| U0 | Setup base | pyproject.toml, src/models.py, Dockerfile multi-stage, update translator | Ninguna | TD1, TD2, TD5 |
| U1 | Executor | src/executor/ (profiles, selectors, auth/, flows, runner) | U0 | M3, M4, M9 |
| U2 | Baseline Manager | src/baseline/baseline_manager.py | U0 | M10, M11, M12 |
| U3 | Reporter | src/reporter/report_generator.py | U0, U2 | M7, M8, M15, M17 |
| U4 | API Endpoints | src/api/main.py + services/ (EnvironmentRegistry, EnvironmentResolver, SecretsManagerClient, RunOrchestrator, LiveStatusTracker) | U1, U2, U3 | M1, M2, M6, M13 |
| MD0 | Dashboard Web Interno | src/dashboard/ (React+Vite+TS+Tailwind) | U0 (contratos TS), U4 (runtime REST) | M19 (Dashboard) |

> **Nota**: Las unidades U1, U2, U3 y MD0 pueden desarrollarse en paralelo una vez completada U0 (MD0 con mocks de API). U4 requiere U1+U2+U3 y debe estar listo antes de la integración final con MD0.

---

## Fuentes de Requisitos

- `docs/product/prd-2026-05-22.md` — PRD snapshot (Christian Díaz, 2026-05-22): Secciones 6 (Principios), 8 (MoSCoW), 9 (Módulos)
- `AGENTS.md` — Convenciones de código, restricciones de implementación
- `aidlc-docs/inception/reverse-engineering/` — Análisis de codebase existente
- `aidlc-docs/inception/requirements/requirement-verification-questions.md` — Respuestas del equipo (2026-05-20)
