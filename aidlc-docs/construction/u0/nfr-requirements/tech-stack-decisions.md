# Tech Stack Decisions — U0 Setup Base (actualizado 2026-05-24)

## Decisión D-U0-01: Pydantic v2 (no v1, no dataclasses)

**Elegido:** Pydantic 2.9.2

**Razones:**
- v2 es la rama soportada — v1 EOL en 2024.
- Performance ~5–50× v1 (escrito en Rust).
- `model_dump(by_alias=True)` necesario para JSON contract con camelCase (specs).
- `EmailStr` y `HttpUrl` validators built-in.
- Compatibilidad nativa con FastAPI.

**Descartado:**
- **dataclasses:** sin validation runtime.
- **attrs:** menos integración con FastAPI.

---

## Decisión D-U0-02: AWS SDK boto3 desde U0

**Elegido:** `boto3==1.35.49`

**Razones para incluir en U0 (no diferir a U4):**
- `EnvironmentConfig` se persiste en DynamoDB → modelos de U0 deben poder mapearse a DynamoDB items.
- `EnvironmentAccessCredentials` y `ShopperCredentials` se construyen desde Secrets Manager → la responsabilidad de "cómo se cargan" vive cerca de los modelos.
- Tener boto3 disponible desde U0 evita versioning conflicts cuando U4 lo agregue.

**Trade-off aceptado:** boto3 es un import pesado (~40 MB en site-packages). Aceptable para imagen de ~1.5 GB.

---

## Decisión D-U0-03: Python 3.12 (no 3.11, no 3.13)

**Elegido:** Python 3.12

**Razones:**
- 3.12 estable (publicado Oct 2023) — adopción amplia.
- Soporte LTS hasta Oct 2028.
- Performance ~10% mejor que 3.11.
- `TypedDict` mejorado, `Self` type built-in.
- 3.13 (Oct 2024) aún tiene compatibilidad limitada de algunas dependencias C-extension (Playwright OK, pero por seguridad MVP queda en 3.12).

---

## Decisión D-U0-04: Multi-stage Docker (cambio vs versión anterior)

**Antes:** single-stage.
**Ahora:** multi-stage (Node builder + Python runtime).

**Justificación del cambio:** la introducción de MD0 requiere build de assets con Vite + pnpm. Sin multi-stage, la imagen final tendría Node + node_modules (~200 MB extra) sin propósito en runtime.

**Estructura:**
1. Stage 1 (`node:20-alpine`): `pnpm install && pnpm build` → `dist/`
2. Stage 2 (`playwright/python:v1.48.0-jammy`): pip install + `COPY --from=stage1 dist/`

---

## Decisión D-U0-05: pip-audit (no safety, no snyk)

**Elegido:** `pip-audit==2.7.3`

**Razones:**
- Oficial de PyPA (Python Packaging Authority).
- Free, sin auth required (a diferencia de Snyk).
- Usa el database de OSV (Open Source Vulnerabilities) — el más completo.
- Salida JSON parseable.

**Modo en CI:** `pip-audit --strict --vulnerability-service osv` → exit code != 0 bloquea PR.

---

## Decisión D-U0-06: structlog vs python-json-logger

**Elegido:** `python-json-logger==2.0.7`

**Razones:**
- Más simple que structlog (subclass de stdlib `logging.Formatter`).
- Output JSON parseable por CloudWatch.
- Permite redacción de campos sensibles con formatter custom.

**Implementación esperada (en U4 logging-strategy.md, referenciada aquí):**
```python
from pythonjsonlogger import jsonlogger

class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "x-api-key"}
    
    def process_log_record(self, log_record):
        for key in list(log_record.keys()):
            if any(s in key.lower() for s in self.SENSITIVE_KEYS):
                log_record[key] = "***REDACTED***"
        return super().process_log_record(log_record)
```

---

## Stack final pinned

| Componente | Versión |
|---|---|
| Python | 3.12 |
| FastAPI | 0.115.0 |
| Uvicorn | 0.30.6 |
| Pydantic | 2.9.2 |
| Playwright Python | 1.48.0 |
| Anthropic SDK | 0.39.0 |
| boto3 | 1.35.49 |
| jsonschema | 4.23.0 |
| python-json-logger | 2.0.7 |
| pytest | 8.3.3 |
| pytest-asyncio | 0.24.0 |
| hypothesis | 6.115.3 |
| ruff | 0.7.1 |
| mypy | 1.13.0 |
| pip-audit | 2.7.3 |
| Docker base (runtime) | mcr.microsoft.com/playwright/python:v1.48.0-jammy |
| Docker base (build) | node:20-alpine |
