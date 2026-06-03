# Requirements Document — TestPilot SFCC

> ⚠️ **Realineado 2026-06-03** (branch `rework/storefront-audit-scope`). El alcance se redefinió hacia
> **recorrido completo de tienda + documento de auditoría de 6 dimensiones + ventana de lenguaje natural**.
> El alcance es **fijo** — ningún módulo se recorta; el tiempo es la variable de ajuste.
> Racional y decisiones en [`../scope-realignment-brief.md`](../scope-realignment-brief.md) (§7 todas resueltas);
> objetivo canónico en `PRODUCT.md` §1. Numeración: RF-01..RF-13 originales (se conservan, con ajustes marcados);
> RF-14..RF-20 agregados en application design 2026-05-24 (retro-portados aquí); RF-21..RF-29 capa nueva del alcance realineado.

## Intent Analysis Summary

| Campo | Valor |
|-------|-------|
| **User Request** | Construir plataforma interna de testing continuo con usuarios sintéticos para SFCC/SFRA vía Playwright; reemplazar 4–8h de QA manual con gate de deploy automatizado en <30 min |
| **Request Type** | New Project (brownfield expansion — ~30% del MVP ya implementado) |
| **Scope** | System-wide — 4 módulos nuevos + refactor de modelos + setup de proyecto + endpoints GET. **Realineación 2026-06-03:** + flows de recorrido, agente de auditoría, captura de red, ventana NL |
| **Complexity** | Complex — LLM integration, Playwright automation, DynamoDB baseline, multi-profile orchestration, síntesis de auditoría multi-dimensión |
| **Depth** | Comprehensive |

---

## Alcance de esta sesión (decisiones de implementación)

> Decisiones de la sesión original (2026-05). Siguen vigentes salvo donde la realineación las amplía (ver siguiente sección).

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

## Análisis de la Reestructuración (realineación 2026-06-03)

> Esta sección es la **base del análisis para construcción**: mapea cada elemento del brief de
> realineación y del PRD realineado a un RF concreto, y revisa las decisiones de inception afectadas.

### Trazabilidad brief/PRD → requisitos

| Origen | Elemento | RF que lo cubre |
|---|---|---|
| Brief R1 / PRD M20 | Flujos de recorrido completo (PLP/búsqueda, descuentos, PDP, carrito) como pruebas propias | RF-21, RF-22 |
| Brief §7 decisión #2 | Alcance del recorrido lo elige el usuario (módulo único / subconjunto / `full_journey`) | RF-22 |
| Brief R2 / PRD M21, MD13, P7, J4 | Agente de auditoría: sintetiza 6 dimensiones, no juzga el semáforo | RF-24, RF-25 |
| Brief N1 / PRD M22, MD14 | Captura de red / tiempos API (HAR) + Core Web Vitals + axe-core | RF-23, RF-24 |
| Brief §7 decisión #5 | Evidencia visual dirigida por hallazgos (no por calendario) | RF-26 |
| PRD M23 / UC6 / PRODUCT.md §1 | Ventana de lenguaje natural como entrada principal de UX | RF-27 |
| PRODUCT.md §1 | Modos de operación: gate (determinista) y exploratorio (agéntico, fuera de baseline) | RF-28 |
| Brief Y1 / PRD M19 | Dashboard matriz genérico sobre flows (sin hardcodear checkout) | RF-29 |

### Decisiones de inception revisadas (mandato del brief §4)

| Decisión | Estado anterior | Estado realineado |
|---|---|---|
| **D6** (GET `?aggregate=daily` OUT of MVP) | Aplazado a Should Have | Se mantiene aplazado, pero con alcance fijo se lee como **ola posterior, no recorte** (ver nota en RF-12) |
| **D7** (clasificador LLM descartado; J4 aplazado) | Sin clasificador en MVP | **Supersedida**: se restaura como **agente de auditoría que sintetiza, no juzga** (P7). J4 des-aplazado parcialmente: las anomalías de integridad de comercio marcan `requires_human_review` (RF-25). El semáforo sigue siendo regla determinista (RF-09) |
| **D8** (entrada estructurada; translator opcional) | Payload estructurado, NL opcional | **Mantenida a nivel de contrato**: `POST /v1/run` sigue recibiendo `SyntheticUserConfig` estructurado y validado. **Ampliada a nivel de UX**: la ventana NL es la entrada principal del dashboard; la traducción NL→config ocurre ANTES del run, con preview y confirmación del usuario (RF-27). La instrucción NL nunca llega al executor |

### Implicaciones de diseño detectadas (insumo para application design y construcción)

