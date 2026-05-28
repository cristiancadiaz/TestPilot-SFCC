# NFR Requirements — U0 Setup Base (actualizado 2026-05-24)

## Reproducibility (RNF-10)

### NFR-U0-R1: Build determinista
`pip install -e ".[dev]"` produce el mismo árbol de dependencias en cada ejecución dado el mismo `pyproject.toml`. Garantizado por versiones pinned exactas (BR-U0-06).

### NFR-U0-R2: Dashboard build determinista
`pnpm install --frozen-lockfile && pnpm run build` produce el mismo `dist/` dado el mismo `pnpm-lock.yaml`. Lockfile commited al repo.

### NFR-U0-R3: Imagen Docker tagged
La imagen se construye con `--tag testpilot-sfcc:{git-sha}`. El SHA del commit es la etiqueta canónica.

---

## Security (Security Baseline)

### NFR-U0-S1: SECURITY-01 — Sin secrets en código
Implementado por BR-U0-12. Verificación: `gitleaks` o `truffleHog` en CI.

### NFR-U0-S2: SECURITY-02 — Env vars para secrets
Los modelos `EnvironmentAccessCredentials` y `ShopperCredentials` se construyen desde Secrets Manager (U4 responsabilidad), nunca desde literales.

### NFR-U0-S3: SECURITY-03 — Input validation
Modelos Pydantic son la primera línea de defensa. Validación estricta de:
- `EnvironmentConfig.store_url` → HttpUrl scheme=https
- `EnvironmentConfig.environment_id` → Literal
- `EnvironmentConfig.*_secret_path` → regex pattern
- `SyntheticUserConfig.products` → min/max length
- `SyntheticUserConfig.profiles` → Literal

### NFR-U0-S4: SECURITY-08 — Dependencias auditadas
`pip-audit` corre en CI. Vulnerabilidades HIGH o CRITICAL bloquean el build.

### NFR-U0-S5: SECURITY-10 — Sin secrets en logs
BR-U0-03: `password` con `repr=False` y `__str__` redactado.

### NFR-U0-S6: SECURITY-12 — Image hardening
Tag semántico fijo, base oficial verificada (mcr.microsoft.com), .dockerignore aplicado.

### NFR-U0-S7: SECURITY-13 — Non-root container
`USER appuser` (o `pwuser` heredado de imagen Playwright).

---

## Code Quality

### NFR-U0-Q1: Lint sin warnings
`ruff check src/` exit code 0. Reglas activadas: E (pycodestyle errors), F (pyflakes), I (isort), UP (pyupgrade), B (bugbear), S (bandit-style security).

### NFR-U0-Q2: Type checking estricto
`mypy --strict src/` exit code 0. Todas las funciones tipadas, sin `Any` implícito, sin `# type: ignore` salvo justificación en comentario.

### NFR-U0-Q3: Tests existentes pasan
`pytest tests/` exit code 0. Incluyendo `test_schemas.py`, `test_translator.py` (actualizados al nuevo modelo) y nuevo `test_models.py`.

### NFR-U0-Q4: Cobertura mínima
Cobertura de `src/models.py` ≥95% (es código declarativo — fácil de cubrir). Resto de código: sin objetivo numérico en U0 (los otros tests son responsabilidad de las otras unidades).

---

## Performance

### NFR-U0-P1: Cold start de imagen
`docker run testpilot-sfcc:{sha}` levanta uvicorn y responde `/health` en **< 5 s** (tiempo desde `docker run` hasta primera 200 OK).

### NFR-U0-P2: Tamaño de imagen
Imagen final **< 2 GB** comprimida (~1.5 GB esperado: base Playwright + Python + node_modules ya purgados por multi-stage).

---

## Aplicabilidad Security Baseline

| Regla | Aplica a U0 | Implementación |
|---|---|---|
| SECURITY-01 No secrets in code | ✅ | NFR-U0-S1, BR-U0-12 |
| SECURITY-02 Env vars para secrets | ✅ | NFR-U0-S2 |
| SECURITY-03 Input validation | ✅ | NFR-U0-S3 (Pydantic) |
| SECURITY-04 SQL injection | N/A | No hay SQL en U0 |
| SECURITY-05 Auth en requests | N/A | U4 implementa API auth |
| SECURITY-06 Authorization | N/A | Sin RBAC en MVP |
| SECURITY-07 TLS/Crypto | Parcial | BR-U0-05 HTTPS en URLs |
| SECURITY-08 Dependencias auditadas | ✅ | NFR-U0-S4 (pip-audit + pnpm audit) |
| SECURITY-09 Sin stack traces | N/A | U4 maneja errores HTTP |
| SECURITY-10 No log secrets | ✅ | BR-U0-03, NFR-U0-S5 |
| SECURITY-11 Rate limiting | N/A | U4 |
| SECURITY-12 Image hardening | ✅ | BR-U0-08, NFR-U0-S6 |
| SECURITY-13 Non-root container | ✅ | BR-U0-09, NFR-U0-S7 |
| SECURITY-14 Network policies | N/A | Infraestructura ECS |
| SECURITY-15 Error handling | N/A | U4 |

**Resumen U0:** 8/15 aplican y se cumplen. 7/15 son N/A — corresponden a unidades posteriores.

---

## Aplicabilidad PBT a U0

PBT aplica marginalmente a U0:
- **PBT-08 (round-trip serialization):** ✅ `SyntheticUserConfig.model_dump() → model_validate()` debe ser identidad. Test en `tests/test_models_pbt.py`.

Resto de reglas PBT (PBT-02, PBT-03, PBT-07, PBT-09) aplican a U2 (cálculo p95 y semáforo).
