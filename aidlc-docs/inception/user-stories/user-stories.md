# User Stories — TestPilot SFCC

**Estado**: Iteración 3 — realineación de alcance 2026-06-03 (pendiente aprobación HITL)
**Origen**: Etapa User Stories formalizada el 2026-05-22; iteración 3 agrega las historias del alcance realineado (recorrido completo, auditoría 6 dimensiones, ventana NL, captura de red) — ver `../scope-realignment-brief.md`
**Trazabilidad**: cada historia referencia al menos un elemento del PRD (Journey, UC, MoSCoW M*, principio P*, RNF*) y los RF del `requirements.md` realineado
**Cobertura MoSCoW**: ver `coverage-matrix.md`

**Personas** (PRD §3 + UC6): Carolina (ingeniera SFCC) · Andrés (Tech Lead) · Sebastián (dev junior) · agente CI/CD · **Valentina (QA, perfil no-técnico — nueva, realineación UC6)**

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
| D14 *(2026-06-03)* | **D7 supersedida** por realineación: se restaura el clasificador como **agente de auditoría que sintetiza, no juzga** (P7). J4 des-aplazado parcialmente vía `requires_human_review` | H7.2, H7.3 | J4, M21 |
| D15 *(2026-06-03)* | `full_journey` es **composición declarada** de flows modulares en el catálogo — NO un flow archivo propio (evita duplicar selectores, riesgo R2) | H6.3 | M20 |
| D16 *(2026-06-03)* | Evidencia **dirigida por hallazgos**: fallo+final siempre; en auditoría además hallazgos (6 dimensiones) y puntos críticos declarados. Nunca capturas "porque sí". Refina D5/ADR-002 sin romper su presupuesto | H7.4 (H1.5 sigue vigente para modo gate) | decisión brief §7-#5 |
| D17 *(2026-06-03)* | Modos `gate` (determinista, entra a baseline) y `exploratory` (descubrimiento, NUNCA entra a baseline ni cuenta como deploy-safe) | H9.3 | PRODUCT.md §1 |
| D18 *(2026-06-03)* | **D8 ampliada**: la ventana NL es la entrada principal de UX (traducir → preview → confirmar); el contrato de `POST /v1/run` sigue siendo payload estructurado — la NL nunca llega al executor | H9.1, H9.2 | M23, UC6 |

---

## U0 — Setup Base (3 historias)

### H0.1 — `SyntheticUserConfig` único punto de definición
**Como** ingeniero del equipo TestPilot,
**quiero** que `SyntheticUserConfig` se defina en un solo lugar del repo,
**para** que cambios futuros (ej. agregar un campo) no se rompan en silencio entre `translator.py` y `api/main.py`.

**AC**:
- AC1. `SyntheticUserConfig` está definido únicamente en `src/models.py`.
- AC2. `src/agents/translator.py` y `src/api/main.py` lo importan desde `src.models` (no lo redefinen).
- AC3. Test (`test_models.py`) verifica que se puede instanciar con todos los campos del JSON Schema (`specs/synthetic-user-config.schema.json`).
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
> **Actualización 2026-06-03 (D14):** D7 quedó supersedida — la capacidad regresa como **agente de auditoría** (sintetiza, no juzga) en la unidad U6, historias H7.2/H7.3. Las historias de U3 no cambian: el semáforo sigue siendo determinista.

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
- AC2. Si el payload no valida contra `synthetic-user-config.schema.json` (vía Pydantic), el endpoint retorna 422 con `{error_code: "validation_failed", details: "..."}`. (Translator NL queda fuera del path principal — ver D8 actualizada).
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

### H5.5 — Matriz de ejecución genérica sobre flows *(★ realineación 2026-06-03)*
**Como** Andrés (Tech Lead),
**quiero** que la vista en vivo sea una matriz perfiles × flows construida desde los datos del run,
**para** que agregar flows nuevos al catálogo nunca requiera retocar el dashboard.

**AC**:
- AC1. La matriz se deriva de `profiles[]` y `flows[]` del run en curso — ningún nombre de flow está hardcodeado en el código del dashboard (no asume "checkout" ni exactamente 2 flows).
- AC2. Cada celda perfil×flow muestra estado vivo: `pending / running / passed / failed / error`.
- AC3. La vista de resultados enlaza el documento de auditoría (H7.2) cuando existe, y distingue visualmente runs `gate` vs `exploratory` (D17).
- AC4. El dashboard muestra las runs restantes del día (cap 10 runs/día visible — principio de producto "el costo es visible").

