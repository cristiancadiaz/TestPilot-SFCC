# Component Inventory — TestPilot SFCC

## Application Packages (Implemented)

| Módulo | Archivos | Estado | Propósito |
|--------|----------|--------|-----------|
| `src/agents/` | translator.py, __init__.py | Implementado | NL → SyntheticUserConfig vía Claude API |
| `src/api/` | main.py, __init__.py | Implementado (parcial) | Endpoint REST POST /v1/run |
| `specs/` | synthetic_user_config.json, execution_report.schema.json | Implementado | Contratos JSON Schema de la API |
| `tests/` | test_schemas.py, test_translator.py | Implementado | Tests unitarios de schemas y traductor |

## Application Packages (Pending)

| Módulo | Archivos Esperados | Estado | Propósito |
|--------|-------------------|--------|-----------|
| `src/executor/` | flows/checkout_full.py, flows/checkout_card_declined.py, profiles/mobile_co.py, profiles/desktop_co.py, profiles/mobile_mx.py, selectors.py | Pendiente | Motor Playwright — ejecución de flows |
| `src/baseline/` | baseline_manager.py | Pendiente | DynamoDB: historial, p95, bootstrap flag |
| `src/reporter/` | report_generator.py | Pendiente | JSON + Markdown + semáforo + Slack |
| `src/classifier/` | error_classifier.py | Pendiente | Clasificación errores vía Claude API |

## Infrastructure Packages (Pending)

| Módulo | Tecnología | Estado | Propósito |
|--------|-----------|--------|-----------|
| `infra/` | AWS CDK Python | Pendiente | Step Functions, ECS, DynamoDB, S3, API GW, Secrets Mgr |

## Shared Packages

| Módulo | Estado | Propósito |
|--------|--------|-----------|
| `specs/` | Implementado | Source of truth de contratos — compartido entre api/, agents/, executor/ |

## Test Packages

| Paquete | Tipo | Estado | Cobertura Actual |
|---------|------|--------|-----------------|
| `tests/test_schemas.py` | Unitario | Implementado | Ambos JSON schemas (Draft7 validation) |
| `tests/test_translator.py` | Unitario (con mocks) | Implementado | translate(), _validate_config(), _build_prompt(), _load_schema() |
| `tests/integration/` | Integración | Pendiente | POST /v1/run end-to-end, executor flows |

## Total Count

| Categoría | Implementados | Pendientes | Total |
|-----------|--------------|------------|-------|
| **Application** | 2 (agents, api) | 4 (executor, baseline, reporter, classifier) | 6 |
| **Infrastructure** | 0 | 1 (infra/) | 1 |
| **Shared/Contracts** | 1 (specs/) | 0 | 1 |
| **Test** | 1 (tests/) | 1 (integration) | 2 |
| **TOTAL** | 4 | 6 | 10 |

## Implementation Progress (PRD MoSCoW)

| Feature PRD | Módulo | Estado |
|-------------|--------|--------|
| M1 POST /v1/run | src/api/ | Implementado (sin ejecución real) |
| M2 GET /v1/runs/{run_id} + /latest | src/api/ | Pendiente |
| M3 3 perfiles | src/executor/profiles/ | Pendiente |
| M4 2 flows Playwright | src/executor/flows/ | Pendiente |
| M5 LLM NL→config + validación | src/agents/ | Implementado |
| M6 Payment prueba + @testpilot.internal | src/executor/ | Parcial (email validado; payment en executor) |
| M7 Reporte JSON + Markdown | src/reporter/ | Pendiente |
| M8 Semáforo 3 estados | src/reporter/ | Pendiente |
| M9 Screenshots fallo + final | src/executor/ | Pendiente |
| M10 DynamoDB + S3 | src/baseline/ | Pendiente |
| M11 Baseline p95 últimas 10 | src/baseline/ | Pendiente |
| M12 Bootstrap 14 runs | src/baseline/ | Pendiente |
| M13 Secrets Manager | infra/ | Pendiente |
| M14 Logging CloudWatch | src/ (transversal) | Pendiente |
| M15 Webhook Slack | src/reporter/ | Pendiente |
| M16 Schema versionado /v1/ | src/api/ | Parcial (prefix existe) |
| M17 Distinción infra vs tienda error | src/classifier/ | Pendiente |
| M18 Pre-flight anti-bot sprint 0 | Manual/Sprint 0 | No aplica en código |
