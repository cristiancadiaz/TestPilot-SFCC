# Business Rules — U3 Reporter (actualizado 2026-05-24)

## BR-U3-01: Invariante orders_created=0 (BLOQUEANTE)
Al inicio de `generate_report`, validar:
```python
assert all(pr.flow_result.orders_created == 0 for pr in profile_results), \
    f"orders_created invariant violated — ALERT: real orders created"
```
Si falla, lanza `InvariantViolatedError` y dispara alerta crítica (CloudWatch alarm + log ERROR).

**Razón:** principio P1 absoluto. Una orden real creada es un incidente bloqueante.

---

## BR-U3-02: Baseline consultado con environment_id (NUEVO)
`generate_report` debe llamar a `baseline_store.get_last_n_runs(environment_id=env.config.environment_id, ...)` — no omitir el `environment_id`.

**Razón:** BR-U2-05 (baseline por ambiente). Mezclar baselines de ambientes distintos genera falsos positivos/negativos.

---

## BR-U3-03: Status global derivado correctamente
```
status = "error" si ≥1 perfil tiene status="error"
status = "failed" si ≥1 perfil tiene status="failed" (y ninguno "error")
status = "success" si todos los perfiles success
```

---

## BR-U3-04: Semáforo global = peor de los individuales
```
overall = RED si ≥1 perfil RED
overall = YELLOW si ≥1 perfil YELLOW (y ninguno RED)
overall = GREEN si todos GREEN
```

**Razón:** semáforo de deploy-gate — el peor caso manda. No promediamos para no enmascarar regresiones específicas.

---

## BR-U3-05: bootstrap_mode global = OR
```python
overall_bootstrap = any(pr.baseline_comparison.bootstrap_mode for pr in profile_results)
```

**Razón:** si CUALQUIER perfil/flow aún está en bootstrap, el run completo se etiqueta como bootstrap para que el usuario sepa que las alertas no son confiables.

**Implicación:** un perfil nuevo (desktop-ec recién agregado) puede mantener al run en bootstrap aunque los otros dos perfiles ya tengan historial suficiente. Esto es deliberado — refleja la realidad estadística.

---

## BR-U3-06: JSON conforme a specs/execution_report.json
`to_json_dict` debe producir un dict que valide contra el JSON Schema `specs/execution_report.json` con `additionalProperties: false`.

**Verificación:** el test `tests/test_reporter.py` carga el schema y llama `jsonschema.validate(report_dict, schema)` — debe pasar.

**Razón:** contrato estable consumido por agentes CI/CD (UC4) y por el dashboard MD0.

---

## BR-U3-07: Markdown empieza con semáforo destacado
La primera línea del Markdown debe ser un H1 con el emoji del semáforo y el `run_id`. Esto facilita lectura rápida en Slack/CLI.

Ejemplo: `# 🟢 TestPilot Run abc123-de45 — STAGING`

---

## BR-U3-08: Markdown incluye banner de auditoría
Inmediatamente debajo del header del status, una línea con `> 🔒 Auditoría: orders_created = 0`. Si fuera distinto, banner ROJO bloqueante.

---

## BR-U3-09: Persistir TODOS los runs (success, failed, error)
`generate_report` debe llamar `baseline_store.save_run(...)` para cada perfil, independientemente del status. Razón: BR-U2-10 — el historial debe ser completo para el dashboard P5 y para tendencias.

El filtrado por `status="success"` en `get_last_n_runs` ocurre solo al CALCULAR baseline, no al PERSISTIR.

---

## BR-U3-10: Sin información sensible en reporte
El reporte NO debe contener:
- Email del shopper (no es necesario para el reporte)
- Passwords (obvio)
- Paths internos del filesystem
- Stack traces (solo `error` string del paso fallido)

**Verificación:** test que regex el output de `to_json_dict` y `to_markdown` buscando `password|secret|token` y rechaza si encuentra.

---

## BR-U3-11: Markdown legible en monoespaciado
El Markdown debe ser legible en CLI (sin renderizar). Esto implica:
- Tablas con anchos razonables (no líneas de >120 chars).
- Sin imágenes embebidas (solo URLs en texto).
- Emojis Unicode estándar (compatible con cualquier terminal moderno).

---

## BR-U3-12: Modo bootstrap visible en JSON top-level
`ExecutionReport.bootstrap_mode` es campo top-level (no anidado en `baseline_comparison`). Razón: el dashboard y el agente CI/CD deben poder decidir "no alertar" sin tener que mirar dentro de cada perfil.

---

## Trazabilidad

| BR | Historia | Principio |
|---|---|---|
| BR-U3-01 | H3.3 (auditabilidad orders=0) | P1 |
| BR-U3-02, BR-U3-05 | H3.2 (JSON estable) | P4 |
| BR-U3-04, BR-U3-08 | H3.1 (reporte legible) | — |
| BR-U3-06, BR-U3-12 | H3.2 (JSON estable) | P2 (versionable) |
| BR-U3-10 | — | SECURITY-10 |