**Origen PRD**: M19, brief Y1. **RF**: RF-29. **Decisión**: D17.

---

## U5 — Flows de Recorrido (4 historias — ★ realineación 2026-06-03)

> Requiere puerta HITL de `specs/` (enum de flows) antes de construcción. RFs: RF-21, RF-22.

### H6.1 — Catálogo de flows de recorrido (cerrado, modular)
**Como** Carolina (ingeniera SFCC),
**quiero** flows propios para búsqueda/PLP, PDP y carrito — no solo pasos dentro del checkout,
**para** validar el recorrido de la tienda sin tener que ejecutar un checkout completo cada vez.

**AC**:
- AC1. El catálogo agrega 4 flows: `search_and_filter`, `browse_discounted_products`, `pdp_validation`, `cart_review` — cada uno archivo propio en `src/executor/flows/` con la misma firma `run(page, config, env, run_id, profile_id) -> FlowResult` que los flows de checkout.
- AC2. Ningún flow de recorrido contiene pasos de pago/checkout — solo los flows `checkout_*` tocan pago (P1 acotado a un solo lugar).
- AC3. Todos los selectores nuevos viven en `selectors.py` (C7); el despacho en `runner.py` es genérico (registro de catálogo, no if/else por flow).
- AC4. El catálogo sigue **cerrado**: un `flows[]` con valor fuera del enum se rechaza en validación de schema, jamás llega al executor.

**Origen PRD**: M20, MD5. **RF**: RF-21.

---

### H6.2 — Probar solo el módulo que me interesa
**Como** Valentina (QA, perfil no-técnico),
**quiero** lanzar una prueba de un solo módulo (p.ej. solo el carrito),
**para** validar el cambio que me importa sin esperar el recorrido completo.

**AC**:
- AC1. Un run con `flows: ["cart_review"]` (un solo flow modular) es válido y ejecuta solo ese módulo.
- AC2. El flow se auto-prepara: su `setup()` determinista satisface las precondiciones (p.ej. busca y añade un producto antes de revisar el carrito) sin intervención del usuario.
- AC3. Los pasos del `setup()` se reportan separados de los pasos del flow bajo prueba (un fallo de setup es `error` de precondición, no `failed` del módulo).
- AC4. El reporte y la matriz del dashboard muestran solo lo ejecutado (sin celdas fantasma de flows no pedidos).

**Origen PRD**: UC6, decisión brief §7-#2. **RF**: RF-21 AC3, RF-22 AC4.

---

### H6.3 — Recorrido completo como composición (`full_journey`)
**Como** Carolina,
**quiero** lanzar el recorrido completo de la tienda con una sola opción,
**para** validar búsqueda → PDP → carrito → checkout como lo viviría un cliente real.

**AC**:
- AC1. `full_journey` se declara en UN solo lugar del catálogo como secuencia ordenada (`search_and_filter` → `pdp_validation` → `cart_review` → `checkout_full`) — NO existe un archivo `full_journey.py` con pasos duplicados (D15).
- AC2. El runner ejecuta la composición encadenada preservando el contexto del browser (sesión, carrito) entre flows; los `setup()` intermedios se omiten.
- AC3. Si un flow de la composición falla, los siguientes se marcan `skipped` y el reporte indica en qué eslabón se cortó el recorrido.
- AC4. El resultado reporta cada flow de la composición por separado (la matriz muestra una columna por flow, no una columna "full_journey" monolítica).

**Origen PRD**: M20, PRODUCT.md §1. **RF**: RF-22. **Decisión**: D15.

---

### H6.4 — Validación de productos con descuento
**Como** Valentina,
**quiero** verificar que los productos en oferta muestran su descuento correctamente,
**para** confirmar una promoción antes del deploy sin revisarla a mano.

**AC**:
- AC1. `browse_discounted_products` navega a una PLP de promociones/ofertas y valida que los productos muestran precio original tachado + precio con descuento.
- AC2. El flow captura los precios observados (PLP y PDP del producto seleccionado) como datos estructurados para el colector de integridad de comercio (H7.1).
- AC3. Un descuento inconsistente (p.ej. precio final no corresponde al % anunciado) genera un hallazgo de integridad de comercio — no un fallo duro del flow (el flow falla solo si la página no carga o no hay productos).
- AC4. Funciona en los 3 perfiles (CO/EC) usando los selectores centralizados.

**Origen PRD**: M20 ("incl. productos con descuento"), UC6. **RF**: RF-21 AC1.

---

## U6 — Auditoría: Colectores + Agente (5 historias — ★ realineación 2026-06-03)

