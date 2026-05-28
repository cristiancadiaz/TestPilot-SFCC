# Deployment Architecture — U0 Setup Base

## Entorno objetivo para U0

U0 establece la base para ejecución **local** (desarrollo) y para posterior despliegue en **ECS Fargate** (no en scope de U0).

## Ejecución local (en scope de U0)

```
Developer Machine
├── Python 3.12 (via pyenv o similar)
├── pyproject.toml → pip install -e .
└── uvicorn src.api.main:app --reload --port 8000
    └── POST /v1/run → responde "queued" (stub actual)
```

Variables de entorno para desarrollo local:
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # En shell, NO en .env trackeado
export API_KEY=dev-local-key
export STOREFRONT_URL=https://staging.example.com
```

## Ejecución via Docker (local, en scope de U0)

```bash
docker build -t testpilot-sfcc:local .
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e API_KEY=$API_KEY \
  -p 8000:8000 \
  testpilot-sfcc:local
```

## ECS Fargate (fuera de scope de U0 — referencia)

La arquitectura objetivo (semana 4–12) es:
```
API Gateway → ECS Fargate (FastAPI + Playwright)
                    ├── DynamoDB (RunRecords)
                    ├── S3 (screenshots)
                    └── Secrets Manager (API keys)
```

En U0 solo se sienta la base del Dockerfile que luego se usa como task definition en ECS.

## .dockerignore

Se crea junto al Dockerfile para excluir:
```
.env
.git
aidlc-docs/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
```

Los `tests/` no se incluyen en la imagen de producción. Se ejecutan en CI antes del build de imagen.
