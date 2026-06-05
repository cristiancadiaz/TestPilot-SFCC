# syntax=docker/dockerfile:1.7
# TestPilot SFCC — runtime image (U0 single-stage).
#
# Built on the official Playwright Python base (Chromium + OS deps preinstalled,
# pinned to match `playwright==1.48.0` in pyproject — BR-U0-08, SECURITY-12).
# NOTE: the `-noble` (Ubuntu 24.04) variant ships Python 3.12, required by
# requires-python>=3.12 (D-U0-03). The `-jammy` variant ships Python 3.10 and is
# incompatible — delta to reconcile in tech-stack-decisions.md / TASK-002.
# The MD0 dashboard multi-stage build (Node builder → dist/) is DEFERRED until
# src/dashboard/ exists; see aidlc-docs/.../infrastructure-design.md §1.
#
# Scope note: src/api/main.py arrives in U4. The CMD below is the TARGET
# entrypoint; the U0 gate validates `docker build` + imports, not app startup.
FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Metadata + package sources required by the hatchling editable install:
# pyproject declares readme="README.md", license={file="LICENSE"}, packages=["src"].
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY specs/ specs/

# Runtime dependencies only — all pinned (RNF-08).
RUN pip install --no-cache-dir -e .

# Ensure Chromium + OS deps are present (idempotent on this base). Must run as
# root, before dropping privileges.
RUN playwright install chromium --with-deps

# Non-root user (SECURITY-13 / BR-U0-09). The Playwright base ships `pwuser`
# (UID 1001) for exactly this purpose — reuse it instead of creating a duplicate.
RUN chown -R pwuser:pwuser /app
USER pwuser

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
