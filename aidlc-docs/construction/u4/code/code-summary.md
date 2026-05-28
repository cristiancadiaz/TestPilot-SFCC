# Code Summary — U4 API Endpoints

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/api/main.py` | Reemplazo completo del stub — 3 endpoints reales + auth + middleware |

## Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `tests/test_api.py` | 17 tests con TestClient + mock de run_profile |

## Endpoints implementados

| Método | Path | Respuesta |
|--------|------|-----------|
| POST | /v1/run | 200 ExecutionReport JSON (camelCase) |
| GET | /v1/runs/{run_id} | 200 ExecutionReport / 404 |
| GET | /v1/runs/latest | 200 ExecutionReport + ageSeconds + ttlOk / 404 |

## Decisiones relevantes

- Auth vía `Depends(verify_api_key)`: FastAPI evalúa en cada request antes de ejecutar el handler
- Middleware `_catch_errors` captura `InfrastructureError` → 503 y `Exception` → 500 sin exponer stack traces (SECURITY-15)
- `_run_store` y `_baseline_store` son module-level (MVP in-memory): se comparten entre requests en el mismo proceso
- POST /v1/run retorna 200 (no 202) — la ejecución es sincrónica en MVP
- `to_json_dict` garantiza que la respuesta cumple `specs/execution_report.json` (camelCase, sin `ordersCreated`)
- Fixture del test limpia `_run_store` entre tests para evitar state leakage