> Requiere puerta HITL de `specs/` (campos de auditoría en `execution_report.schema.json`). RFs: RF-24, RF-25, RF-26.

### H7.1 — Colectores deterministas de las 6 dimensiones
**Como** Andrés (Tech Lead),
**quiero** que los hallazgos de auditoría salgan de código determinista, no de un LLM,
**para** que cada hallazgo sea reproducible y verificable.

**AC**:
- AC1. Existen colectores para las 6 dimensiones: integridad de comercio (consistencia de precios PLP/PDP/carrito, promociones), rendimiento (de H8.1/H8.2), locale (moneda/idioma/formato por perfil), accesibilidad (axe-core en páginas clave, WCAG AA), salud del cliente (errores JS, requests 4xx/5xx, mixed content), contenido (meta/SEO, imágenes rotas, `alt`).
- AC2. Cada hallazgo es un objeto estructurado `{dimension, severity, page_url, step, data, evidence_refs[]}` generado sin intervención del LLM.
- AC3. El fallo de un colector individual degrada a "dimensión no recolectada" en el reporte — nunca tumba el flow.
- AC4. axe-core corre solo en páginas clave del flow (no en cada estado intermedio) — overhead total de colectores ≤ ~10% del tiempo del flow (RNF-15).

**Origen PRD**: M21, MD13, PRODUCT.md §1. **RF**: RF-24.

---

### H7.2 — Documento de auditoría legible para no-técnicos
**Como** Valentina,
**quiero** un documento de auditoría en lenguaje claro con cada hallazgo enlazado a su evidencia,
**para** entender el estado de la tienda sin leer logs ni JSON.

**AC**:
- AC1. El agente produce el documento en Markdown + representación JSON: resumen ejecutivo + una sección por dimensión.
- AC2. Cada hallazgo enlaza su evidencia (screenshot, URL, paso, entrada de red) — sin evidencia no hay hallazgo (principio "trazabilidad sobre opinión").
- AC3. El input del agente son exclusivamente los hallazgos/métricas sanitizados (sin credenciales, cookies ni PII — RNF-14); el agente nunca accede al browser.
- AC4. Las hipótesis del agente llevan `confidence` (0–1) y se presentan como hipótesis, nunca como hechos confirmados (P7).

**Origen PRD**: M21, MD2, P7, UC6. **RF**: RF-25. **Decisión**: D14.

---

### H7.3 — El agente no juzga; anomalías escalan a humano *(restaura J4)*
**Como** Sebastián (dev junior),
**cuando** el sistema detecta una anomalía sutil (p.ej. descuento aplicado a producto inelegible),
**quiero** que la marque `requires_human_review` con su hipótesis — sin decidir por mí,
**para** escalar al Tech Lead con evidencia en vez de dejar pasar el bug.

**AC**:
- AC1. Una anomalía de integridad de comercio produce `requires_human_review: true` en el hallazgo y semáforo AMARILLO **por regla determinista** — el agente la describe, no la veredicta.
- AC2. El semáforo verde/amarillo/rojo es un campo aparte calculado exclusivamente por `compute_traffic_light` (U2) — el documento de auditoría no lo contradice ni lo recalcula (C10).
- AC3. El reporte distingue los 3 sub-tipos de amarillo: `performance_regression`, `infrastructure_error`, `human_review`.
- AC4. Test: un set de hallazgos con anomalía de comercio produce YELLOW aunque el texto del agente sea optimista (el LLM no puede subir/bajar el semáforo).

**Origen PRD**: Journey 4 (des-aplazado), P7. **RF**: RF-25 AC4-AC5. **Decisión**: D14.

---

### H7.4 — Evidencia dirigida por hallazgos
**Como** responsable de costos,
**quiero** que las capturas extra existan solo cuando hay algo que resaltar,
**para** que el documento de auditoría tenga evidencia útil sin desperdiciar storage.

**AC**:
- AC1. Siempre (todos los modos): captura en fallo de paso + paso final (H1.5 intacta).
- AC2. En modo auditoría, captura adicional SOLO cuando: (a) un colector emite un hallazgo (captura en la página del hallazgo, enlazada en `evidence_refs`), o (b) el flow alcanza un punto crítico declarado en el catálogo (p.ej. resumen de pago).
- AC3. Nunca se captura un paso OK sin hallazgo ni punto crítico; `capture_intermediate_screenshots` sigue `const false` en el schema.
- AC4. Naming: `{run_id}/{perfil}/{flujo}/{paso}-{fail|final|finding-{dimension}|critical}.png`; lifecycle S3 90 días hot → Glacier; presupuesto KPI C4 del PRD vigente (≤1 GB sem 4).

