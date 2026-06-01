# Code Structure — TestPilot SFCC

## Build System
- **Type**: Python con ruff (formatter + linter) y mypy (type checker)
- **Configuration**: No se encontró pyproject.toml ni requirements.txt en el workspace root. Las dependencias inferidas de los imports son: `anthropic`, `fastapi`, `pydantic`, `jsonschema`, `uvicorn`, `pytest`.
- **Python Version**: 3.12 (declarado en AGENTS.md)

## Key Classes/Modules

```
src/
+-- agents/
|   +-- __init__.py          # Exporta translate, TranslatorError
|   +-- translator.py        # NL -> SyntheticUserConfig via Claude API
|
+-- api/
    +-- __init__.py          # Exporta app
    +-- main.py              # FastAPI app, POST /v1/run, modelos Pydantic

specs/
+-- synthetic_user_config.json   # JSON Schema v Draft-07 (input contract)
+-- execution_report.schema.json        # JSON Schema v Draft-07 (output contract)

tests/
+-- test_schemas.py          # Validacion de schemas JSON
+-- test_translator.py       # Tests unitarios del agente traductor
```

### Modules Pendientes (definidos en AGENTS.md, aun no implementados)
```
src/
+-- executor/
|   +-- flows/
|   |   +-- checkout_full.py          (pendiente)
|   |   +-- checkout_card_declined.py (pendiente)
|   +-- profiles/
|   |   +-- mobile_co.py              (pendiente)
|   |   +-- desktop_co.py             (pendiente)
|   |   +-- desktop_ec.py             (pendiente)
|   +-- selectors.py                  (pendiente)
|
+-- reporter/                         (pendiente)
+-- baseline/                         (pendiente)
+-- classifier/                       (pendiente)

infra/                                (pendiente - AWS CDK)
```

## Existing Files Inventory

- `src/agents/__init__.py` — Re-exporta `translate` y `TranslatorError` desde translator.py
- `src/agents/translator.py` — Agente LLM: NL → SyntheticUserConfig. Constantes: FLOWS, PROFILES, MAX_RETRIES. Clases: SyntheticUserConfig (Pydantic), TranslatorError. Funciones: translate(), _validate_config(), _build_prompt(), _load_schema()
- `src/api/__init__.py` — Re-exporta `app` desde main.py
- `src/api/main.py` — FastAPI app. Modelos Pydantic: SyntheticUserConfig, RunResponse. Endpoint: POST /v1/run → 202 Accepted con {testRunId, status: "queued"}
- `specs/synthetic_user_config.json` — JSON Schema draft-07. Campos: testRunId (UUID), environment_id (enum: sandbox|development|staging), products[] (search_term + validate_variant), flows[] (enum closed), profiles[] (enum closed: mobile_co|desktop_co|desktop_ec), screenshot_on_success/error (bool), timeout (30000-180000). Sin credenciales.
- `specs/execution_report.schema.json` — JSON Schema draft-07. Campos: testRunId, status (success/failed/error), trafficLight (green/yellow/red), startedAt, finishedAt, durationMs, steps[], config{}, baselineComparison{p95BaselineMs, percentDiff, bootstrapMode}
- `tests/test_schemas.py` — Tests pytest para ambos JSON schemas con jsonschema.Draft7Validator. Clases: TestSyntheticUserConfigSchema, TestExecutionReportSchema
- `tests/test_translator.py` — Tests pytest con mocks de anthropic.Anthropic. Clases: TestLoadSchema, TestValidateConfig, TestBuildPrompt, TestTranslate

## Design Patterns

### Validation Chain (P3 del PRD)
- **Location**: `src/agents/translator.py:_validate_config()` + `src/api/main.py` (Pydantic validators)
- **Purpose**: Garantizar que ningún config inválido llegue al executor
- **Implementation**: jsonschema.validate() → Pydantic model → custom field validators (@field_validator)

### Closed Catalog (P3 del PRD)
- **Location**: `FLOWS` y `PROFILES` constantes en translator.py; `enum` en specs/
- **Purpose**: Reducir tasa de error del LLM de ~20% a casi cero; prevenir flujos arbitrarios
- **Implementation**: Enum en JSON Schema + Literal types en Pydantic + constantes en translator

### Retry with Bounded Attempts
- **Location**: `src/agents/translator.py:translate()` — loop MAX_RETRIES=3
- **Purpose**: Tolerar respuestas JSON inválidas del LLM sin loops infinitos
- **Implementation**: Loop for attempt in range(MAX_RETRIES), re-raise último error

### Zero Contamination Invariant (P1 del PRD)
- **Location**: `src/agents/translator.py:_validate_config()` y `src/api/main.py:validate_email()`
- **Purpose**: Garantizar que todos los emails sean @testpilot.internal
- **Implementation**: Regex pattern en JSON Schema + @field_validator en Pydantic + auto-assign en translator

## Critical Dependencies

### anthropic (Python SDK)
- **Version**: No especificada en requirements (inferred from imports)
- **Usage**: `src/agents/translator.py` — mensajes a claude-3-haiku-20240307
- **Purpose**: Traducción NL → config y (futuro) clasificación de errores

### fastapi
- **Version**: No especificada
- **Usage**: `src/api/main.py` — framework REST
- **Purpose**: Endpoint /v1/run con validación automática Pydantic

### pydantic (v2)
- **Version**: v2 (usa `model_config`, `field_validator` — API Pydantic v2)
- **Usage**: `src/api/main.py` y `src/agents/translator.py`
- **Purpose**: Validación de modelos de entrada/salida con tipos estrictos

### jsonschema
- **Version**: No especificada
- **Usage**: `src/agents/translator.py:_validate_config()` y `tests/test_schemas.py`
- **Purpose**: Validación de configs contra specs/synthetic_user_config.json

### pytest
- **Version**: No especificada
- **Usage**: `tests/` — todos los tests
- **Purpose**: Framework de testing unitario
