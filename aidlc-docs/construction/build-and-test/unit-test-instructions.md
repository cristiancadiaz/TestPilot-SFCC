# Unit Test Instructions — TestPilot SFCC

## Ejecutar todos los tests

```bash
pytest tests/ -v
```

## Ejecutar por módulo

```bash
# U0 — Modelos
pytest tests/test_models.py -v

# U0 — Schemas JSON (contratos existentes)
pytest tests/test_schemas.py -v

# U0 — Translator (existente)
pytest tests/test_translator.py -v

# U1 — Executor profiles (sin browser)
pytest tests/test_executor_profiles.py -v

# U1 — Executor flows (con mocks de Page)
pytest tests/test_executor_flows.py -v

# U1 — Executor runner (con mocks de Playwright)
pytest tests/test_executor_runner.py -v

# U2 — Baseline Manager (tests de ejemplo)
pytest tests/test_baseline_manager.py -v

# U2 — Baseline PBT (hypothesis — puede tardar 30–60s)
pytest tests/test_baseline_pbt.py -v

# U3 — Reporter
pytest tests/test_reporter.py -v

# U4 — API (FastAPI TestClient)
pytest tests/test_api.py -v
```

## Criterios de completitud por unidad

| Unidad | Tests | Criterio |
|--------|-------|---------|
| U0 | test_models, test_schemas, test_translator | 100% pass |
| U1 | test_executor_profiles, test_executor_flows, test_executor_runner | 100% pass, orders_created=0 en todos los flows |
| U2 | test_baseline_manager, test_baseline_pbt | 100% pass, PBT-02/03/07/08/09 pasan |
| U3 | test_reporter | 100% pass, schema validation con jsonschema |
| U4 | test_api | 100% pass, 401 sin key, 404 run inexistente |

## Variables de entorno para tests

Los tests de API requieren `API_KEY`. El fixture `_set_api_key` en `test_api.py` la configura automáticamente via `monkeypatch`.

Los tests de flows y runner mockean Playwright — no requieren browsers instalados.

Los tests de PBT pueden configurar el número de ejemplos:
```bash
# Más ejemplos para mayor cobertura (más lento)
HYPOTHESIS_MAX_EXAMPLES=500 pytest tests/test_baseline_pbt.py -v
```