**Origen PRD**: M9 refinado, decisión brief §7-#5. **RF**: RF-26. **Decisión**: D16.

---

### H7.5 — Degradación con gracia del agente
**Como** Carolina,
**cuando** la llamada al LLM de auditoría falla o excede su timeout,
**quiero** recibir igual el reporte con los hallazgos crudos,
**para** que el gate nunca dependa de la disponibilidad del agente.

**AC**:
- AC1. Si el agente falla/agota timeout, el `ExecutionReport` se emite igual con los hallazgos deterministas y una nota "síntesis no disponible" — el run nunca falla por el agente.
- AC2. La llamada al agente tiene timeout explícito y presupuesto de tokens acotado por constante configurable; al exceder el presupuesto, los hallazgos se truncan por prioridad de severidad y el documento lo declara (RNF-14).
- AC3. Test: con el cliente Claude mockeado para lanzar excepción, `generate_report` retorna reporte válido contra el schema.

**Origen PRD**: RNF-04, P4. **RF**: RF-25 AC6.

---

## U7 — Captura de Red / Performance (2 historias — ★ realineación 2026-06-03)

> Requiere puerta HITL de `specs/` (campos de red en `execution_report.schema.json`). RF: RF-23.

### H8.1 — Traza de red con timings de controllers SFRA
**Como** Carolina,
**quiero** ver los tiempos de respuesta de los controllers SFRA del recorrido,
**para** ubicar exactamente qué endpoint degradó cuando el semáforo da amarillo.

**AC**:
- AC1. Por cada par perfil×flow se captura traza estilo HAR vía Playwright: URL, método, status, tipo de recurso, timings, tamaño — restringida a allowlist de dominios del storefront.
- AC2. Los requests que matchean patrones de controllers SFRA (`*-Show`, `Cart-*`, `CheckoutServices-*`, etc.) se agregan en un resumen de timings por controller.
- AC3. Headers de autenticación y cookies se redactan ANTES de persistir; los bodies no se persisten (solo metadata + timings).
- AC4. El HAR filtrado va a S3 (`{run_id}/{perfil}/{flujo}/network.har.json`, mismo lifecycle que evidencia); el `ExecutionReport` lleva el resumen (totales, requests fallidos, p95 por controller) + referencia al HAR.

**Origen PRD**: M22, MD14, brief N1. **RF**: RF-23.

---

### H8.2 — Core Web Vitals por página clave
**Como** Andrés,
**quiero** LCP/CLS/TTFB de las páginas clave del recorrido por perfil,
**para** defender ante negocio el impacto de performance con métricas estándar.

**AC**:
- AC1. Se capturan LCP, CLS y TTFB en las páginas clave de cada flow (INP/TBT solo si no infla el tiempo del flow — RNF-15).
- AC2. Las métricas se reportan por perfil (mobile vs desktop difieren) en el `ExecutionReport`.
- AC3. El baseline p95 sigue operando sobre `durationMs` en esta ola; la extensión del baseline a CWV queda declarada como ola posterior (no recorte).

**Origen PRD**: M22, dimensión rendimiento de PRODUCT.md §1. **RF**: RF-23 AC2, AC6.

---

## U8 — Ventana NL + Modos de Operación (3 historias — ★ realineación 2026-06-03)

> Requiere puerta HITL de `specs/` (campo `mode`; contrato del endpoint de traducción). RFs: RF-27, RF-28.

### H9.1 — Valentina lanza una prueba describiéndola en español
**Como** Valentina (QA, perfil no-técnico),
**quiero** describir la prueba en español, ver qué se va a ejecutar y confirmarlo,
**para** validar la tienda por mi cuenta sin escribir JSON ni conocer la API.

**AC**:
- AC1. El dashboard ofrece un campo NL como vía principal (el editor JSON queda como vía avanzada).
- AC2. La traducción retorna el `SyntheticUserConfig` propuesto + explicación legible (flows, perfiles, productos, modo); el run solo se lanza tras confirmación explícita del usuario (preview obligatorio).
- AC3. `POST /v1/run` sigue recibiendo únicamente el payload estructurado validado — la instrucción NL nunca llega al executor (C12, D18).
- AC4. El mapeo NL→alcance cubre los casos de H6.2/H6.3: "revisa solo el carrito" → `cart_review`; "revisa toda la tienda" → `full_journey`.

**Origen PRD**: M23, UC6, Journey 1 paso 1. **RF**: RF-27. **Decisión**: D18.

