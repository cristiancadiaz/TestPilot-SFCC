# Code Summary — U3 Reporter

## Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `src/reporter/__init__.py` | Exports del módulo |
| `src/reporter/report_generator.py` | `generate_report`, `to_json_dict`, `to_markdown` |
| `tests/test_reporter.py` | 14 tests: bootstrap, degradación, schema validation, markdown |

## Decisiones relevantes

- `to_json_dict` serializa a camelCase para cumplir `specs/execution_report.schema.json` (additionalProperties: false)
- `orders_created` NO aparece en el dict JSON — el schema no lo define
- `generate_report` calcula `traffic_light` como el peor (más crítico) entre todos los perfiles del run
- `percentDiff` se calcula en `to_json_dict` como `(current - p95) / p95 * 100`
- `to_markdown` usa emojis 🟢🟡🔴 para visualización rápida en CI/CD
- Assertion `orders_created == 0` es la primera línea de `generate_report` — falla loud antes de crear el report