1. **`full_journey` es composición, no flow.** Si se escribe como archivo propio se duplican selectores y pasos (riesgo R2 del proyecto). Debe declararse en un único lugar (catálogo) como secuencia ordenada de flows modulares.
2. **Precondiciones encadenables.** Los flows modulares corren en dos contextos: dentro de `full_journey` (el estado — sesión, carrito — fluye del flow anterior) y como módulo único (el flow debe auto-prepararse con un `setup()` determinista mínimo). Esto condiciona la firma y el contrato interno de los flows (RF-21 AC3).
3. **Colectores deterministas ≠ agente.** Las 6 dimensiones se **recolectan** con código determinista (RF-24) y se **sintetizan** con LLM (RF-25). Esta separación es la que permite que P7 se cumpla: el agente nunca toca datos crudos del browser ni decide el semáforo.
4. **Cascada de contratos.** RF-21, RF-22, RF-23, RF-25 y RF-28 requieren cambios **breaking** en `specs/` (enum de flows, `mode`, campos de auditoría y red). Ninguno se aplica sin la puerta HITL (tarea #6 del cascade); estos RFs definen el **contrato objetivo**, el schema vigente sigue siendo la verdad hasta el bump de versión.
5. **El gate no se degrada.** Todo lo nuevo (auditoría, red, NL) es aditivo: el modo gate conserva exactamente la semántica actual (determinista, p95, bootstrap silencioso, screenshots fallo+final). Si el agente de auditoría falla, el run NO falla (RF-25 AC6).

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
  - AC3. Los campos de `SyntheticUserConfig` son: `environment_id` (enum: `sandbox|development|staging`), `products[]` (array con `search_term` + `validate_variant`), `flows[]` (array enum closed: `checkout_full`, `checkout_card_declined`), `profiles[]` (array enum closed: `mobile_co`, `desktop_co`, `desktop_ec`) y `capture_intermediate_screenshots` (bool, siempre `false` en MVP). Los campos `storefrontUrl`, `email`, `password`, `screenshot_on_success` y `screenshot_on_error` NO existen en `SyntheticUserConfig`. **Nota realineación:** el enum de `flows[]` crece con el catálogo de recorrido (RF-21) y se agrega `mode` (RF-28) — ambos son breaking change de `specs/` pendiente de puerta HITL (tarea #6); hasta ese bump, el enum vigente del schema es la verdad.
  - AC4. `src/agents/translator.py` importa `SyntheticUserConfig` desde `src/models` (translator promovido a componente principal de UX por RF-27 — sigue sin ser la entrada del endpoint `/v1/run`).
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
  - AC3. Están agrupados por sección: `SEARCH`, `PDP`, `CART`, `CHECKOUT`, `PAYMENT`, `LOGIN`. **Realineación:** se agregan los grupos que demanden los flows de recorrido (p.ej. `PLP`, `PROMOTIONS`) — siempre en este archivo (C7)
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
  - Screenshots según la política de evidencia (RF-26): en modo gate, solo fallo + paso final (ADR-002, sin cambio); en modo auditoría se agregan capturas SOLO por hallazgo o punto crítico declarado.
  - Si un paso falla, los pasos posteriores se marcan como `skipped`
  - La función principal es `run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult` — `env` reemplaza los parámetros `store_url/shopper_email/shopper_password` (ADR-001: credenciales resueltas server-side, nunca como strings sueltos)
- **Módulo**: src/executor/flows/checkout_full.py

### RF-07: Flow checkout_card_declined (src/executor/flows/checkout_card_declined.py)
- **Descripción**: Flow que ejecuta el mismo camino que checkout_full pero verifica explícitamente que el mensaje de error de tarjeta rechazada aparece correctamente en la UI.
- **Criterios de aceptación**:
  - Mismos pasos que checkout_full en orden: `env_access_auth` → `shopper_login` → `search_product` → `category_page` → `pdp_variant_select` → `add_to_cart` → `mini_cart_validation` → `checkout_shipping` → `checkout_payment` → `payment_failure_validation`
  - El paso final es `verify_decline_message`: verifica que el mensaje de error de la UI coincide con el mensaje esperado
  - `orders_created` siempre es 0
  - Screenshots según la política de evidencia (RF-26): en modo gate, solo fallo + paso final (ADR-002, sin cambio).
  - Expone la misma firma: `run(page: Page, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str, profile_id: str) -> FlowResult` — `env` reemplaza los parámetros de credenciales (ADR-001)
- **Módulo**: src/executor/flows/checkout_card_declined.py

### RF-08: Ejecutor de Flows (src/executor/runner.py)
- **Descripción**: Orquestador local (stub de Step Functions) que ejecuta los flows en cada perfil y recolecta los resultados.
- **Criterios de aceptación**:
  - Función `run_profile(profile: BrowserProfile, flow_name: FlowName, config: SyntheticUserConfig, env: ResolvedEnvironment, run_id: str) -> ProfileResult` — `env` ya contiene credenciales resueltas; runner NO las resuelve (ADR-001: responsabilidad del orquestador)
  - El orquestador (`RunOrchestrator`) resuelve `ResolvedEnvironment` desde Secrets Manager antes de llamar a `run_profile`
  - Lanza el browser con la configuración del perfil (viewport, locale, user-agent)
  - Ejecuta el flow correspondiente del catálogo cerrado (checkout + recorrido, RF-21) — **el despacho de flows es genérico** (registro/catálogo), no un if/else hardcodeado a 2 flows
  - Retorna `ProfileResult` con: perfil, flow, lista de StepResults, durationMs total
  - Captura cualquier excepción no manejada de Playwright y la convierte en error de tipo `infrastructure_error`
  - Soporta contexto asíncrono (async/await con Playwright Python)
  - **Realineación:** soporta ejecución secuencial encadenada de una composición (`full_journey`, RF-22) preservando el contexto del browser entre flows
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
  - **Realineación:** solo runs en modo **gate** alimentan el baseline; los runs exploratorios nunca se incluyen (RF-28, C11). El baseline es por par perfil×flow — al crecer el catálogo (RF-21), cada flow nuevo arranca su propio bootstrap (sin alertas amarillas hasta N≥14 de ESE par).
- **Módulo**: src/baseline/baseline_manager.py

### RF-10: Generador de Reportes (src/reporter/report_generator.py)
- **Descripción**: Módulo que toma los resultados de ejecución y genera el reporte dual (JSON + Markdown) con semáforo.
- **Criterios de aceptación**:
  - Función `generate_report(profile_results: list[ProfileResult], baseline_store: BaselineStore, config: SyntheticUserConfig) -> ExecutionReport`
  - El `ExecutionReport` cumple con el schema `specs/execution_report.schema.json`
  - Función `to_markdown(report: ExecutionReport) -> str` — genera el reporte en Markdown legible para humanos
  - El reporte Markdown incluye: semáforo (emoji verde/amarillo/rojo), resumen por perfil, tabla de pasos, comparación con baseline p95, sección `orders_created: 0`
  - El campo `baselineComparison.bootstrapMode` es True si hay menos de 14 runs
  - El campo `orders_created` SIEMPRE está presente y SIEMPRE es 0 en todos los flows
  - **Realineación:** el reporte renderiza los flows de forma **genérica** (iterando lo ejecutado, sin asumir 2 flows de checkout) e integra/enlaza el documento de auditoría cuando existe (RF-25)
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
  - **Realineación:** el "latest" relevante para gate considera solo runs en modo gate (los exploratorios no representan estado deploy-safe, RF-28)
- **Diferido a ola posterior (decisión D6, re-leída con alcance fijo 2026-06-03 — no es recorte)**: query param `?profile=...` para filtrar por perfil y agregación temporal `?since=...&aggregate=daily`. Ver `inception/user-stories/coverage-matrix.md`.
- **Módulo**: src/api/main.py
- **Referencia historias**: H4.2 en `inception/user-stories/user-stories.md`

### RF-13: Integración POST /v1/run con Executor
- **Descripción**: El endpoint `POST /v1/run` recibe un `SyntheticUserConfig` estructurado, resuelve el ambiente y ejecuta los flows en paralelo.
- **Criterios de aceptación**:
  - El endpoint recibe directamente un payload `SyntheticUserConfig` (ver `specs/synthetic-user-config.schema.json`) — la traducción NL ocurre ANTES, en la ventana NL del dashboard (RF-27); la instrucción NL nunca llega a este endpoint
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

## Requisitos Funcionales — Agregados en Application Design (2026-05-24)

> **Retro-portados 2026-06-03.** Estos RF-14..RF-20 fueron definidos durante application design
> (Dashboard MD0, Environment Registry, credenciales duales, endpoints en tiempo real) y estaban
> referenciados en `coverage-matrix.md` y `unit-of-work-story-map.md` sin existir en este documento.
> Se retro-portan aquí en forma resumida para que la numeración sea continua y este documento sea
> la fuente única de RFs. **Detalle completo:** `../application-design/unit-of-work-story-map.md` y
> `../application-design/services.md`.

| RF | Descripción resumida | Unidad | PRD |
|---|---|---|---|
| RF-14 | CRUD Environment Registry (`POST/GET/PUT/DELETE /v1/environments`) | U4 | M19, M13 |
| RF-15 | `EnvironmentResolver`: resolución de credenciales `env_access` + `shopper` desde Secrets Manager (caché TTL 5 min) | U4 | M13 |
| RF-16 | `GET /v1/runs/{id}/status` — estado en vivo para polling del dashboard | U4 | M19 |
| RF-17 | `GET /v1/runs` — historial paginado con filtros (env, semáforo, flow, fechas) | U4 | M19, Journey 2 |
| RF-18 | `GET /v1/runs/{id}/screenshots/{path}` — proxy de evidencia desde S3 | U4 | M9 |
| RF-19 | `GET /health` — verifica DynamoDB + Secrets Manager | U4 | Observability |
| RF-20 | Dashboard MD0 — 5 pantallas (P1 Environments, P2 NewRun, P3 LiveRun, P4 RunDetail, P5 History) | MD0 | M19 |

---

## Requisitos Funcionales — Alcance Realineado (recorrido + auditoría)

> RFs nuevos de la realineación 2026-06-03. Trazabilidad: ver "Análisis de la Reestructuración".
> Los cambios de contrato que estos RFs implican en `specs/` son **breaking** y pasan por puerta HITL (tarea #6 del cascade) antes de implementarse.

### RF-21: Catálogo de Flows de Recorrido (modular, cerrado)
- **Descripción**: Extender el catálogo cerrado con flows modulares de recorrido de tienda, cada uno como prueba propia (no como pasos del checkout). El catálogo **sigue cerrado** — crece solo de forma curada vía PR (decisión D47 del PRD); el LLM/usuario solo selecciona de él.
- **Criterios de aceptación**:
  - AC1. Flows nuevos del catálogo:
    - `search_and_filter` — búsqueda desde el header, validación de resultados en PLP, aplicación de al menos un refinamiento (categoría/precio), validación de que el grid responde
    - `browse_discounted_products` — navegación a PLP de promociones/ofertas, validación de que los productos muestran precio original tachado + precio con descuento, y que el descuento mostrado es consistente (alimenta la dimensión integridad de comercio, RF-24)
    - `pdp_validation` — PDP de un producto (vía `products[].search_term`): precio visible, selector de variantes funcional, galería de imágenes carga, botón add-to-cart habilitado
    - `cart_review` — carrito: producto presente, cantidad modificable, subtotal recalcula, precio consistente con el visto en PDP
  - AC2. Cada flow es un archivo propio en `src/executor/flows/` con la **misma firma** `run(page, config, env, run_id, profile_id) -> FlowResult` que RF-06/RF-07
  - AC3. Cada flow declara sus **precondiciones** y expone un `setup()` determinista que las satisface en modo módulo-único (p.ej. `cart_review.setup()` busca y añade un producto). En modo `full_journey` (RF-22) el `setup()` se omite porque el estado fluye del flow anterior
  - AC4. Ningún flow de recorrido contiene pasos de pago/checkout — solo los flows `checkout_*` tocan pago (preserva el invariante de cero contaminación acotado a un solo lugar)
  - AC5. Todos los selectores nuevos viven en `selectors.py` (C7); los flows emiten `StepResult` por paso igual que RF-06
  - AC6. Cada flow emite, además de sus StepResults, los datos crudos que necesitan los colectores de auditoría (RF-24): precios observados por página, URLs visitadas, etc.
  - AC7. La extensión del enum `flows[]` en `specs/synthetic-user-config.schema.json` (+ ajuste de `maxItems`) es breaking → puerta HITL (tarea #6). Este RF define el **catálogo objetivo**
- **Módulo**: src/executor/flows/
- **Trazabilidad**: PRD M20/MD5, brief R1, decisión §7-#2

### RF-22: Selección de Alcance del Recorrido (módulo único / subconjunto / full_journey)
- **Descripción**: El usuario que lanza el run decide el alcance: probar el flujo de un solo módulo, un subconjunto, o el recorrido completo de la tienda.
- **Criterios de aceptación**:
  - AC1. `flows[]` acepta cualquier combinación de flows del catálogo (RF-21 + checkout) — un solo flow es un run válido
  - AC2. `full_journey` es una **composición declarada** (secuencia ordenada: `search_and_filter` → `pdp_validation` → `cart_review` → `checkout_full`), definida en UN solo lugar del catálogo — **NO** es un archivo flow propio (evita duplicar selectores/pasos; ver Implicación de diseño #1)
  - AC3. Cuando el run incluye `full_journey`, el runner (RF-08) ejecuta la composición de forma encadenada preservando el contexto del browser (sesión, carrito) entre flows; los `setup()` de los flows intermedios se omiten
  - AC4. Cuando el run incluye flows modulares sueltos, cada uno corre aislado ejecutando su `setup()` (RF-21 AC3)
  - AC5. La representación exacta en el contrato (`full_journey` como valor del enum que el backend expande, vs. campo `journey_scope`) se decide en la puerta HITL de `specs/` (tarea #6) — el comportamiento de este RF es independiente de esa elección
  - AC6. La ventana NL (RF-27) puede mapear instrucciones como "revisa toda la tienda" → `full_journey` y "revisa solo el carrito" → `cart_review`
- **Módulo**: src/executor/ (catálogo + runner) + specs/ (HITL)
- **Trazabilidad**: decisión §7-#2 (2026-06-03), PRD UC6

### RF-23: Captura de Red y Métricas de Rendimiento (HAR + CWV + controllers SFRA)
- **Descripción**: Durante cada flow, el executor captura tráfico de red estilo HAR vía Playwright y métricas de rendimiento percibido. Es **user-perceived + network timing** — NO APM de backend.
- **Criterios de aceptación**:
  - AC1. Por cada par perfil×flow se captura: requests (URL, método, status, tipo de recurso, timings, tamaño de respuesta) restringidos a una **allowlist de dominios** (el storefront y sus assets — nunca dominios de terceros no relacionados)
  - AC2. Core Web Vitals por página clave del flow: LCP, CLS y TTFB (INP/TBT si Playwright/CDP lo permite sin inflar el tiempo del flow)
  - AC3. Tiempos de controllers SFRA: agregación de los requests cuyo path coincide con el patrón de controllers (`*-Show`, `*-AddProduct`, `Cart-*`, `CheckoutServices-*`, etc.) — esto da el "waterfall de controllers" del PRD
  - AC4. Headers de autenticación, cookies y cualquier credencial se **redactan antes de persistir** (mismo filtro de redacción de RNF-01); los bodies de request/response NO se persisten (solo metadata + timings)
  - AC5. El HAR filtrado se sube a S3 (`{run_id}/{perfil}/{flujo}/network.har.json`) con la misma política de lifecycle que la evidencia (RF-26); el `ExecutionReport` lleva un **resumen** (totales, requests fallidos, p95 de controllers, CWV) + referencia al HAR — campos nuevos en `execution_report.schema.json` → breaking, puerta HITL (tarea #6)
  - AC6. El baseline p95 (RF-09) sigue operando sobre `durationMs` de pasos/flows en esta ola; extender baseline a CWV/red es ola posterior (no recorte)
- **Módulo**: src/executor/ (captura) + src/reporter/ (resumen)
- **Trazabilidad**: PRD M22/MD14, brief N1, decisión §7-#4

### RF-24: Colectores Deterministas de las 6 Dimensiones de Auditoría
- **Descripción**: Código determinista (sin LLM) que recolecta hallazgos por dimensión durante la ejecución de los flows. Los hallazgos son la **única fuente de datos** del agente de auditoría (RF-25) y disparan evidencia visual (RF-26).
- **Criterios de aceptación**:
  - AC1. **Integridad de comercio** — precios del mismo producto capturados en PLP, PDP y carrito se comparan de forma determinista; mismatch (p.ej. descuento aplicado/no aplicado, monto distinto) = hallazgo. Disponibilidad inconsistente = hallazgo
  - AC2. **Rendimiento** — derivado de RF-23 (CWV fuera de umbrales razonables, controllers lentos, requests fallidos repetidos)
  - AC3. **Correctitud de locale** — por perfil (CO/EC): símbolo/código de moneda esperado, idioma del contenido visible, formato numérico; verificación por asserts deterministas
  - AC4. **Accesibilidad** — axe-core inyectado en las **páginas clave** del flow (no en cada estado intermedio); violaciones WCAG AA serializadas con regla, impacto y nodo afectado
  - AC5. **Salud del cliente** — errores de consola JS, requests con 4xx/5xx, mixed content, recopilados vía listeners de Playwright durante todo el flow
  - AC6. **Integridad de contenido** — en páginas clave: title/meta description presentes, imágenes que cargan (no 404), atributos `alt` en imágenes de producto
  - AC7. Cada hallazgo es un objeto estructurado: `{dimension, severity, page_url, step, data, evidence_refs[]}` — generado por código, reproducible, sin intervención del LLM
  - AC8. Los colectores corren en modo auditoría/exploratorio y en modo gate cuando el run lo solicita; su fallo individual degrada a "dimensión no recolectada" en el reporte, nunca tumba el flow
- **Módulo**: src/executor/ (captura durante el flow) + módulo de auditoría (ensamblaje — ubicación final en application design)
- **Trazabilidad**: PRD M21/MD13, PRODUCT.md §1 (6 dimensiones), brief R2

### RF-25: Agente de Auditoría (síntesis, no juicio — P7)
- **Descripción**: Agente LLM que **sintetiza y redacta** el documento de auditoría a partir de los hallazgos deterministas (RF-24) y métricas (RF-23). **Nunca decide** el semáforo — ese veredicto lo dicta la regla determinista (RF-09). Restaura el "Generador de Resumen + clasificación" (MD2) que D7 había aplazado, bajo la restricción P7.
- **Criterios de aceptación**:
  - AC1. Input del agente: hallazgos estructurados + resúmenes de métricas + StepResults, **sanitizados** (sin credenciales, sin cookies/headers, sin PII real — RNF-14). El agente nunca accede al browser ni a datos crudos
  - AC2. Output: documento de auditoría en Markdown + representación JSON, con: resumen ejecutivo legible para no-técnicos, una sección por dimensión, y cada hallazgo con su evidencia enlazada (screenshot, URL, paso, entrada HAR). Sin evidencia no hay hallazgo (principio de producto #3)
  - AC3. El agente puede **categorizar** hallazgos y proponer hipótesis — cada hipótesis lleva `confidence` (0–1) y `requires_human_review: bool`; las hipótesis se presentan como hipótesis, nunca como hechos confirmados (P7)
  - AC4. Restauración parcial de J4: una anomalía de integridad de comercio (p.ej. descuento aplicado a producto inelegible) produce `requires_human_review: true` y semáforo AMARILLO por regla determinista — el agente la describe, no la veredicta
  - AC5. El semáforo verde/amarillo/rojo es un campo aparte del reporte, calculado exclusivamente por RF-09; el documento de auditoría NO lo contradice ni lo recalcula
  - AC6. **Degradación con gracia**: si la llamada al LLM falla o excede timeout, el reporte se emite igual con los hallazgos crudos de RF-24 y una nota "síntesis no disponible" — el run nunca falla por el agente
  - AC7. Las llamadas a Claude API van por el módulo de agente permitido por los boundaries del proyecto (hoy `src/classifier/`; el nombre/ubicación final del módulo de auditoría se fija en application design — tarea #5)
- **Módulo**: src/classifier/ (agente de auditoría — nombre final en application design)
- **Trazabilidad**: PRD M21/MD2/P7/J4, brief R2, decisión §7-#3

### RF-26: Política de Evidencia Dirigida por Hallazgos
- **Descripción**: La evidencia visual se captura **cuando vale la pena resaltar algo**, nunca por calendario. Refina ADR-002 sin romper su presupuesto.
- **Criterios de aceptación**:
  - AC1. **Siempre** (todos los modos, sin cambio respecto a ADR-002): captura en fallo de paso + paso final del flow
  - AC2. **En modo auditoría/exploratorio**, capturas adicionales SOLO en dos casos: (a) un colector emite un hallazgo (RF-24) — la captura se toma en el momento/página del hallazgo y se enlaza en `evidence_refs`; (b) el flow alcanza un **punto crítico declarado** en el catálogo (p.ej. resumen de pago, validación de rechazo de tarjeta). Los puntos críticos se declaran por flow en el catálogo, no ad-hoc en el código del paso
  - AC3. **Nunca** se captura un paso OK sin hallazgo ni punto crítico ("porque sí" está prohibido)
  - AC4. Naming extiende la convención C4: `{run_id}/{perfil}/{flujo}/{paso}-{fail|final|finding-{dimension}|critical}.png`
  - AC5. `capture_intermediate_screenshots` permanece `const false` en el schema — la captura por hallazgos NO es "capturar intermedios": es dirigida por evento, no por paso
  - AC6. Lifecycle S3: evidencia con retención 90 días hot → Glacier (P6); el presupuesto KPI C4 del PRD (≤1 GB sem 4, ≤5 GB sem 12) se mantiene como criterio de control
- **Módulo**: src/executor/ (captura) + infra/ (lifecycle, HITL)
- **Trazabilidad**: decisión §7-#5 (2026-06-03), ADR-002, PRD M9/C7

### RF-27: Ventana de Lenguaje Natural (entrada principal de UX)
- **Descripción**: Cualquier miembro del equipo —técnico o no— describe en lenguaje natural qué quiere validar; el sistema traduce a `SyntheticUserConfig`, **muestra qué va a ejecutar**, y solo tras confirmación lanza el run. Promueve el translator de "opcional" a componente principal de UX, sin cambiar el contrato del endpoint de ejecución (D8 se mantiene a nivel de API).
- **Criterios de aceptación**:
  - AC1. El dashboard ofrece un campo de texto NL (es-CO neutro) como vía principal; el editor JSON queda como vía avanzada
  - AC2. La traducción ocurre en un endpoint dedicado (p.ej. `POST /v1/translate` — contrato exacto en puerta HITL #6) que retorna el `SyntheticUserConfig` propuesto + una explicación legible de lo que se va a ejecutar (flows, perfiles, productos, modo)
  - AC3. El usuario **confirma el preview** antes de que se llame a `POST /v1/run` con el payload estructurado — la instrucción NL nunca llega al executor (C12)
  - AC4. Validación P3 estricta: el config propuesto pasa JSON Schema + catálogo cerrado ANTES de mostrarse; instrucción ambigua → respuesta de clarificación (equivalente a `400 AmbiguousInstruction`), instrucción fuera de catálogo → rechazo explicando el catálogo disponible
  - AC5. Límite de 2000 caracteres en la instrucción NL (RNF-05); resistencia a prompt injection per RT1 (Q8 = 0 ejecutados); todo intento rechazado se loggea
  - AC6. El mapeo NL→alcance soporta los casos de RF-22 AC6 (módulo único, subconjunto, recorrido completo)
  - AC7. Gate de calidad pre-lanzamiento: dataset D-NL con Q1 ≥90% de configs válidos, Q2 = 100% adherencia al catálogo (PRD §11)
- **Módulo**: src/agents/translator.py + src/api/main.py + src/dashboard/
- **Trazabilidad**: PRD M23/UC6/P3, PRODUCT.md §1-§2, brief cascade #4

### RF-28: Modos de Operación — Gate y Exploratorio
- **Descripción**: Dos modos con semánticas separadas: **gate** (determinista, reproducible, alimenta baseline, bloquea deploys) y **exploratorio** (para descubrimiento/auditoría ad-hoc; nunca contamina el baseline ni emite veredicto de gate).
- **Criterios de aceptación**:
  - AC1. Campo `mode: "gate" | "exploratory"` en `SyntheticUserConfig`, default `gate` (campo nuevo → breaking, puerta HITL #6)
  - AC2. Modo gate: comportamiento actual íntegro — flows deterministas del catálogo, baseline p95, bootstrap silencioso, semáforo como veredicto de deploy
  - AC3. Modo exploratorio: ejecuta flows del mismo catálogo cerrado (no flows libres — invariante #2 intacto) con colectores de auditoría siempre activos; sus resultados **no se escriben al baseline** (C11) y su reporte se marca `mode: exploratory` de forma visible — el semáforo que muestre es informativo, no veredicto de gate
  - AC4. `GET /v1/runs/latest` para decisiones de deploy considera solo runs gate (RF-12)
  - AC5. El cap de costo (10 runs/día) aplica a la **suma** de ambos modos
- **Módulo**: src/models.py + src/api/ + src/baseline/
- **Trazabilidad**: PRODUCT.md §1 (modos), P3 (exploratorio fuera del gate), P4

### RF-29: Dashboard — Matriz Genérica de Ejecución
- **Descripción**: La vista en tiempo real del dashboard es una matriz filas=perfiles × columnas=flows **derivada de los datos del run**, sin hardcodear "checkout" ni asumir un número fijo de flows.
- **Criterios de aceptación**:
  - AC1. La matriz se construye desde los `flows[]` y `profiles[]` del run en curso — agregar un flow nuevo al catálogo NO requiere cambios en el dashboard
  - AC2. Cada celda muestra estado vivo (pending/running/passed/failed/error) del par perfil×flow
  - AC3. La vista de resultados enlaza el documento de auditoría (RF-25) cuando existe, y distingue visualmente runs gate vs exploratorios (RF-28)
  - AC4. El dashboard muestra las runs restantes del día (cap de costo visible — principio de producto #5)
- **Módulo**: src/dashboard/ (MD0)
- **Trazabilidad**: brief Y1, PRD M19/MD0

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
- **Realineación:** los flows de recorrido (RF-21) no contienen pasos de pago — la superficie de riesgo de contaminación queda acotada exclusivamente a los flows `checkout_*`

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
- **Realineación:** un run `full_journey` (3 perfiles × composición completa, con colectores y captura de red activos) debe mantener el techo de producto de **<30 minutos** end-to-end; el timeout global de 1800s (D10) es coherente con este techo

### RNF-08: Supply Chain (SECURITY-08, SECURITY-12)
- `pyproject.toml` con versiones exactas pinned (no rangos `>=`, no `*`)
- Dockerfile usa imagen base con tag de versión específica (no `latest`)
- Las dependencias son de registros oficiales (PyPI, Docker Hub oficial)
- **Realineación:** aplica también a las dependencias nuevas (axe-core inyectado, tooling HAR) — versiones pinned y origen oficial

### RNF-09: Property-Based Testing en Lógica de Baseline (PBT parcial)
- `calculate_p95()` tiene PBT verificando: output siempre está en el rango [min, max] de los inputs, es invariante con reordenamiento (PBT-03)
- `compute_traffic_light()` tiene PBT verificando: bootstrap mode siempre retorna GREEN, result es determinístico para mismo input (PBT-03)
- El modelo de datos `ExecutionReport → JSON → ExecutionReport` tiene round-trip PBT (PBT-02)
- Framework: `hypothesis` (PBT-09)

### RNF-10: Reproducibilidad del Build
- `pyproject.toml` es suficiente para instalar el proyecto con `pip install -e ".[dev]"`
- `Dockerfile` construye imagen sin errores con `docker build`
- Hay instrucciones de setup en `README.md` o `AGENTS.md`

### RNF-11..RNF-13: Agregados en Application Design (2026-05-24, retro-portados 2026-06-03)

> Definidos en `../application-design/unit-of-work-story-map.md` ("Mapa RNF → Unidad"); se retro-portan resumidos para numeración continua:

- **RNF-11** — CSP + security headers para el dashboard estático (U4 middleware + MD0)
- **RNF-12** — Caché TTL para Environment Registry (60s) y resolución de credenciales (5 min) (U4)
- **RNF-13** — Endpoint `/v1/runs/{id}/status` polling-friendly, <100 ms p95 (U4)

### RNF-14: Seguridad y Costo del Agente de Auditoría (nuevo — realineación)
- El input al LLM se **sanitiza** antes de cada llamada: sin credenciales, sin cookies/headers de autenticación, sin PII real (los emails sintéticos ya son `@testpilot.internal`)
- Presupuesto de tokens por run acotado por constante configurable; si los hallazgos exceden el presupuesto, se truncan por prioridad de severidad (y el documento lo declara)
- Timeout explícito de la llamada al agente; al exceder → degradación con gracia (RF-25 AC6)
- Las hipótesis del agente nunca se presentan como hechos (P7); el output del agente pasa por el mismo filtro de redacción de logs antes de persistirse

### RNF-15: Overhead de Captura (nuevo — realineación)
- La captura de red (RF-23) y los colectores (RF-24) no deben agregar más de ~10% al tiempo de ejecución del flow; axe-core corre solo en páginas clave (no en cada estado)
- El HAR persistido excluye bodies (solo metadata + timings) y se filtra por allowlist de dominios — tamaño acotado por run
- Evidencia y HAR comparten lifecycle S3 (90 días hot → Glacier) y se vigilan contra el KPI de costo C4 del PRD

---

## Restricciones No Negociables (del PRD)

| ID | Restricción | Impacto |
|----|-------------|---------|
| C1 | Catálogo **cerrado** de flows: `checkout_full`, `checkout_card_declined` + flows de recorrido curados (RF-21: `search_and_filter`, `browse_discounted_products`, `pdp_validation`, `cart_review`) y la composición `full_journey` (RF-22). Crece solo de forma curada vía PR (D47) — **nunca** flows arbitrarios | El executor NO acepta flows fuera del catálogo; el enum del schema es la puerta |
| C2 | Credenciales del shopper (`@testpilot.internal`) en Secrets Manager, nunca en el payload ni en logs. El campo `email` no existe en `SyntheticUserConfig`. | Validado en modelos y en el executor |
| C3 | `orders_created` siempre 0 | Assert en reporter; `payment_failure_validation` step es invariante; flows de recorrido no tocan pago |
| C4 | Evidencia dirigida por hallazgos (RF-26): fallo + paso final SIEMPRE; en auditoría, además hallazgos y puntos críticos declarados — nunca capturas "porque sí". Nombrado: `{run_id}/{perfil}/{flujo}/{paso}-{fail\|final\|finding-{dim}\|critical}.png` | El executor no captura pasos OK sin hallazgo; presupuesto C4 del PRD vigente |
| C5 | No alertas amarillas durante bootstrap (<14 runs) — por par perfil×flow; cada flow nuevo del catálogo arranca su propio bootstrap | El reporter omite comparación con baseline en modo bootstrap |
| C6 | Credenciales nunca en código ni logs | Variables de entorno + filtro de redacción en logs |
| C7 | Selectores solo en `src/executor/selectors.py` | Ningún selector hardcodeado en flows ni profiles |
| C8 | `environment_id` es el único identificador de ambiente en el payload — nunca `store_url` ni credenciales | El endpoint rechaza payloads con `store_url` o `email` directos |
| C9 | Dos credenciales distintas por ambiente: `env_access` (puerta de infraestructura) y `shopper` (cliente SFCC). Nunca intercambiarlas. | El runner resuelve ambas desde Secrets Manager por separado |
| C10 | **El agente de auditoría nunca decide el semáforo** (P7). El veredicto verde/amarillo/rojo es exclusivamente regla determinista sobre métricas + baseline | El campo de semáforo se calcula en RF-09; el agente (RF-25) solo sintetiza |
| C11 | **Los runs exploratorios nunca entran al baseline** ni cuentan como estado deploy-safe | `save_run` filtra por modo; `/v1/runs/latest` para gate ignora exploratorios |
| C12 | **La instrucción NL nunca llega al executor** — solo una `SyntheticUserConfig` validada contra schema + catálogo, confirmada por el usuario (P3) | El executor no tiene dependencia alguna del translator |

---

## Unidades de Trabajo Identificadas

Basado en el scope acordado (Q1=B) y la realineación 2026-06-03 (alcance fijo, entrega por olas), se identifican las siguientes unidades de trabajo para el Construction Phase:

| # | Unidad | Módulos | Dependencias | PRD |
|---|--------|---------|--------------|-----|
| U0 | Setup base | pyproject.toml, src/models.py, Dockerfile multi-stage, update translator | Ninguna | TD1, TD2, TD5 |
| U1 | Executor | src/executor/ (profiles, selectors, auth/, flows checkout, runner) | U0 | M3, M4, M9 |
| U2 | Baseline Manager | src/baseline/baseline_manager.py | U0 | M10, M11, M12 |
| U3 | Reporter | src/reporter/report_generator.py | U0, U2 | M7, M8, M15, M17 |
| U4 | API Endpoints | src/api/main.py + services/ (EnvironmentRegistry, EnvironmentResolver, SecretsManagerClient, RunOrchestrator, LiveStatusTracker) | U1, U2, U3 | M1, M2, M6, M13 |
| MD0 | Dashboard Web Interno | src/dashboard/ (React+Vite+TS+Tailwind) — incluye matriz genérica (RF-29) | U0 (contratos TS), U4 (runtime REST) | M19 |
| **U5** | **Flows de recorrido** | src/executor/flows/ (4 flows nuevos, RF-21) + selectores nuevos + composición `full_journey` + despacho genérico en runner (RF-22) | U1, **puerta HITL specs (#6)** | M20, MD5 |
| **U6** | **Auditoría: colectores + agente** | colectores deterministas 6 dimensiones (RF-24) + agente de síntesis (RF-25) + integración en reporter | U1, U3, U7, **puerta HITL specs (#6)** | M21, MD2, MD13 |
| **U7** | **Captura de red / performance** | captura HAR + CWV + timings de controllers en executor (RF-23) + resumen en reporter | U1, **puerta HITL specs (#6)** | M22, MD14 |
| **U8** | **Ventana NL** | endpoint de traducción + preview/confirmación (RF-27) + UI NL en dashboard + modos gate/exploratorio (RF-28) | U0 (translator), U4, MD0, **puerta HITL specs (#6)** | M23, MD2 |

> **Notas de secuencia (entrega por olas — alcance fijo):**
> 1. **Ola 1 (sin cambios):** U0 → {U1, U2, U3, MD0 en paralelo} → U4. Es el gate de checkout que ya estaba planificado.
> 2. **Puerta HITL de contratos (tarea #6 del cascade):** los cambios a `specs/` (enum de flows, `mode`, campos de auditoría/red) se aprueban ANTES de iniciar U5–U8. Ningún contrato se toca sin confirmación humana.
> 3. **Ola 2:** U5 (recorrido) y U7 (red) pueden ir en paralelo tras U1. U6 (auditoría) requiere U7 (sus hallazgos de rendimiento consumen datos de red) y U3 (integración en reporte). U8 puede arrancar tras U4/MD0.
> 4. La consolidación fina de U5–U8 (¿U8 se funde con U4+MD0? ¿los colectores viven en executor o módulo propio?) se decide en `application-design/unit-of-work.md` (tarea #5).

---

## Fuentes de Requisitos

- `docs/product/prd.md` — PRD v1.2 (realineado 2026-06-02): Secciones 6 (Principios, incl. P7), 8 (MoSCoW + M20–M23), 9 (Módulos, incl. MD13–MD14)
- `PRODUCT.md` §1 — objetivo canónico realineado (recorrido completo, 6 dimensiones, ventana NL, modos gate/exploratorio)
- `aidlc-docs/inception/scope-realignment-brief.md` — racional de la realineación; decisiones §7 #1–#5 (todas resueltas a 2026-06-03)
- `AGENTS.md` — Convenciones de código, restricciones de implementación
- `aidlc-docs/inception/reverse-engineering/` — Análisis de codebase existente
- `aidlc-docs/inception/requirements/requirement-verification-questions.md` — Respuestas del equipo (2026-05-20)
- `specs/synthetic-user-config.schema.json` + `specs/execution_report.schema.json` — contrato vigente (v1); los RF-21/15/16/18/21 definen el contrato objetivo pendiente de puerta HITL
