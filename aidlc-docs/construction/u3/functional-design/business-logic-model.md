# Business Logic Model — U3 Reporter (actualizado 2026-05-24)

## Propósito desde la perspectiva del producto

U3 convierte resultados crudos (`ProfileResult[]`) + decisión de semáforo (de U2) en **dos artefactos legibles**: un JSON estructurado (consumido por agentes CI/CD y por el dashboard MD0) y un Markdown con emojis (consumido por Carolina y Andrés en Slack/CLI).

**Cambio mayor vs versión anterior:** el reporte ahora incluye `environment_id` top-level y consume el baseline pasándole `environment_id` (BR-U2-05 — baseline por ambiente).

**Outcomes de negocio:**
1. **Cierra el loop del UC1:** el output que Carolina ve en 30 segundos para aprobar el merge.
2. **Habilita el UC4 (agente CI/CD):** JSON sigue `specs/execution_report.json` estricto.
3. **Alimenta al dashboard MD0:** el modelo `ExecutionReport` se sirve directamente en `GET /v1/runs/{id}` para que la P4 lo renderice.
4. **Auditoría visible:** banner permanente "orders_created: 0" tanto en Markdown como en metadata del JSON.

---

## Componentes de U3

```
src/reporter/
├── __init__.py
└── report_generator.py
    │
    ├── generate_report(profile_results, baseline_store, config, run_id, env, started_at)
    │       → ExecutionReport
    │
    ├── to_json_dict(report) → dict
    │       (cumple specs/execution_report.json)
    │
    └── to_markdown(report) → str
            (formato human-friendly)
```

---

## Lógica de `generate_report`

```
INPUTS:
  - profile_results: list[ProfileResult]  (de U1)
  - baseline_store: BaselineStore         (de U2)
  - config: SyntheticUserConfig           (de la request)
  - run_id: str (UUID)
  - env: ResolvedEnvironment              (★ NUEVO — para environment_id)
  - started_at: datetime

PROCESO:
  1. Validar invariante crítica (BLOQUEANTE):
     assert all(pr.flow_result.orders_created == 0 for pr in profile_results)
     # Si falla: raise InvariantViolatedError + alerta crítica
  
  2. finished_at = datetime.now(timezone.utc)
     duration_ms = (finished_at - started_at).total_seconds() * 1000
  
  3. Para cada ProfileResult:
     - Obtener baseline runs del store:
         runs = baseline_store.get_last_n_runs(
             environment_id=env.config.environment_id,
             profile=pr.profile.name,
             flow=pr.flow_result.flow_name,
             n=10,
             status="success",
         )
     - p95 = calculate_p95(runs)
     - bootstrap = is_bootstrap_mode(runs)
     - light = compute_traffic_light(
           current_ms=pr.flow_result.duration_ms,
           p95_ms=p95,
           bootstrap=bootstrap,
       )
     - Actualizar pr.traffic_light = light
     - Crear BaselineComparison por perfil
  
  4. Persistir RunRecord por cada perfil:
     for pr in profile_results:
         baseline_store.save_run(RunRecord(
             run_id=run_id,
             environment_id=env.config.environment_id,
             profile_name=pr.profile.name,
             flow_name=pr.flow_result.flow_name,
             duration_ms=pr.flow_result.duration_ms,
             status=pr.flow_result.status,
             created_at=finished_at,
         ))
  
  5. Determinar traffic_light del REPORTE completo:
     overall_light = worst_of([pr.traffic_light for pr in profile_results])
     # RED > YELLOW > GREEN
  
  6. Determinar bootstrap_mode global:
     overall_bootstrap = any(BaselineComparison.bootstrap_mode for pr in profile_results)
     # Si CUALQUIER perfil aún está en bootstrap, el run completo se etiqueta como bootstrap
  
  7. Construir ExecutionReport:
     return ExecutionReport(
         run_id=run_id,
         environment_id=env.config.environment_id,
         started_at=started_at,
         finished_at=finished_at,
         duration_ms=duration_ms,
         traffic_light=overall_light,
         bootstrap_mode=overall_bootstrap,
         orders_created=0,                      # invariante
         profile_results=profile_results,
         baseline_comparison=overall_baseline_comparison,  # consolidado
     )

OUTPUT: ExecutionReport (modelo Pydantic de U0)
```

---

## Determinación del status global (helper interno)