---

### H9.2 — Traducción estricta: ambigüedad y prompt injection
**Como** responsable de seguridad,
**quiero** que toda traducción NL pase el mismo gate de schema + catálogo que un payload manual,
**para** que la ventana NL no abra una puerta trasera al executor.

**AC**:
- AC1. El config propuesto se valida contra JSON Schema + catálogo cerrado ANTES de mostrarse al usuario; instrucción fuera de catálogo → rechazo explicando el catálogo disponible.
- AC2. Instrucción ambigua → respuesta de clarificación (no se adivina); equivale a `400 AmbiguousInstruction`.
- AC3. Instrucción NL limitada a 2000 caracteres (RNF-05); intentos de prompt injection se rechazan y se loggean (RT1, meta Q8 = 0 ejecutados).
- AC4. Gate de calidad pre-lanzamiento: dataset D-NL con Q1 ≥90% configs válidos y Q2 = 100% adherencia al catálogo.

**Origen PRD**: P3, §11 (D-NL, RT1). **RF**: RF-27 AC4-AC5, AC7.

---

### H9.3 — Modo exploratorio sin contaminar el baseline
**Como** Andrés,
**quiero** que las pruebas exploratorias nunca entren al baseline ni cuenten como estado deploy-safe,
**para** que la experimentación libre no degrade la honestidad del semáforo.

**AC**:
- AC1. `SyntheticUserConfig.mode` acepta `gate` (default) y `exploratory`; ambos ejecutan solo flows del catálogo cerrado.
- AC2. Los runs `exploratory` NUNCA se escriben al baseline (`save_run` filtra por modo — C11) y su reporte se marca visiblemente; su semáforo es informativo, no veredicto de gate.
- AC3. `GET /v1/runs/latest` para decisión de deploy considera solo runs `gate`.
- AC4. El cap de 10 runs/día aplica a la suma de ambos modos.

**Origen PRD**: PRODUCT.md §1 (modos), P3, P4. **RF**: RF-28. **Decisión**: D17.

---

## Resumen

| Unidad | Historias | AC totales |
|---|---|---|
| U0 Setup | 3 (H0.1–H0.3) | 11 |
| U1 Executor | 5 (H1.1–H1.5) | 20 |
| U2 Baseline | 5 (H2.1–H2.5) | 20 |
| U3 Reporter | 3 (H3.1–H3.3) | 11 |
| U4 API | 5 (H4.1–H4.5) | 21 |
| MD0 Dashboard | 5 (H5.1–H5.5) | 20 |
| **U5 Flows de recorrido** | **4 (H6.1–H6.4)** | **16** |
| **U6 Auditoría** | **5 (H7.1–H7.5)** | **19** |
| **U7 Captura de red** | **2 (H8.1–H8.2)** | **7** |
| **U8 Ventana NL + modos** | **3 (H9.1–H9.3)** | **12** |
| **Total** | **40** | **157** |

**Cambios vs iteración 2 (2026-05-22) — realineación 2026-06-03**:
- Agregadas: H6.1–H6.4 (U5 flows de recorrido), H7.1–H7.5 (U6 auditoría), H8.1–H8.2 (U7 red), H9.1–H9.3 (U8 ventana NL + modos), H5.5 (matriz genérica MD0)
- Decisiones nuevas: D14–D18 (D7 supersedida → agente de síntesis; `full_journey` como composición; evidencia por hallazgos; modos gate/exploratorio; D8 ampliada con ventana NL)
- Persona nueva: Valentina (QA, no-técnica — actor de UC6)
- J4 des-aplazado parcialmente (H7.3)
- Las historias de iteración 2 NO cambian su semántica — el gate de checkout se construye como estaba

**Cambios vs draft v1** (histórico):
- Descartada: H3.3 original (clasificador LLM, decisión D7 — supersedida en iteración 3 por D14)
- Renumerada: H3.4 → H3.3
- Agregada: H2.5 (Protocol pattern para baseline store, decisión D13)
- Actualizada: H1.1 — `mobile/MX` → `desktop/EC (Ecuador)`
- Actualizada: H1.2 — email removido de payload; credenciales en Secrets Manager
- Actualizada: H1.5 — screenshots solo en fallo + paso final, según ADR-002 y `AGENTS.md`
- Agregadas: H5.1–H5.4 (Dashboard MD0 — MUST HAVE)
- 12 marcas `[?]` resueltas e incorporadas a los AC; las decisiones quedan trazadas en la sección "Design Decisions" de este documento.
