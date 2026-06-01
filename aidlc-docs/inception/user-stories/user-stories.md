# User Stories — TestPilot SFCC

**Estado**: Aprobado iteración 2 — 2026-05-22
**Origen**: Etapa User Stories formalizada el 2026-05-22 (originalmente OMITIDA el 2026-05-20 con justificación "PRD cubre personas y journeys"; reactivada para resolver gaps de diseño detectados en auditoría)
**Trazabilidad**: cada historia referencia al menos un elemento del PRD (Journey, UC, MoSCoW M*, principio P*, RNF*)
**Cobertura MoSCoW**: ver `coverage-matrix.md` (14/18 cubiertos, 1 simplificado, 3 aplazados/operativos justificados)

---

## Design Decisions (consolidadas de iteración 1)

Estas decisiones se tomaron en revisión del 2026-05-22 y aplican transversalmente a las historias.

| ID | Decisión | Aplica a | Cierra gap |
|---|---|---|---|
| D1 | Paralelización de 3 perfiles vía `asyncio.gather` con cap `MAX_CONCURRENT_PROFILES=3` | H1.1, S1 | B3 (concurrencia) |
| D2 | Tarjeta de declinación por env var `TEST_DECLINE_CARD`, default `4000000000000002` | H1.2 | A6, B2 |
| D3 | Mensaje de declinación validado por regex flexible `/tarjeta.*(rechaz\|declin)/i` | H1.3 | A6 |
| D4 | `InfrastructureError` se lanza en cualquier `TimeoutError` de navegación; los `TimeoutError` esperando selector son app-error | H1.4 | B1 (taxonomía errores) |
| D5 | `SCREENSHOT_DIR` default `./screenshots` en dev; requerida si `ENV=production` (chequeo en startup). Política MVP: screenshots solo en fallo + paso final (ADR-002). | H1.5 | B2 |
| D6 | Endpoint `GET /v1/runs?since=...&aggregate=daily` OUT of MVP | H2.3 | scope MVP |
| D7 | Clasificador LLM con `confidence` / `requires_human_review` OUT of MVP; descartada historia original H3.3 | U3 | scope MVP |
| D8 | `POST /v1/run` recibe `SyntheticUserConfig` estructurado (Pydantic). El translator NL queda como funcionalidad opcional en `src/agents/translator.py` para uso futuro o endpoint dedicado, NO como entrada principal del run. Las credenciales se resuelven en backend desde Secrets Manager vía `environment_id` (BR-U0-01). | H4.1 | A1 (translator integration) — actualizada 2026-05-24 |
| D9 | `run_id` se genera server-side como UUID4; idempotencia via `Idempotency-Key` header → SHOULD HAVE | H4.1, H4.3 | B4 |
| D10 | Timeout global del run: 1800s (30 min) — env var `RUN_TIMEOUT_SECONDS`; si lo excede → 504 con `error_code: "run_timeout"`. *Actualizado 2026-05-24: el flow con dos autenticaciones + 10 pasos × 3 perfiles supera el budget original de 480s.* | H4.1 | B5 |
| D11 | Si `TESTPILOT_API_KEY` no está seteada al iniciar, la app falla loud en startup | H4.4 | B2 |
| D12 | Logging: stdlib `logging` + `JSONFormatter` custom + filtros de redacción para `X-API-Key`, `ANTHROPIC_API_KEY` y campos cuyo nombre contenga `password\|token\|card\|key` | H4.5 + transversal | A2 (logging strategy) |
| D13 | Se agrega `H2.5` para hacer explícita la swappabilidad del `BaselineStore` (M10) | H2.5 | cobertura M10 |

---

## U0 — Setup Base (3 historias)

### H0.1 — `SyntheticUserConfig` único punto de definición
**Como** ingeniero del equipo TestPilot,
**quiero** que `SyntheticUserConfig` se defina en un solo lugar del repo,
**para** que cambios futuros (ej. agregar un campo) no se rompan en silencio entre `translator.py` y `api/main.py`.

**AC**:
- AC1. `SyntheticUserConfig` está definido únicamente en `src/models.py`.
- AC2. `src/agents/translator.py` y `src/api/main.py` lo importan desde `src.models` (no lo redefinen).
- AC3. Test (`test_models.py`) verifica que se puede instanciar con todos los campos del JSON Schema (`specs/synthetic_user_config.json`).
- AC4. `grep -rn "class SyntheticUserConfig" src/` retorna exactamente 1 línea.

