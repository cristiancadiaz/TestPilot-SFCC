# Dependencies — TestPilot SFCC

## Internal Dependencies

```
specs/
  ^
  |  (validates against)
  |
src/agents/translator.py  <----imports----  src/agents/__init__.py
  ^
  |  (re-uses SyntheticUserConfig shape)
  |
src/api/main.py  <-----------imports----  src/api/__init__.py

tests/test_schemas.py  ----reads------>  specs/
tests/test_translator.py  --imports-->  src/agents/translator.py
```

### Pending Internal Dependencies (planned)

```
src/executor/  ----reads------>  specs/ (flow catalog)
src/executor/  ----calls------>  src/baseline/ (writes results)
src/executor/  ----calls------>  src/classifier/ (classifies errors)
src/reporter/  ----reads------>  src/baseline/ (reads p95)
src/reporter/  ----reads------>  specs/execution_report.schema.json (schema)
src/api/       ----calls------>  src/executor/ (triggers run)
src/api/       ----calls------>  src/baseline/ (reads history)
```

## External Dependencies (Current)

| Dependencia | Version | Propósito | Licencia |
|-------------|---------|-----------|---------|
| anthropic | Unknown | Claude API SDK - NL translation | MIT |
| fastapi | Unknown | REST API framework | MIT |
| pydantic | v2.x | Data validation/serialization | MIT |
| uvicorn | Unknown | ASGI server | BSD |
| jsonschema | Unknown | JSON Schema validation (draft-07) | MIT |
| pytest | Unknown | Test framework | MIT |

## External Dependencies (Planned)

| Dependencia | Propósito | Notas |
|-------------|-----------|-------|
| playwright | Browser automation para SFCC | Binarios ~200MB; no cabe en Lambda |
| boto3 | AWS SDK (DynamoDB, S3, Secrets Mgr) | Standard para AWS Python |
| aws-cdk-lib | CDK v2 - Infrastructure as Code | |
| constructs | Base de CDK | |

## Dependency Constraints Importantes

### anthropic SDK — Versión crítica
- **Riesgo**: translator.py usa `claude-3-haiku-20240307` — modelo con fecha. Puede quedar deprecated.
- **Recomendación**: Pin a una versión reciente del SDK y usar `claude-haiku-4-5-20251001` (último disponible per system info).
- **Impacto**: Si el modelo se depreca, _build_prompt() falla silenciosamente.

### Playwright — Constraint de infraestructura
- **Restricción**: Playwright binarios (~200MB) superan límite de AWS Lambda (250MB deployment package).
- **Decisión tomada (no reabrir)**: ECS Fargate con imagen oficial de Playwright.
- **Implicación**: El código de executor/ debe ser compatible con la imagen oficial `mcr.microsoft.com/playwright/python`.

### pydantic v2 — Breaking changes vs v1
- **Estado**: La API usa Pydantic v2 (`model_config`, `field_validator` decorators).
- **Riesgo**: Si translator.py usa v1 compat mode (`BaseModel` puro sin v2 features), podría haber inconsistencias.
- **Verificación**: translator.py usa `SyntheticUserConfig(BaseModel)` — compatible con v2.

### No requirements.txt
- **Riesgo alto**: Sin pinning de versiones, `pip install` en CI puede instalar versiones incompatibles.
- **Acción requerida en MVP**: Crear `requirements.txt` o `pyproject.toml` con versiones exactas antes de construir imagen Docker.
