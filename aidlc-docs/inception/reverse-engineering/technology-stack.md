# Technology Stack — TestPilot SFCC

## Programming Languages

| Lenguaje | Versión | Uso |
|----------|---------|-----|
| Python | 3.12 | Lenguaje principal (src/, tests/, infra/) |

## Frameworks (Implemented)

| Framework | Versión | Propósito |
|-----------|---------|-----------|
| FastAPI | No especificada (inferred) | API REST — endpoint /v1/run |
| Pydantic v2 | v2 (usa model_config, field_validator) | Validación de modelos entrada/salida |
| uvicorn | No especificada | ASGI server para FastAPI |
| anthropic Python SDK | No especificada | Llamadas a Claude API (haiku-20240307) |
| jsonschema | No especificada | Validación de configs contra JSON Schema |
| pytest | No especificada | Tests unitarios |

## Frameworks (Planned)

| Framework | Versión | Propósito |
|-----------|---------|-----------|
| Playwright Python | Latest | Browser automation para flujos SFCC |
| boto3 | Latest | Cliente AWS (DynamoDB, S3, Secrets Manager) |
| AWS CDK Python | v2 | Infraestructura como código |

## Code Quality Tools

| Herramienta | Propósito | Configuración |
|------------|-----------|---------------|
| ruff | Formatter + Linter (E, F, I, UP rules) | Declarado en AGENTS.md (sin pyproject.toml) |
| mypy | Type checking con --strict | Declarado en AGENTS.md |

## LLM Models

| Modelo | Proveedor | Uso actual |
|--------|-----------|------------|
| claude-3-haiku-20240307 | Anthropic | Traducción NL → SyntheticUserConfig |
| claude-* (TBD) | Anthropic | Clasificación de errores (pendiente) |

> **Nota**: AGENTS.md y CLAUDE.md mencionan claude-3-haiku para traducción. El PRD especifica Claude API sin modelo específico para clasificación. El modelo haiku actual en translator.py es claude-3-haiku-20240307 — versión antigua; hay versiones más recientes disponibles.

## Infrastructure (Planned — AWS)

| Servicio | Propósito |
|----------|-----------|
| AWS Step Functions | Orquestación de ejecución paralela (3 perfiles x 2 flows) |
| AWS ECS Fargate | Ejecución de containers Playwright (imagen oficial) |
| Amazon DynamoDB | Historial de runs, métricas por paso, baseline p95 |
| Amazon S3 | Screenshots (fail + paso final únicamente) |
| AWS API Gateway | Exposición de endpoints REST versionados |
| AWS Lambda | Handlers para endpoints GET (lightweight) |
| AWS Secrets Manager | Credenciales SFCC staging, Claude API key |
| Amazon CloudWatch | Logging centralizado de todas las ejecuciones |
| Amazon EventBridge | Scheduler para bootstrapping (2 runs/día) |
| Amazon SNS/Slack | Notificaciones de resultado vía webhook |

## Testing Tools

| Herramienta | Tipo | Uso |
|------------|------|-----|
| pytest | Unit testing | src/agents/, src/api/ |
| unittest.mock | Mocking | Llamadas externas (Claude API, DynamoDB) |
| jsonschema.Draft7Validator | Schema testing | Validación de specs/ |

## Build & Packaging

| Aspecto | Estado | Recomendación |
|---------|--------|---------------|
| requirements.txt | No encontrado | Crear con versiones pinned |
| pyproject.toml | No encontrado | Crear para configurar ruff + mypy |
| Dockerfile | No encontrado | Crear basado en imagen oficial Playwright |
| docker-compose.yml | No encontrado | Útil para desarrollo local |