**Origen PRD**: TD1, deuda técnica crítica.

---

### H0.2 — Build reproducible y supply chain segura
**Como** responsable de release,
**quiero** que el build sea reproducible y use una imagen Docker verificada,
**para** que el reporte del miércoles sea explicable mañana.

**AC**:
- AC1. `pyproject.toml` declara todas las dependencias con `==` (no `>=` ni `~=`).
- AC2. `Dockerfile` usa `mcr.microsoft.com/playwright/python:v1.48.0-jammy` (no `:latest`).
- AC3. `Dockerfile` corre como usuario `pwuser` (no root).
- AC4. `.dockerignore` excluye `.env`, `.git`, `aidlc-docs/`, `tests/`, `__pycache__/`.

**Origen PRD**: RNF-08, RNF-10, P5.

---

### H0.3 — Lint y type checking desde día 1
**Como** ingeniero del equipo,
**quiero** que `ruff` y `mypy --strict` estén configurados antes de escribir código nuevo,
**para** detectar regresiones de tipos antes de runtime.

**AC**:
- AC1. `pyproject.toml` configura `ruff` con reglas E, F, I, UP habilitadas.
- AC2. `pyproject.toml` configura `mypy` con `strict = true`.
- AC3. `ruff check .` y `mypy src/` retornan exit 0 sobre el código de U0.

**Origen PRD**: TD2, calidad del código.

---

## U1 — Executor Playwright (5 historias)

### H1.1 — Ejecución paralela en 3 perfiles críticos
**Como** Carolina (ingeniera SFCC),
**quiero** que el sistema corra los flows en `mobile/CO`, `desktop/CO` y `desktop/EC (Ecuador)`,
**para** validar que mi PR no rompe ninguno de los 3 segmentos críticos.

**AC**:
- AC1. El sistema expone exactamente 3 perfiles: `mobile_co`, `desktop_co`, `desktop_ec` (constante `ALL_PROFILES`).
- AC2. Cada perfil define `viewport_width`, `viewport_height`, `locale`, `user_agent`, `is_mobile`.
- AC3. Un POST /v1/run ejecuta los 3 perfiles en paralelo vía `asyncio.gather`, con cap `MAX_CONCURRENT_PROFILES=3` (env var override). Si un perfil falla, los otros se completan (`return_exceptions=True`).
- AC4. La respuesta contiene un `ProfileResult` por cada perfil ejecutado, en orden estable (orden de `ALL_PROFILES`).

**Origen PRD**: M3, Journey 1 paso 3. **Decisión**: D1.

---

### H1.2 — Cero contaminación de órdenes reales
**Como** Carolina,
**quiero** que el sistema intente pagar pero **nunca** confirme una orden real,
**para** no contaminar la base de datos de producción.

**AC**:
- AC1. El campo `email` NO existe en `SyntheticUserConfig`. Las credenciales del shopper (`@testpilot.internal`) se resuelven desde Secrets Manager via `environment_id`. El payload nunca contiene credenciales.
- AC2. La tarjeta usada en `_fill_payment` se carga de env var `TEST_DECLINE_CARD` (default `4000000000000002` — Stripe-test garantizada de declinación).
- AC3. `FlowResult.orders_created` siempre es `0`; `runner.py` lo valida con `assert` antes de retornar.
- AC4. Test: si `orders_created != 0`, `generate_report` lanza `AssertionError` (defense-in-depth).

**Origen PRD**: P1, RNF-02, M6. **Decisión**: D2.

---

### H1.3 — Verificación explícita de mensaje de declinación
**Como** Carolina,
**quiero** que el sistema valide visualmente que aparece el mensaje de "tarjeta rechazada",
**para** confirmar que SFCC maneja correctamente el error de pago.

**AC**:
- AC1. El flow `checkout_card_declined` incluye un step `verify_decline_message`.
- AC2. El step valida el texto visible contra el patrón regex `/tarjeta.*(rechaz|declin)/i` (case-insensitive). El patrón se centraliza en `selectors.py` como constante `DECLINE_MESSAGE_PATTERN`.
- AC3. Si el patrón no aparece en 5s, el step se marca `failed` con `error="decline_message_not_found"`.
- AC4. Si el step falla, el flow completo es `status="failed"` (no `"error"`).

**Origen PRD**: UC3, RF-07. **Decisión**: D3.

---

### H1.4 — Distinción entre error de infra y bug de tienda
**Como** Carolina,
**cuando** una ejecución falla por timeout de red ajeno a SFCC,
**quiero** que el sistema lo marque como `infrastructure_error` y no como bug de tienda,
**para** no bloquear el merge por algo que no es responsabilidad de mi PR.

