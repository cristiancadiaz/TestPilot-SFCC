# NFR Requirements — U3 Reporter (2026-05-28)

## Contexto de la unidad

U3 es una unidad de **transformación y formateo puro**: recibe `ProfileResult[]` + `BaselineStore` + metadata y produce `ExecutionReport` + su representación JSON y Markdown. No tiene infraestructura propia — hereda compute de U4 (Lambda/ECS) y storage de U2 (BaselineStore). Su naturaleza es **síncrona y determinista**.

Dado ese perfil, las preocupaciones NFR más críticas son:
1. **Velocidad** — está en el camino crítico de `POST /v1/run`.
2. **Fidelidad del output** — el JSON debe honrar el contrato de `specs/execution_report.json` siempre.
3. **No fuga de información sensible** — el reporte lo lee un humano y lo parsea un agente CI/CD.
4. **Robustez del serializador** — ningún input válido puede hacer lanzar `to_markdown` o `to_json_dict`.

---

## Performance

### NFR-U3-P1: Latencia de `generate_report` — ruta crítica

`generate_report` debe completarse en **< 500 ms** (P95) bajo carga normal del MVP (1 run activo a la vez). El cuello de botella esperado es la serialización Pydantic, no el cálculo.

**Desglose esperado:**
| Paso | Tiempo estimado |
|---|---|
| Validar invariante `orders_created=0` | < 1 ms |
| `get_last_n_runs` × 6 (3 perfiles × 2 flows) | < 50 ms (InMemory) |
| `calculate_p95` × 6 | < 1 ms total |
| `save_run` × 6 | < 20 ms (InMemory) |
| Construir `ExecutionReport` (Pydantic) | < 10 ms |
| **Total** | **< 100 ms P95 en MVP** |

El margen hasta 500 ms absorbe varianza de GC y serialización. Post-MVP con DynamoDB, el objetivo escala a **< 2 s** (I/O de red incluido).

### NFR-U3-P2: `to_json_dict` — serialización rápida

`to_json_dict` (incluyendo validación `jsonschema`) debe ejecutarse en **< 200 ms** para un reporte completo de 6 perfiles. `model_dump(mode="json", by_alias=True)` es la ruta caliente — no se construyen strings intermedios.

### NFR-U3-P3: `to_markdown` — sin bloqueo

`to_markdown` debe ejecutarse en **< 50 ms** para 6 perfiles × pasos de checkout (estimado: 15–20 pasos por perfil). U3 no usa templates externos ni regex costosas.

---

## PBT — Property-Based Testing con hypothesis (BLOQUEANTE)

Referenciado en **RNF-09** de la matriz de arquitectura (`U2, U3 — Blocking`).

### PBT-U3-01: Round-trip `to_markdown` nunca lanza

Para cualquier `ExecutionReport` válido generado con `hypothesis.strategies`:
```python
for any valid ExecutionReport r: to_markdown(r) does not raise
```
**Propiedades verificadas:**
- El output es un string no vacío.
- La primera línea empieza con `# 🟢`, `# 🟡` o `# 🔴` según `r.traffic_light`.
- La línea `orders_created = 0` aparece en el output (BR-U3-08).

### PBT-U3-02: Round-trip `to_json_dict` — conformidad con schema

Para cualquier `ExecutionReport` válido:
```python
for any valid ExecutionReport r: jsonschema.validate(to_json_dict(r), SCHEMA) passes
```
**Propiedades verificadas:**
- El dict no contiene claves no declaradas en `specs/execution_report.json` (`additionalProperties: false`).
- `traffic_light` en el dict es uno de `["GREEN", "YELLOW", "RED"]`.
- `orders_created` siempre es `0`.

### PBT-U3-03: `_worst_traffic_light` — monotonicidad

Para cualquier lista de `TrafficLight`:
- Si al menos uno es RED → resultado es RED.
- Si al menos uno es YELLOW (y ninguno RED) → resultado es YELLOW.
- Si todos son GREEN → resultado es GREEN.
- La función es **idempotente**: `worst([worst(a, b), c]) == worst(a, b, c)`.

### PBT-U3-04: `bootstrap_mode` global — conservador

Para cualquier lista de `ProfileResult`:
- Si **cualquier** perfil tiene `bootstrap_mode=True` → `ExecutionReport.bootstrap_mode = True`.
- Solo si **todos** los perfiles tienen `bootstrap_mode=False` → `ExecutionReport.bootstrap_mode = False`.

---

## Reliability

### NFR-U3-R1: Determinismo total

Mismo set de `ProfileResult[]` + mismo `BaselineStore` state → mismo `ExecutionReport`. Las funciones `generate_report`, `to_json_dict` y `to_markdown` no dependen de `random`, `uuid4()` intermedio (el `run_id` viene como parámetro), ni de `datetime.now()` (el `started_at` viene como parámetro; solo `finished_at` se captura internamente).

### NFR-U3-R2: `InvariantViolatedError` nunca silenciada

Si `orders_created != 0` en cualquier `ProfileResult`, `InvariantViolatedError` debe propagarse hacia U4. U3 no tiene `except InvariantViolatedError` — solo lanza. El handler de U4 es el único que la captura y produce el HTTP 500.

**Razón:** silenciar esta excepción en U3 ocultaría un incidente de contaminación real.

### NFR-U3-R3: Schema validation no omitible

`to_json_dict` llama `jsonschema.validate(...)` en **cada invocación**, incluido en producción. No hay flag de desarrollo que lo deshabilite. La penalidad de rendimiento (< 200 ms) es aceptable a cambio de garantía de contrato.

