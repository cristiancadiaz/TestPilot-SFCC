# NFR Design — U0 Setup Base (2026-05-28)

Patrones concretos para satisfacer los NFR-U0-* y BR-U0-* de la unidad base.

---

## Patrón 1: Multi-stage Dockerfile (NFR-U0-P2, D-U0-04)

Resuelve el conflicto entre incluir el build del dashboard MD0 (Node + pnpm) y mantener la imagen runtime < 2 GB.

```dockerfile
# ── Stage 1: Dashboard build (Node) ──────────────────────────────────────────
FROM node:20-alpine AS dashboard-builder

WORKDIR /build
COPY src/dashboard/package.json src/dashboard/pnpm-lock.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile

COPY src/dashboard/ ./
RUN pnpm run build
# Output: /build/dist/

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy AS runtime

WORKDIR /app

# Dependencias Python (pinned exacto, BR-U0-06)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[prod]"

# Código fuente
COPY src/ ./src/

# Dashboard compilado — sin Node ni node_modules en imagen final
COPY --from=dashboard-builder /build/dist/ ./src/dashboard/dist/

# Non-root (BR-U0-09, SECURITY-13)
# La imagen Playwright ya tiene 'pwuser' — lo reutilizamos
USER pwuser

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Por qué multi-stage:**
- Node + `node_modules` añaden ~200 MB que no se necesitan en runtime.
- El dashboard compilado (`dist/`) pesa ~2 MB — solo ese artifact cruza de stage.
- La imagen final hereda `pwuser` de la base Playwright sin crear un usuario adicional.

**Trade-off aceptado:** dos stages implican un build más lento en CI (~90 s extra). Aceptable para imagen ~1.4 GB vs ~1.6 GB sin multi-stage.

---

## Patrón 2: Credential models con redacción nativa (BR-U0-03, NFR-U0-S5)

Impide que `logger.info(creds)` o `print(creds)` filtre passwords en logs.

```python
# src/models.py
from pydantic import BaseModel, Field, field_validator

class EnvironmentAccessCredentials(BaseModel):
    username: str
    password: str = Field(repr=False)  # excluido de repr() automático

    def __str__(self) -> str:
        return f"EnvironmentAccessCredentials(username={self.username!r}, password=***)"

class ShopperCredentials(BaseModel):
    email: str
    password: str = Field(repr=False)

    def __str__(self) -> str:
        local, _, domain = self.email.partition("@")
        redacted_email = f"{local[0]}***@{domain}" if local else "***"
        return f"ShopperCredentials(email={redacted_email!r}, password=***)"
```

**Verificación (test):**
```python
def test_credentials_never_expose_password():
    creds = ShopperCredentials(email="qa-sandbox@testpilot.internal", password="s3cr3t")
    assert "s3cr3t" not in str(creds)
    assert "s3cr3t" not in repr(creds)
    assert "***" in str(creds)
```

**Por qué `Field(repr=False)` y no `SecretStr`:**
- Pydantic's `SecretStr` oscurece el valor pero requiere `.get_secret_value()` en todo el código que lo usa.
- Los flows de U1 necesitan `password` como `str` nativo para pasarlo a Playwright (`page.fill`).
- Con `repr=False` + `__str__` custom se logra la misma protección sin fricción downstream.

---

## Patrón 3: RedactingJsonFormatter para logging estructurado (D-U0-06, NFR-U0-S5)

Garantiza que ningún campo con nombre sensible salga en los logs de CloudWatch, incluso si un developer hace `logger.info("resolved creds", extra={"password": creds.password})` por error.

```python
# src/logging_config.py
from pythonjsonlogger import jsonlogger

class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    _SENSITIVE_KEYS = frozenset({
        "password", "secret", "token", "api_key",
        "x-api-key", "authorization", "env_access", "shopper",
    })

    def process_log_record(self, log_record: dict) -> dict:
        for key in list(log_record.keys()):
            if any(s in key.lower() for s in self._SENSITIVE_KEYS):
                log_record[key] = "***REDACTED***"
        return super().process_log_record(log_record)


def configure_logging(level: str = "INFO") -> None:
    import logging, sys
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingJsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    logging.basicConfig(level=level, handlers=[handler], force=True)
```

**Uso en `src/api/main.py`:**
```python
from src.logging_config import configure_logging
configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
```

**Trade-off:** el formatter inspecciona todas las claves del record en cada log call — O(k) donde k = número de campos extra. Indetectable en benchmarks a < 1000 logs/s, que es el techo del MVP.

---

## Patrón 4: pyproject.toml con grupos de dependencias (NFR-U0-R1, BR-U0-06)

Separa dependencias de producción de las de desarrollo para que la imagen Docker no incluya pytest, hypothesis, ruff ni mypy.

```toml
[project]
name = "testpilot-sfcc"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "fastapi==0.115.0",
    "uvicorn==0.30.6",
    "pydantic==2.9.2",
    "playwright==1.48.0",
    "anthropic==0.39.0",
    "boto3==1.35.49",
    "jsonschema==4.23.0",
    "python-json-logger==2.0.7",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-asyncio==0.24.0",
    "hypothesis==6.115.3",
    "ruff==0.7.1",
    "mypy==1.13.0",
    "pip-audit==2.7.3",
    "boto3-stubs[dynamodb,secretsmanager,s3]==1.35.49",
]