**AC**:
- AC1. `InfrastructureError` se lanza cuando `playwright.errors.TimeoutError` ocurre en **navegación** (`page.goto`, `wait_for_load_state`, `page.reload`). Los `TimeoutError` esperando selector (`wait_for_selector`) son app-error y NO lanzan `InfrastructureError`.
- AC2. Cuando se lanza `InfrastructureError`, `RunRecord.status = "error"` (distinto de `"failed"`).
- AC3. `TrafficLight` para un run con `status="error"` es `YELLOW` (no `RED`).
- AC4. El reporte Markdown incluye una línea destacada "infraestructura, no producto" cuando aplica.

**Origen PRD**: Journey 3, M17. **Decisión**: D4.

---

### H1.5 — Disciplina de screenshots
**Como** responsable de costos,
**quiero** capturar screenshots solo cuando hay fallo y en el paso final,
**para** tener evidencia accionable sin desperdiciar storage ni llenar el reporte de ruido visual.

**AC**:
- AC1. `take_screenshot` se invoca cuando `step.status == "failed"` y en el paso final de cada flow ejecutado.
- AC2. Los steps `skipped` y los steps OK intermedios nunca generan screenshot.
- AC3. La ruta se controla por env var `SCREENSHOT_DIR`. Default `./screenshots` cuando `ENV != "production"`; cuando `ENV == "production"`, la app falla en startup si la env var no está seteada o si no existe `S3_BUCKET_SCREENSHOTS`. Naming: `{run_id}/{perfil}/{flujo}/{paso}-{fail|final}.png`.
- AC4. Test: un flow exitoso de 10 steps produce exactamente 1 screenshot final; un flow con un fallo produce screenshot del fallo y, si aplica, screenshot final del estado terminal.

**Origen PRD**: BR-U1-04, "Screenshot discipline" de `PRODUCT.md` / `AGENTS.md`. **Decisión**: D5.

---

## U2 — Baseline Manager (5 historias)

### H2.1 — Alerta por regresión de performance
**Como** Carolina,
**quiero** ser alertada cuando el tiempo de carga supera 1.2× el p95 reciente,
**para** detectar regresiones de performance antes del deploy.

**AC**:
- AC1. `compute_traffic_light(current_ms, p95_ms, bootstrap=False)` retorna `YELLOW` si `1.2*p95_ms < current_ms <= 1.5*p95_ms`.
- AC2. Retorna `RED` si `current_ms > 1.5*p95_ms`.
- AC3. Retorna `GREEN` si `current_ms <= 1.2*p95_ms`.
- AC4. PBT (hypothesis): para cualquier `current_ms` y `p95_ms` positivos, la función es monotónica en `current_ms` (más lento ⇒ semáforo peor o igual).

**Origen PRD**: UC2, M11, PBT-09.

---

### H2.2 — Bootstrap honesto (cero amarillos en primeras 14 corridas)
**Como** Andrés (Tech Lead),
**quiero** que durante las primeras 14 corridas exitosas el sistema NO emita amarillos por performance,
**para** no perder credibilidad con falsos positivos cuando aún no hay base estadística.

**AC**:
- AC1. `is_bootstrap_mode(runs)` retorna `True` si la lista de runs tiene menos de 14 entradas con `status="success"`.
- AC2. `compute_traffic_light(..., bootstrap=True)` siempre retorna `GREEN`.
- AC3. El reporte Markdown incluye un disclaimer `"modo bootstrap (X/14 runs)"` cuando aplica.
- AC4. PBT: `compute_traffic_light(any_current, any_p95, bootstrap=True) == GREEN` (invariante).

**Origen PRD**: M12, P4.

---

### H2.3 — Consulta de histórico para tendencias (alcance MVP)
**Como** Andrés,
**quiero** consultar el último run y runs específicos por `run_id`,
**para** revisar el estado actual y casos concretos sin perder contexto.

**AC**:
- AC1. `baseline_store.get_last_n_runs(profile, flow, n)` retorna lista ordenada por `created_at` descendente.
- AC2. Si hay menos de `n` runs, retorna los que haya (no falla).
- AC3. `GET /v1/runs/latest` retorna el más reciente con `ageSeconds` y `ttlOk` (true si `<14400s`).
- AC4. Endpoint de agregación temporal (`?since=...&aggregate=daily`) queda fuera de MVP — se traslada a SHOULD HAVE.

