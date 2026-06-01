---
id: TASK-002
title: Dockerfile + .dockerignore (imagen base Playwright)
milestone: "M1: Packaging & Container Foundation"
priority: 2
estimate: 2
blockedBy: [TASK-001]
blocks: [TASK-006]
parent: null
---

## Summary
Crear el `Dockerfile` multi-stage sobre la imagen base oficial de Playwright y el `.dockerignore`, para empaquetar el servicio de forma reproducible y con superficie mínima (RNF-08, SECURITY-12/13).

## Scope
- **Incluye:** `Dockerfile` y `.dockerignore` en la raíz.
- **Reservado:** no modificar deps (eso es TASK-001); no tocar `infra/`.

## Deliverables
- `Dockerfile`:
  - `FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy` (versión pinned — alinear con la de `playwright` en `pyproject.toml`).
  - `WORKDIR /app`; `COPY pyproject.toml .`; `RUN pip install --no-cache-dir -e .`.
  - `COPY src/ src/`; `COPY specs/ specs/`; `RUN playwright install chromium --with-deps`.
  - Usuario **no-root**; `EXPOSE 8000`; `CMD ["uvicorn","src.api.main:app","--host","0.0.0.0","--port","8000"]`.
- `.dockerignore`: `.env*`, `.git`, `aidlc-docs/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `tests/`, `.claude/`, `.ai/`.

## Acceptance Criteria
- `docker build -t testpilot-sfcc:local .` completa sin errores.
- La imagen corre como usuario no-root.
- No se incluye `.env*` ni secretos en la imagen (SECURITY-13).
- Versión de imagen base pinned (sin `latest`).

## Test Plan
- `docker build -t testpilot-sfcc:local .` → exit 0.
- `docker run --rm testpilot-sfcc:local python -c "import fastapi, playwright"` → exit 0.
- `docker run --rm testpilot-sfcc:local whoami` → no devuelve `root`.

## Context
- `aidlc-docs/construction/plans/u0-code-generation-plan.md` (Steps 6, 7).
- `aidlc-docs/construction/u0/infrastructure-design/infrastructure-design.md`.

## Definition of Ready
Depende de TASK-001 (pyproject). AC verificables por comando. Pin de versión de imagen requerido antes de marcar listo.