[tool.ruff]
line-length = 100
target-version = "py312"
select = ["E", "F", "I", "UP", "B", "S"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**En Dockerfile (stage runtime):**
```dockerfile
RUN pip install --no-cache-dir -e ".[prod]"   # solo deps de [project.dependencies]
```

**En CI y desarrollo local:**
```bash
pip install -e ".[dev]"   # deps + herramientas de calidad
```

**Por qué `==` exacto (BR-U0-06):** `pip install fastapi==0.115.0` en lunes y en miércoles produce exactamente el mismo binario. `>=0.115` podría instalar `0.116` el miércoles si hay release intermedio.

---

## Patrón 5: pip-audit en CI (NFR-U0-S4, D-U0-05)

Bloquea cualquier PR que introduzca una dependencia con vulnerabilidad HIGH o CRITICAL.

```yaml
# .github/workflows/ci.yml (fragmento)
- name: Audit dependencies
  run: |
    pip install pip-audit==2.7.3
    pip-audit \
      --strict \
      --vulnerability-service osv \
      --format json \
      --output pip-audit-report.json
  # exit code != 0 si hay HIGH/CRITICAL → el step falla → el PR no se puede mergear
```

**Verificación local:**
```bash
uv run pip-audit --strict
```

**Trade-off:** OSV database tiene latencia de ~24 h desde que se publica un CVE. No es detección instantánea. Para MVP es suficiente — producción requeriría Snyk o Dependabot con alertas en tiempo real.

---

## Patrón 6: PBT round-trip SyntheticUserConfig (PBT-08, NFR-U0)

Garantiza que cualquier instancia válida de `SyntheticUserConfig` sobrevive serialización → deserialización sin pérdida.

```python
# tests/test_models_pbt.py
from hypothesis import given, settings
from hypothesis import strategies as st
from src.models import SyntheticUserConfig, FlowName, ProfileName, EnvironmentId

@given(
    environment_id=st.sampled_from(["sandbox", "development", "staging"]),
    flows=st.lists(
        st.sampled_from(["checkout-full", "checkout-card-declined"]),
        min_size=1, max_size=2, unique=True,
    ),
    profiles=st.lists(
        st.sampled_from(["mobile-co", "desktop-co", "desktop-ec"]),
        min_size=1, max_size=3, unique=True,
    ),
)
@settings(max_examples=200)
def test_synthetic_user_config_round_trip(environment_id, flows, profiles):
    original = SyntheticUserConfig(
        environment_id=environment_id,
        products=[{"search_term": "test product", "validate_variant": False}],
        flows=flows,
        profiles=profiles,
        screenshot_on_success=False,
        screenshot_on_error=True,  # invariante BR-U0-04
    )
    dumped = original.model_dump(mode="json")
    restored = SyntheticUserConfig.model_validate(dumped)
    assert original == restored
```

**Propiedades verificadas:**
- Round-trip identity: `model_dump → model_validate` produce la misma instancia.
- `screenshot_on_error=True` invariante nunca se rompe en el round-trip.
- Catálogo cerrado: `flows` y `profiles` siempre son subsets del `Literal` definido.

---

## Patrón 7: .dockerignore (BR-U0-10)

Evita que secrets, artefactos de desarrollo e historial git contaminen la imagen.

```
# .dockerignore
.env
.env.*
.git/
.claude/
.hardcore-ai/
.aidlc-rules/
aidlc-docs/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
node_modules/
src/dashboard/node_modules/
dist/           # se usa solo dentro del multi-stage, no en contexto de build
*.egg-info/
```

**Por qué excluir `aidlc-docs/`:** contiene documentación de especificación (NFR designs, business rules) que no tiene ningún propósito en runtime y añade ~10 MB al build context.

---

## Resumen patrones → NFRs / BRs

| Patrón | NFRs / BRs satisfechos |
|---|---|
| 1. Multi-stage Dockerfile | NFR-U0-P2, NFR-U0-R2, D-U0-04, BR-U0-08, BR-U0-09, BR-U0-11 |
| 2. Credential models con redacción | BR-U0-03, NFR-U0-S5, SECURITY-10 |
| 3. RedactingJsonFormatter | D-U0-06, NFR-U0-S5, RNF-03 |
| 4. pyproject.toml con grupos | NFR-U0-R1, BR-U0-06, NFR-U0-S4, SECURITY-08 |
| 5. pip-audit en CI | NFR-U0-S4, D-U0-05, SECURITY-08 |
| 6. PBT round-trip | PBT-08 |
| 7. .dockerignore | BR-U0-10, SECURITY-01, NFR-U0-P2 |