**Origen PRD**: Journey 2 (parcial), UC5, M11. **Decisión**: D6.

---

### H2.4 — Solo runs success entran al p95
**Como** ingeniero del equipo,
**quiero** que solo runs con `status="success"` cuenten en el cálculo del p95,
**para** que una falla genuina no contamine el baseline a futuro.

**AC**:
- AC1. `calculate_p95(runs)` filtra primero por `status == "success"`.
- AC2. Si después del filtro la lista está vacía, retorna `0`.
- AC3. PBT: `calculate_p95(mixed_runs) == calculate_p95([r for r in mixed_runs if r.status=='success'])`.
- AC4. Para lista no vacía, el resultado está en `[min(durations), max(durations)]` (rango).

**Origen PRD**: decisión de diseño documentada en `u2/code-summary.md`; PBT-07.

---

### H2.5 — Baseline store swappable (Protocol pattern)
**Como** ingeniero del equipo,
**quiero** que el `BaselineStore` sea swappable a DynamoDB sin tocar U3/U4,
**para** no rehacer los endpoints cuando promovamos a producción.

**AC**:
- AC1. `BaselineStore` se define como `Protocol` (`typing.Protocol`, `@runtime_checkable`) con métodos: `save_run`, `get_last_n_runs`, `get_run`.
- AC2. `InMemoryBaselineStore` implementa el Protocol completamente.
- AC3. Los consumidores (`ReportGenerator`, endpoints) dependen del Protocol, no de la implementación concreta (parámetro tipado como `BaselineStore`).
- AC4. Test: se puede crear un `MockBaselineStore` que implemente el Protocol e inyectarlo en `generate_report` sin cambios de código.

**Origen PRD**: M10. **Decisión**: D13.

---

## U3 — Reporter (3 historias)

> Nota: la historia original H3.3 (clasificador LLM con `confidence` / `requires_human_review`) fue **descartada** del MVP por decisión D7. El Journey 4 del PRD se aplaza a SHOULD HAVE. Las historias H3.1, H3.2 y H3.4 se mantienen; H3.4 se renumera a H3.3.

### H3.1 — Reporte Markdown legible en 30 segundos
**Como** Carolina,
**quiero** un reporte Markdown con semáforo visible al inicio,
**para** decidir el merge en 30 segundos sin leer 6 logs.

**AC**:
- AC1. La primera línea del Markdown contiene el emoji del semáforo (🟢/🟡/🔴).
- AC2. La segunda sección muestra `orders_created: 0` destacado.
- AC3. Cada perfil tiene una tabla con columnas `step | status | duration_ms`.
- AC4. La sección final compara contra baseline p95 si no es bootstrap; si es bootstrap, muestra el disclaimer.

**Origen PRD**: M7, Journey 1 paso 4.

---

### H3.2 — JSON estable para agentes CI/CD
**Como** agente CI/CD,
**quiero** un JSON estable (camelCase, schema validado),
**para** parsearlo sin lógica condicional por campo.

**AC**:
- AC1. `to_json_dict(report)` produce un dict que valida contra `specs/execution_report.schema.json` (`additionalProperties: false`).
- AC2. Todas las claves son camelCase (`testRunId`, `trafficLight`, `baselineComparison`).
- AC3. PBT (round-trip): para cualquier `ExecutionReport` válido, `ExecutionReport(**parse(to_json_dict(r)))` reconstruye un objeto equivalente.
- AC4. El dict NO incluye `ordersCreated` (la invariante se valida vía `assert`, no se publica en el contrato).

**Origen PRD**: UC4, M16, PBT-08.

---

### H3.3 — Auditabilidad de `orders_created=0` *(renumerada desde H3.4)*
**Como** auditor interno,
**quiero** que `orders_created=0` sea la primera assertion del `generate_report`,
**para** que un bug futuro en U3 nunca pueda emitir un reporte con órdenes reales.

**AC**:
- AC1. Primera línea ejecutable de `generate_report`: `assert all(p.flow_result.orders_created == 0 for p in profile_results)`.
- AC2. Si la assertion falla, el `AssertionError` incluye qué perfil/flow violó la invariante.
- AC3. Test inyecta un `ProfileResult` mock con `orders_created=1` y verifica que `generate_report` lanza.

**Origen PRD**: P1, RNF-02 (defense-in-depth).

---

## U4 — API Endpoints (5 historias)

