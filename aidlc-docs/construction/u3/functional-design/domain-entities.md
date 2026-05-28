# Domain Entities — U3 Reporter (actualizado 2026-05-24)

## Módulo: `src/reporter/report_generator.py`

U3 **consume** entidades de U0/U1/U2 y **produce** `ExecutionReport` + dos representaciones (dict JSON + str Markdown). No define entidades propias.

---

## Entidades consumidas

### ProfileResult (de U1, definido en U0)
Resultado por perfil. Entrada principal del reporter.
```python
class ProfileResult(BaseModel):
    profile: BrowserProfile
    flow_result: FlowResult
    traffic_light: TrafficLight  # parcial — U3 lo actualiza con baseline
```

### BaselineStore (de U2)
Protocol. U3 lo recibe inyectado y lo usa para:
- `get_last_n_runs(environment_id, profile, flow, n=10, status="success")` → calcular baseline
- `save_run(RunRecord)` → persistir el resultado actual

### SyntheticUserConfig (de U0)
Config del run — usado para metadata del reporte (productos buscados, perfiles solicitados).

### ResolvedEnvironment (de U0 — NUEVO consumo)
Necesario para extraer `environment_id` y agregarlo al reporte + usarlo como clave de baseline.

---

## Entidades producidas

### ExecutionReport (definido en U0)
Modelo top-level del reporte. **Cambios vs versión anterior:**
- `environment_id: EnvironmentId` ★ NUEVO top-level
- `bootstrap_mode: bool` ★ NUEVO top-level (antes solo dentro de `baseline_comparison` por perfil)
- `profile_results: list[ProfileResult]` con `traffic_light` actualizado

```python
class ExecutionReport(BaseModel):
    run_id: str
    environment_id: EnvironmentId
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    traffic_light: TrafficLight       # peor de los perfiles
    bootstrap_mode: bool              # OR de los perfiles
    orders_created: int = 0           # invariante
    profile_results: list[ProfileResult]
    baseline_comparison: BaselineComparison | None = None  # consolidado top-level
```

### dict JSON (output de `to_json_dict`)
Producido con `model_dump(mode="json", by_alias=True, exclude_none=True)`. Valida contra `specs/execution_report.json`.

**Formato:** camelCase (alineado con convención del schema). Pydantic field aliases manejan la conversión.

**Excluye:** campos `None`. Esto incluye `baseline_comparison` cuando no aplica (bootstrap puro).

### str Markdown (output de `to_markdown`)
Texto plano Markdown legible en CLI o renderizado. Estructura definida en `business-logic-model.md`.

---

## Entidades internas (helpers no exportados)

### `_determine_overall_status(profile_results) → Literal["success", "failed", "error"]`
Helper para BR-U3-03.

### `_worst_traffic_light(lights: list[TrafficLight]) → TrafficLight`
Helper para BR-U3-04.

### `_emoji_for_light(light: TrafficLight) → str`
Mapeo `GREEN → 🟢`, `YELLOW → 🟡`, `RED → 🔴`.

### `_format_duration(ms: int) → str`
Convierte milisegundos a string legible (`"11 min 23 s"`, `"45 s"`, `"890 ms"`).

### `_relative_to_p95(current_ms: int, p95_ms: int) → str`
Devuelve string como `"91% (p95=244s)"`. Si `p95_ms == 0`, retorna `"sin baseline"`.

---

## InvariantViolatedError
Excepción interna lanzada por BR-U3-01:
```python
class InvariantViolatedError(Exception):
    """Raised when a non-negotiable invariant (e.g., orders_created != 0) is violated."""
    pass
```

El handler de U4 captura esta excepción y produce:
- HTTP 500 al cliente con error_code `invariant_violated`
- Alerta CloudWatch crítica
- Log ERROR con detalles redactados

---

## Schemas externos consumidos

### `specs/execution_report.json`
JSON Schema (Draft 2020-12) que define el contrato del JSON output. `to_json_dict` valida contra este schema en cada llamada.

**Política de cambios:**
- Adición de campos optional → minor (backwards-compatible)
- Cualquier otra cosa (rename, required field, type change) → breaking → bump `/v2/`

**Mantenimiento:** el schema vive en `specs/` y es la fuente de verdad. Si Pydantic produce algo que no valida, el bug está en el modelo Pydantic.

---

## Resumen de tamaño de U3

U3 es delgada:
- 3 funciones públicas (`generate_report`, `to_json_dict`, `to_markdown`)
- ~5 helpers internos
- 1 excepción
- 0 entidades propias

Su valor está en **integración** (orquesta U1 + U2 + persistencia) y en **formato** (genera artefactos consumibles).
