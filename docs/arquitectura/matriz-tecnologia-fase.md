# Matriz Tecnología × Fase — TestPilot SFCC

> **Última actualización:** 2026-06-02
> **Fuentes de verdad:** `aidlc-docs/inception/application-design/unit-of-work.md`,
> `aidlc-docs/inception/reverse-engineering/technology-stack.md`, `CLAUDE.md`, `README.md`.
> Este documento es **derivado**: si una de esas fuentes cambia, actualízalo aquí.

Mapa de qué tecnología entra en juego en cada fase del proyecto. Coexisten **tres ejes
de "fase"** y conviene no mezclarlos:

- **Eje B — Unidades de trabajo (U0→U4 + MD0):** el roadmap de implementación. Es la
  lectura principal de este documento.
- **Eje C — Pipeline en runtime:** cómo se encadenan los módulos en una ejecución real.
- **Eje A — Infraestructura AWS:** fase de despliegue, **diferida** al deploy-gate (~semana 12).

---

## Stack transversal (todas las fases)

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12+ |
| Validación de datos | Pydantic | 2.9.2 |
| Empaquetado | `pyproject.toml` (PEP 621) + `uv` | — |
| Calidad | ruff (lint+format), mypy `--strict` | — |
| Tests | pytest, `unittest.mock`, hypothesis (PBT), jsonschema | — |
| LLM | Anthropic Python SDK (Claude) | — |
| Contenedor | Docker base `mcr.microsoft.com/playwright/python:v1.48.0-jammy` | — |

---

## Eje B — Tecnología × Unidad de trabajo

Orden de construcción por dependencia: **U0 es prerrequisito de todas las demás**
(ver `aidlc-docs/construction/plans/build-sequence.md`).

| Fase | Estado | Foco | Tecnologías que **entran** en esta fase |
|---|---|---|---|
| **U0 — Setup Base** | En curso | Deuda técnica + reproducibilidad de build | `pyproject.toml` (deps pinned), ruff/mypy, **Dockerfile** (imagen Playwright), `src/models.py` (Pydantic unificado) |
| **U1 — Executor** | Pendiente | Corre los flows reales en SFCC | **Playwright 1.48.0** (`async_playwright`), `asyncio.gather` (cap `MAX_CONCURRENT_PROFILES=3`), `wait_for_selector`/`wait_for_load_state` (prohibido `time.sleep`), screenshots a `SCREENSHOT_DIR`/S3 |
| **U2 — Baseline Manager** | Pendiente | Decide qué es "lento" (semáforo p95) | Python **puro síncrono**, patrón **Protocol + Strategy** (`InMemoryBaselineStore`, swappable a DynamoDB), funciones puras `calculate_p95`/`compute_traffic_light`, **hypothesis** (PBT) |
| **U3 — Reporter** | Pendiente | JSON + Markdown + semáforo | Pydantic `model_dump(by_alias=True)` (camelCase), **jsonschema** validando contra `specs/execution_report.schema.json`, PBT round-trip |
| **U4 — API Endpoints** | Pendiente | Superficie pública + integración | **FastAPI 0.115.0** (handlers async), auth `X-API-Key`, `fastapi.testclient.TestClient`, logging stdlib + JSONFormatter con redacción |
| **MD0 — Dashboard** | Decisión pendiente (sprint 0) | UI interna sin CLI | **Frontend TBD: React o HTML/JS+Fetch**, Tailwind CSS (opcional), consume API REST |

### Notas de scope (no obvias desde el código)

- **U2 nace `InMemory`, no DynamoDB.** El patrón Protocol permite el swap a DynamoDB
  *sin tocar U3/U4*; el cambio efectivo es parte de la fase AWS (Eje A).
- **Clasificador LLM descartado del MVP** (decisión D7). El `src/classifier/` que menciona
  `CLAUDE.md` no se implementa en MVP: la distinción infra-vs-bug se resuelve por
  **taxonomía de errores** en U1, no por Claude.

---

## Eje C — Tecnología × etapa del pipeline en runtime

Encadenamiento en una ejecución real de `POST /v1/run`:

```text
FastAPI (U4)
  → Anthropic SDK / src/agents      (NL → SyntheticUserConfig)
  → jsonschema gate (specs/)        (rechazo inmediato si inválido)
  → Playwright async (U1)           (3 perfiles × 2 flows en paralelo)
  → BaselineManager p95 (U2)        (semáforo vs ventana de 10 runs)
  → Reporter Pydantic→JSON+MD (U3)  (semáforo verde / amarillo / rojo)
```

| Etapa runtime | Módulo | Tecnología |
|---|---|---|
| Entrada HTTP | `src/api/` | FastAPI async, auth `X-API-Key` |
| Traducción NL→config | `src/agents/` | Anthropic SDK (Claude) |
| Gate de contrato | `specs/` | jsonschema (Draft7Validator) |
| Ejecución de flows | `src/executor/` | Playwright async, `asyncio.gather` |
| Decisión de semáforo | `src/baseline/` | Python puro, p95 sobre ventana móvil |
| Reporte | `src/reporter/` | Pydantic → JSON + Markdown |

---

## Eje A — Tecnología AWS (fase de despliegue, DIFERIDA)

El MVP local corre **sin AWS** (in-memory, screenshots a disco, uvicorn local). La infra
cloud es la fase **deploy-gate (~semana 12)**, vía **AWS CDK (Python) en `infra/`**.

| Servicio AWS | Para qué | Reemplaza a (MVP local) |
|---|---|---|
| Step Functions | Orquesta 3×2 ejecuciones paralelas | `asyncio.gather` local |
| ECS Fargate | Corre containers Playwright | Docker local |
| DynamoDB | Historial de runs + baseline p95 | `InMemoryBaselineStore` |
| S3 | Screenshots (fail + paso final) | `SCREENSHOT_DIR` local |
| Secrets Manager | Credenciales SFCC + Claude API key | env vars locales |
| API Gateway + Lambda | Endpoints REST / GET | uvicorn local |
| CloudWatch | Logging centralizado | logging stdlib |
| EventBridge | Scheduler de bootstrap (2 runs/día) | — |
| SNS / Slack webhook | Notificaciones de resultado | — |

---

## Decisiones de tecnología aún abiertas

1. **Frontend del Dashboard MD0** — React vs HTML/JS+Fetch (pendiente sprint 0).
2. **Versión del modelo Claude** — `translator.py` aún apunta a `claude-3-haiku-20240307`
   (obsoleto); la actualización de `CLAUDE_MODEL` (TASK-005) se difirió a U4.
3. **Hosting del dashboard** — misma instancia FastAPI (estáticos) vs servidor separado.
4. **Momento del swap a DynamoDB** — el Protocol queda listo en U2; el cambio efectivo es
   parte de la fase AWS.

---

## Referencias cruzadas

| Tema | Documento |
|---|---|
| Unidades de trabajo (detalle por U) | `aidlc-docs/inception/application-design/unit-of-work.md` |
| Secuencia de build y gates | `aidlc-docs/construction/plans/build-sequence.md` |
| Stack heredado (reverse engineering) | `aidlc-docs/inception/reverse-engineering/technology-stack.md` |
| Catálogo de env vars | `aidlc-docs/inception/application-design/env-vars-catalog.md` |
| Invariantes de producto y boundaries | `CLAUDE.md`, `AGENTS.md` |
| Pitch, arquitectura y riesgos | `README.md` |
