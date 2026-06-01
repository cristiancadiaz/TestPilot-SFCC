# Mission 2 — Baseline Manager (DynamoDB + Bootstrap Guard)

**Branch:** `feat/baseline-dynamodb`
**Estimated duration:** 60–90 min agentic execution
**Parallelism:** independiente de Mission 1 (toca módulos distintos)
**Owner agent:** Antigravity session #2

---

## Objetivo de la misión

Implementar `src/baseline/` — la capa de persistencia que escribe ejecuciones a DynamoDB, calcula p95 sobre las últimas 10 ejecuciones, y **silencia alertas amarillas durante el período de bootstrap** (primeras 14 ejecuciones exitosas). Es la pieza que materializa los invariantes de bootstrap silence y p95 de `PRODUCT.md` / `AGENTS.md`.

## Contexto que el agente debe cargar antes de empezar

1. `AGENTS.md` — convenciones del proyecto.
2. `PRODUCT.md` — invariantes (especialmente bootstrap silence y p95).
3. `README.md` — secciones "Decisiones de diseño no obvias" y "Cómo funciona".
4. `docs/definition-of-ready.md` — checklist de readiness antes de implementar.

## Criterios de aceptación

- [ ] `src/baseline/manager.py` con clase `BaselineManager`:
  - `record_execution(run_id, profile, flow, duration_ms, status) -> None` → escribe a DynamoDB.
  - `compute_baseline(profile, flow) -> Baseline | None` → devuelve `None` si hay <14 runs exitosos; devuelve `Baseline(p95_ms, count)` en otro caso.
  - `evaluate(profile, flow, duration_ms) -> Verdict` → devuelve `green` / `yellow` / `red` / `bootstrap`.
- [ ] `src/baseline/models.py` con dataclasses/Pydantic models de `ExecutionRecord`, `Baseline`, `Verdict`.
- [ ] **Constante de bootstrap explícita:** `BOOTSTRAP_RUN_COUNT = 14` en `src/baseline/constants.py`. No mágica numerada inline.
- [ ] Lógica de `evaluate`:
  - Si `count < 14` → `bootstrap` (nunca yellow, nunca green con confianza).
  - Si `count >= 14` y `duration_ms <= p95 * 1.0` → `green`.
  - Si `duration_ms > p95 * 1.0` y `duration_ms <= p95 * 1.3` → `yellow`.
  - Si `duration_ms > p95 * 1.3` o `status == "failed"` → `red`.
- [ ] DynamoDB partition key: `profile#flow`, sort key: `timestamp`. TTL de 90 días sobre cada registro.
- [ ] Tests en `tests/test_baseline_manager.py` con `moto` (mock de DynamoDB):
  - `evaluate` devuelve `bootstrap` con 0, 1, 13 runs.
  - `evaluate` devuelve `green` con 14+ runs y duration ≤ p95.
  - `evaluate` devuelve `yellow` cuando duration está entre p95 y p95*1.3.
  - `evaluate` devuelve `red` cuando duration > p95*1.3.
  - `evaluate` devuelve `red` siempre si `status="failed"`, incluso en bootstrap.
  - p95 se calcula sobre las últimas 10 ejecuciones exitosas (no las 10 últimas crudas).
- [ ] `uv run pytest tests/test_baseline_manager.py -v` pasa al 100%.
- [ ] `ruff check src/baseline/ tests/` sin warnings.
- [ ] `mypy --strict src/baseline/` sin errores.

## Archivos a crear/modificar

```
src/baseline/
├── __init__.py         (nuevo — exporta BaselineManager, Verdict)
├── manager.py          (nuevo)
├── models.py           (nuevo)
└── constants.py        (nuevo — BOOTSTRAP_RUN_COUNT, P95_WINDOW)

tests/
├── conftest.py         (nuevo o modificar — fixture de DynamoDB mockeado con moto)
└── test_baseline_manager.py  (nuevo)

pyproject.toml          (modificar — agregar boto3, moto[dynamodb], numpy o statistics-only)
```

## Constraints que NO se pueden violar

- **No emite yellow durante bootstrap.** Si `count < 14`, el verdict es `bootstrap` — distinto a `green` o `yellow`. Un fix erróneo aquí rompe el invariante #4.
- **p95 se calcula con `statistics.quantiles(method="inclusive")` de stdlib** — no instalar numpy si es evitable (peso en imagen Docker).
- **No es un wrapper de boto3 transparente.** Encapsula los accesos a DynamoDB; nadie más en el proyecto puede llamar `dynamodb.put_item` (invariante de módulo).
- **No toca `src/api/`, `src/executor/`, `src/agents/`.** Esos son scope de otras misiones.
- **No agrega CDK / infra real.** La tabla DynamoDB se crea en `infra/` (otra mission). Aquí solo trabajamos contra el cliente boto3 con un nombre de tabla leído de env var `BASELINE_TABLE_NAME`.

## Cómo verificar al final

```bash
uv run pytest tests/test_baseline_manager.py -v --tb=short
uv run ruff check src/baseline/ tests/
uv run mypy --strict src/baseline/

# Test de smoke con moto:
uv run python -c "
import os
os.environ['BASELINE_TABLE_NAME'] = 'test-table'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
from moto import mock_aws
import boto3
with mock_aws():
    boto3.client('dynamodb').create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'pk', 'KeyType': 'HASH'},
            {'AttributeName': 'sk', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'pk', 'AttributeType': 'S'},
            {'AttributeName': 'sk', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    from src.baseline.manager import BaselineManager
    m = BaselineManager()
    for i in range(13):
        m.record_execution(f'run-{i}', 'mobile_co', 'checkout_full', 2000, 'success')
    print('verdict @ 13:', m.evaluate('mobile_co', 'checkout_full', 2100))
    m.record_execution('run-14', 'mobile_co', 'checkout_full', 2000, 'success')
    print('verdict @ 14:', m.evaluate('mobile_co', 'checkout_full', 2100))
"
# esperado: bootstrap → green
```

## Entregable para el reviewer humano

- Diff completo en la rama `feat/baseline-dynamodb`.
- Output de los 4 comandos de verificación copiados al PR description.
- Una sección "Decisiones tomadas" en el PR description, listando al menos:
  - Por qué `BOOTSTRAP_RUN_COUNT = 14` (cita `PRODUCT.md` / `AGENTS.md`).
  - Por qué thresholds 1.0× y 1.3× p95 (proponer + justificar).
  - Por qué TTL = 90 días.

---

## ⚠️ Nota para el agente de Antigravity

Esta misión corre **en paralelo** con Mission 1 (FastAPI scaffolding). Ambas tocan `pyproject.toml` — coordinar el merge según indicado en Mission 1. La table de DynamoDB se asume ya creada (responsabilidad de `infra/`); este código solo opera el cliente.