```python
def _determine_overall_status(
    profile_results: list[ProfileResult],
) -> Literal["success", "failed", "error"]:
    """
    - success: todos los profiles completaron sin error.
    - failed: al menos un flow tuvo step fallido (no infrastructure_error).
    - error: al menos un profile tuvo infrastructure_error.
    """
    statuses = [pr.flow_result.status for pr in profile_results]
    if "error" in statuses:
        return "error"
    if "failed" in statuses:
        return "failed"
    return "success"


def _worst_traffic_light(lights: list[TrafficLight]) -> TrafficLight:
    """RED > YELLOW > GREEN"""
    if TrafficLight.RED in lights:
        return TrafficLight.RED
    if TrafficLight.YELLOW in lights:
        return TrafficLight.YELLOW
    return TrafficLight.GREEN
```

---

## Lógica de `to_json_dict`

```python
def to_json_dict(report: ExecutionReport) -> dict:
    """
    Serializa ExecutionReport al formato definido por specs/execution_report.json (camelCase).
    Valida contra el JSON Schema antes de retornar.
    """
    raw = report.model_dump(mode="json", by_alias=True, exclude_none=True)
    
    # Asegurar shape exacta del schema
    # (Pydantic con by_alias=True ya produce camelCase si los modelos usan alias)
    
    validate(instance=raw, schema=EXECUTION_REPORT_SCHEMA)  # jsonschema lib
    return raw
```

**Schema:** `specs/execution_report.json` (definido en repo). Cualquier cambio al schema es **breaking change** del API. Versionado vía `/v1/`.

---

## Lógica de `to_markdown`

Genera un Markdown legible. Estructura:

```markdown
# 🟢 TestPilot Run abc123-de45 — STAGING

**Status:** ✅ success • **Bootstrap:** false • **Duración:** 11 min 23 s

> 🔒 Auditoría: `orders_created = 0`

## Resultados por perfil

| Perfil | Flow | Status | Duración | vs p95 | Semáforo |
|---|---|---|---|---|---|
| mobile-co | checkout-full | success | 222 s | 91% (p95=244s) | 🟢 |
| desktop-co | checkout-full | success | 198 s | 88% (p95=225s) | 🟢 |
| desktop-ec | checkout-full | success | 215 s | 95% (p95=226s) | 🟢 |
| mobile-co | checkout-card-declined | success | 188 s | 92% (p95=204s) | 🟢 |
| desktop-co | checkout-card-declined | success | 178 s | 90% (p95=197s) | 🟢 |
| desktop-ec | checkout-card-declined | success | 192 s | 94% (p95=204s) | 🟢 |

## Comparación con baseline

- Baseline: últimos 10 runs success por (environment, perfil, flow)
- Bootstrap: false (11 runs success en historial)
- Peor desviación: desktop-ec / checkout-full — 95% de p95

## Detalle de pasos por perfil

### mobile-co / checkout-full
| # | Step | Status | Duración | Screenshot |
|---|---|---|---|---|
| 1 | env_access_auth | ✅ | 1.4s | abc123/mobile-co/checkout-full/env_access_auth-ok.png |
| 2 | shopper_login | ✅ | 2.8s | ...ok.png |
| ... | ... | ... | ... | ... |

(continúa para los demás perfiles)
```

**Si el run es RED:**
- Header en rojo con emoji 🔴
- Sección destacada al inicio con los steps fallidos por perfil
- Banner: "Acción requerida: revisar screenshots de fallo antes de aprobar merge"

**Si bootstrap_mode=true:**
- Banner azul: "ℹ️ Modo aprendizaje (X/14 runs success — no se emiten alertas amarillas hasta tener 14 runs)"

---

## Casos especiales

### Run con `status="error"` (infraestructura)
- Semáforo: YELLOW (no RED — la tienda no es culpable)
- Markdown: mensaje específico "Infrastructure error detected — ver detalles"
- JSON: campo `error_details` poblado
- NO bloquea merge automáticamente (decisión del usuario)

### Run con un solo perfil fallido
- Semáforo overall: RED
- Resto de perfiles se muestran normalmente
- Carolina ve cuál perfil falló y puede priorizar el debug

### Bootstrap parcial
- Caso: mobile-co tiene 15 runs success, desktop-ec tiene 8.
- `bootstrap_mode` por perfil reflejará la realidad de cada uno.
- `bootstrap_mode` overall = True (any perfil en bootstrap).
- Decisión PO: prefiero ser conservador en alertas — un nuevo perfil entra a bootstrap, no contamina los demás pero pone el run completo en bootstrap.

---

## Criterio de completitud (Definition of Done)

- [ ] Tests pasan (ejemplos verde/amarillo/rojo/bootstrap + caso error).
- [ ] `assert orders_created==0` activado y testeado.
- [ ] `to_json_dict` produce dict que valida contra `specs/execution_report.json`.
- [ ] PBT round-trip: para cualquier `ExecutionReport` válido, `to_markdown` no lanza.
- [ ] Baseline correctamente segregado por `environment_id` (test integrate con U2).
- [ ] H3.1–H3.3 AC satisfechos.
