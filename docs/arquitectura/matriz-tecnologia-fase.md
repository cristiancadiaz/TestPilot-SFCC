# Matriz Tecnología × Fase — TestPilot SFCC

> **Última actualización:** 2026-06-03 (realineación de alcance — ola 2: U5–U8, axe-core, captura HAR, agente de síntesis)
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
| **MD0 — Dashboard** | Decisión pendiente (sprint 0) | UI interna sin CLI + matriz genérica perfiles×flows | **Frontend TBD: React o HTML/JS+Fetch**, Tailwind CSS (opcional), consume API REST |
| **U5 — Flows de recorrido** *(ola 2)* | Planificado | Recorrido de tienda como pruebas propias | **FlowCatalog** (registro declarativo + composición `full_journey`), 4 flows Playwright nuevos, despacho genérico en runner, selectores PLP/PROMOTIONS |
| **U7 — Captura de red** *(ola 2)* | Planificado | Tiempos user-perceived + network | **Listeners de red de Playwright / CDP** (HAR filtrado, sin bodies, con redacción), agregación de **controllers SFRA** (p95 por patrón), **Core Web Vitals** (LCP/CLS/TTFB vía Performance API) |
| **U8 — Ventana NL + modos** *(ola 2)* | Planificado | Entrada NL para no-técnicos | Endpoint `POST /v1/translate` (traducir → preview → confirmar), translator promovido a path principal, campo `mode` gate/exploratory, suite anti prompt-injection (RT1) |
| **U6 — Auditoría** *(ola 2)* | Planificado | Documento de 6 dimensiones | **Colectores deterministas** (precios, locale, salud del cliente, contenido), **axe-core** inyectado (WCAG AA, solo páginas clave), **agente de síntesis** (Anthropic SDK en `src/classifier/` — sintetiza, NUNCA juzga el semáforo, P7), política de evidencia **ADR-003** |

### Notas de scope (no obvias desde el código)

- **U2 nace `InMemory`, no DynamoDB.** El patrón Protocol permite el swap a DynamoDB
  *sin tocar U3/U4*; el cambio efectivo es parte de la fase AWS (Eje A).
- **Clasificador LLM: D7 supersedida (2026-06-03).** El descarte original del clasificador
  fue revertido por la realineación: `src/classifier/` se implementa en la ola 2 (U6) como
  **agente de síntesis de auditoría** — redacta y categoriza sobre hallazgos deterministas,
  pero el semáforo sigue siendo regla determinista (P7/C10). La distinción infra-vs-bug
  sigue resuelta por taxonomía de errores en U1, no por Claude.
- **Ola 2 detrás de specs v2.** Los contratos v2 (flows + `full_journey` + `mode` + auditoría
  + red) fueron aprobados por HITL y aplicados el 2026-06-03 — prerrequisito cumplido.
- **axe-core es dependencia nueva** → su entrada a `pyproject.toml` requiere confirmación
  humana (regla de dependencias del arnés).

---

## Eje C — Tecnología × etapa del pipeline en runtime

Encadenamiento en una ejecución real (realineado 2026-06-03):

```text
Ventana NL (MD0) → POST /v1/translate (U8)   (NL → config propuesto + preview; el usuario CONFIRMA)
POST /v1/run — solo payload estructurado     (la NL nunca llega al executor — C12)
  → jsonschema gate (specs/ v2)              (rechazo inmediato si inválido; full_journey se expande)
  → Playwright async (U1+U5)                 (3 perfiles × flows elegidos del catálogo cerrado)
      + captura de red (U7)                  (HAR redactado + controllers SFRA + CWV)
      + datos de auditoría (U6)              (precios, consola, axe-core en páginas clave)
  → BaselineManager p95 (U2)                 (solo runs gate; semáforo vs ventana de 10 runs)
  → Agente de síntesis (U6, src/classifier)  (hallazgos → documento de auditoría; NO toca el semáforo)
  → Reporter Pydantic→JSON+MD (U3)           (semáforo determinista + audit + network_summary)
```

| Etapa runtime | Módulo | Tecnología |
|---|---|---|
| Traducción NL→config (pre-run) | `src/agents/` + `src/api/` | Anthropic SDK (Claude), validación P3 + preview |
| Entrada HTTP | `src/api/` | FastAPI async, auth `X-API-Key` |
| Gate de contrato | `specs/` (v2) | jsonschema (Draft 2020-12) |
| Ejecución de flows | `src/executor/` | Playwright async, `asyncio.gather`, FlowCatalog |
| Captura de red | `src/executor/` | Listeners Playwright/CDP, HAR filtrado, Performance API |
| Colectores de auditoría | `src/executor/` + `src/classifier/` | Python determinista + axe-core |
| Decisión de semáforo | `src/baseline/` | Python puro, p95 sobre ventana móvil (solo gate) |
| Síntesis de auditoría | `src/classifier/` | Anthropic SDK (sanitizado, presupuesto de tokens, P7) |
| Reporte | `src/reporter/` | Pydantic → JSON + Markdown + documento de auditoría |

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