**Razón:** el JSON es consumido por agentes CI/CD externos (UC4). Un reporte malformado silencioso es peor que una excepción temprana.

---

## Security

### NFR-U3-S1: Sin PII ni secretos en el reporte (BLOQUEANTE)

El output de `to_json_dict` y `to_markdown` **no debe contener**:
- Email del shopper (excepto en forma de `@testpilot.internal` — permitido, no es PII real).
- Contraseñas, tokens, API keys, ni ningún string que coincida con patrones de credencial.
- Paths internos del filesystem (e.g., `/home/runner/...`).
- Stack traces completos (solo el mensaje de error del step fallido).

**Verificación:** test de regex en `tests/test_reporter.py`:
```python
output = to_json_dict(report)
raw = json.dumps(output)
assert not re.search(r"password|secret|token|Authorization|Bearer", raw, re.IGNORECASE)
```

Referencia: **BR-U3-10**, **RNF-03** (structured logging without secrets).

### NFR-U3-S2: `orders_created` siempre visible en el JSON

El campo `orders_created: 0` **no puede excluirse** en la serialización (`exclude_none=True` no aplica porque es un int, no None). Debe ser auditable por cualquier consumidor del JSON sin tener que inspeccionar el Markdown.

**Razón:** auditabilidad de zero contamination — RNF-02.

---

## Maintainability

### NFR-U3-M1: Funciones puras sin side effects (excepto `generate_report`)

`to_json_dict`, `to_markdown`, `_worst_traffic_light`, `_determine_overall_status`, `_format_duration` y `_relative_to_p95` son **funciones puras**: sin I/O, sin escritura a estado compartido, sin imports que no sean stdlib o Pydantic. Testeables con `assert f(input) == expected` sin mocks.

La única función con side effects es `generate_report` (llama a `baseline_store.save_run`). Sus efectos se inyectan vía el parámetro `baseline_store: BaselineStore` — testeable mediante implementación in-memory o mock.

### NFR-U3-M2: Un solo módulo de implementación

U3 vive en `src/reporter/report_generator.py`. No se fragmenta en submódulos dentro de `src/reporter/` en MVP — toda la lógica en un archivo facilita la revisión y el onboarding. Si el archivo supera las 300 líneas, evaluar extracción en iteración posterior.

### NFR-U3-M3: Cambios al schema de reporte son breaking

Cualquier modificación a `specs/execution_report.json` que rompa la validación de `to_json_dict` es un **breaking change** que requiere:
1. Bump a `/v2/` en la API.
2. Actualización coordinada de U3 + U4.
3. Confirmación humana previa (invariante del CLAUDE.md).

---

## Aplicabilidad Security Baseline

| Regla | Aplica | Implementación en U3 |
|---|---|---|
| SECURITY-01 (Sin secrets hardcoded) | N/A | U3 no maneja secretos — los resuelve U4 |
| SECURITY-02 | N/A | — |
| SECURITY-03 (Validación de inputs) | ✅ | Pydantic valida `ExecutionReport` en U0; `jsonschema` valida el output |
| SECURITY-04 (No SQL injection) | N/A | U3 no hace queries — InMemoryStore en MVP |
| SECURITY-05 (Auth) | N/A | Responsabilidad de U4 |
| SECURITY-06 | N/A | — |
| SECURITY-07 | N/A | — |
| SECURITY-08 (Supply chain) | ✅ | Sin dependencias nuevas — hereda de U0 (`jsonschema` ya declarado) |
| SECURITY-09 (Rate limiting) | N/A | U4 |
| SECURITY-10 (Sin PII en logs/outputs) | ✅ | NFR-U3-S1 — test de regex sobre output |
| SECURITY-11 | N/A | — |
| SECURITY-12 | N/A | — |
| SECURITY-13 | N/A | — |
| SECURITY-14 | N/A | — |
| SECURITY-15 (Headers HTTP) | N/A | U4 y MD0 |

**Resumen U3:** 3/15 aplican (SECURITY-03, SECURITY-08, SECURITY-10). U3 es lógica de transformación — sin auth, sin I/O externo propio, sin infra propia.

---

## Aplicabilidad PBT (resumen)

| Regla | Estado | Nota |
|---|---|---|
| PBT-U3-01 (round-trip to_markdown) | ✅ BLOQUEANTE | Ningún input válido puede hacer lanzar |
| PBT-U3-02 (round-trip to_json_dict + schema) | ✅ BLOQUEANTE | Contrato con agentes CI/CD |
| PBT-U3-03 (_worst_traffic_light monotonicidad) | ✅ BLOQUEANTE | Semáforo incorrecto = deploy-gate inválido |
| PBT-U3-04 (bootstrap_mode conservador) | ✅ BLOQUEANTE | Falso negativo en bootstrap es más dañino que falso positivo |

**U3 comparte con U2 el rango de cobertura PBT más alto del proyecto** — su naturaleza de transformación pura lo justifica y facilita.

---

## Trazabilidad con RNFs de arquitectura

| NFR U3 | RNF arquitectura | Nota |
|---|---|---|
| NFR-U3-P1, P2, P3 | RNF-07 (executor performance) | U3 está en el camino crítico del run |
| PBT-U3-01 a 04 | RNF-09 (PBT baseline/reporting) | Bloqueante para MVP |
| NFR-U3-S1 | RNF-02 (zero contamination), RNF-03 (logging sin secrets) | Auditabilidad del reporte |
| NFR-U3-S2 | RNF-02 (zero contamination) | `orders_created` siempre visible |
| NFR-U3-R2, R3 | RNF-04 (safe error handling) | Invariante no silenciable |
| NFR-U3-M3 | RNF-05 (input validation), versionado API | Schema = contrato |