### H4.1 — Invocación con instrucción en lenguaje natural
**Como** Carolina,
**quiero** invocar TestPilot con un POST y texto en español,
**para** no tener que aprender un DSL.

**AC**:
- AC1. `POST /v1/run` recibe un `SyntheticUserConfig` estructurado (Pydantic): `{environment_id, products[], flows[], profiles[], capture_intermediate_screenshots=false}`. Sin credenciales en el payload — el backend las resuelve desde Secrets Manager vía `environment_id`.
- AC2. Si el payload no valida contra `synthetic_user_config.json` (vía Pydantic), el endpoint retorna 422 con `{error_code: "validation_failed", details: "..."}`. (Translator NL queda fuera del path principal — ver D8 actualizada).
- AC3. El servidor genera `run_id` como UUID4 server-side (idempotencia con `Idempotency-Key` header queda en SHOULD HAVE, no MVP).
- AC4. La respuesta incluye `testRunId` en el body y `X-Run-Id` en el header.
- AC5. Timeout global del run: 1800s (30 min, env var override `RUN_TIMEOUT_SECONDS`). Si lo excede → 504 con `{error_code: "run_timeout"}`. *(actualizado 2026-05-24 — el flow con dos autenticaciones + 10 pasos × 3 perfiles requiere mayor margen)*

**Origen PRD**: M1, Journey 1 paso 1. **Decisiones**: D8, D9, D10.

---

### H4.2 — Consulta del último run
**Como** Andrés,
**quiero** consultar `/v1/runs/latest`,
**para** saber el último estado de la tienda sin recordar un `run_id`.

**AC**:
- AC1. `GET /v1/runs/latest` retorna 200 con el último `ExecutionReport` por `created_at`.
- AC2. Incluye `ageSeconds` y `ttlOk` (true si `<14400s` = 4h).
- AC3. Si no hay runs, retorna 404 con `{error_code: "no_runs_yet"}`.
- AC4. Sin `X-API-Key` válida → 401.

**Origen PRD**: M2.

---

### H4.3 — Consulta por `run_id`
**Como** agente CI/CD,
**quiero** consultar `GET /v1/runs/{id}`,
**para** tomar la decisión de merge sobre un run específico.

**AC**:
- AC1. `GET /v1/runs/{run_id}` retorna 200 con `ExecutionReport` si existe.
- AC2. Si `run_id` no es UUID4 válido → 422 (Pydantic validation).
- AC3. Si `run_id` no existe en el store → 404 con `{error_code: "run_not_found"}`.
- AC4. Sin `X-API-Key` válida → 401.

**Origen PRD**: M2. **Decisión**: D9.

---

### H4.4 — Autenticación por API key
**Como** responsable de seguridad,
**quiero** que ningún endpoint responda sin `X-API-Key` válida,
**para** que el sistema no quede expuesto en la red interna.

**AC**:
- AC1. Los 3 endpoints validan `X-API-Key` antes del handler (vía `Depends(verify_api_key)`).
- AC2. La key esperada se carga de env var `TESTPILOT_API_KEY` en startup.
- AC3. Si `TESTPILOT_API_KEY` no está seteada al iniciar la app, la app falla loud con `RuntimeError("TESTPILOT_API_KEY not set")` antes de aceptar requests.
- AC4. Header ausente o incorrecto → 401 con `{error_code: "unauthorized"}` (sin distinguir entre "falta" vs "incorrecta" para no filtrar info).

**Origen PRD**: P5, RNF-06, SECURITY-08. **Decisión**: D11.

---

### H4.5 — Errores 500 sin stack traces (logging estructurado con redacción)
**Como** auditor de seguridad,
**quiero** que ningún error retorne stack traces al cliente,
**para** no filtrar estructura interna del sistema.

**AC**:
- AC1. Cualquier `Exception` no esperada → 500 con `{error_code: "internal_error", request_id: "..."}` (sin traceback, sin nombres de archivo).
- AC2. Cualquier `InfrastructureError` no manejada en flow → 503 con `{error_code: "infrastructure_error"}`.
- AC3. El `request_id` se incluye en los logs estructurados (correlacionable server-side).
- AC4. Logging: stdlib `logging` configurado con `JSONFormatter` custom. Un filtro de redacción aplica a todos los handlers: redacta valores cuyo header sea `X-API-Key`, env var sea `ANTHROPIC_API_KEY` o cuyo campo del config tenga nombre matching `(?i)(password|token|card|key)`.

**Origen PRD**: RNF-04, SECURITY-15. **Decisión**: D12.

---

---

## MD0 — Dashboard Web Interno (4 historias)

### H5.1 — Registro de ambientes desde dashboard
**Como** Carolina (ingeniera SFCC),
**quiero** registrar los 3 ambientes (sandbox/development/staging) en el dashboard con su URL y paths de Secrets Manager,
**para** que el equipo pueda lanzar runs sin conocer los detalles de infraestructura.

**AC**:
- AC1. El dashboard tiene una pantalla de "Ambientes" con formulario: `environment_id` (enum), `display_name`, `store_url`, `env_access_secret_path`, `shopper_secret_path`, `anti_bot_whitelisted`.
- AC2. El registro persiste entre sesiones (no se pierde al recargar el dashboard).
- AC3. Si un campo requerido está vacío, el formulario bloquea el guardado con mensaje claro.
- AC4. El dashboard NO solicita ni muestra los valores de las credenciales — solo los paths en Secrets Manager.

**Origen PRD**: M19, MD0.

---

### H5.2 — Lanzamiento de run desde dashboard
**Como** Carolina,
**quiero** configurar y lanzar una ejecución de pruebas desde el dashboard con un campo JSON,
**para** no tener que usar curl ni conocer la API REST.

**AC**:
- AC1. El dashboard tiene un campo JSON pre-rellenado con un ejemplo válido de `SyntheticUserConfig`.
- AC2. El JSON no incluye `store_url`, `email` ni credenciales — solo `environment_id`, `products`, `flows`, `profiles`.
- AC3. Al hacer click en "Lanzar", el dashboard hace POST /v1/run y muestra el `testRunId` retornado.
- AC4. Si el JSON es inválido, el dashboard muestra el error de validación antes de enviar.

**Origen PRD**: M19, UC1.

---

### H5.3 — Vista en tiempo real de agentes activos
**Como** Andrés (Tech Lead),
**quiero** ver en tiempo real qué perfiles están ejecutando y cuál es su estado,
**para** saber si puedo aprobar el merge antes de que termine el run completo.

**AC**:
- AC1. El dashboard muestra, por cada perfil activo (mobile-CO, desktop-CO, desktop-EC): nombre, estado (en progreso / completado / fallido), paso actual.
- AC2. La vista se actualiza sin recargar la página (polling cada 5s o WebSocket).
- AC3. Un perfil completado muestra su semáforo individual inmediatamente.
- AC4. Si todos los perfiles completan, el semáforo global del run es visible en < 2s después del último perfil.

**Origen PRD**: M19, Journey 1.

---

### H5.4 — Historial de ejecuciones
**Como** Andrés,
**quiero** ver el historial de los últimos runs con su semáforo y métricas,
**para** identificar tendencias de performance a lo largo del tiempo.

**AC**:
- AC1. El historial muestra: fecha, ambiente, semáforo, duración total, perfiles ejecutados.
- AC2. El historial es filtrable por ambiente (sandbox/development/staging) y por semáforo (verde/amarillo/rojo).
- AC3. Al hacer click en un run, se ve el detalle: steps, screenshots, comparación con baseline p95.
- AC4. El historial persiste al menos 30 días.

**Origen PRD**: M19, Journey 2.

---

## Resumen

| Unidad | Historias | AC totales |
|---|---|---|
| U0 Setup | 3 (H0.1–H0.3) | 11 |
| U1 Executor | 5 (H1.1–H1.5) | 20 |
| U2 Baseline | 5 (H2.1–H2.5) | 20 |
| U3 Reporter | 3 (H3.1–H3.3) | 11 |
| U4 API | 5 (H4.1–H4.5) | 21 |
| MD0 Dashboard | 4 (H5.1–H5.4) | 16 |
| **Total** | **25** | **99** |

**Cambios vs draft v1**:
- Descartada: H3.3 original (clasificador LLM, decisión D7)
- Renumerada: H3.4 → H3.3
- Agregada: H2.5 (Protocol pattern para baseline store, decisión D13)
- Actualizada: H1.1 — `mobile/MX` → `desktop/EC (Ecuador)`
- Actualizada: H1.2 — email removido de payload; credenciales en Secrets Manager
- Actualizada: H1.5 — screenshots solo en fallo + paso final, según ADR-002 y `AGENTS.md`
- Agregadas: H5.1–H5.4 (Dashboard MD0 — MUST HAVE)
- 12 marcas `[?]` resueltas e incorporadas a los AC; las decisiones quedan trazadas en la sección "Design Decisions" de este documento.
