# Propuesta de Cambios de Contrato — Puerta HITL (cascade #6)

> **Estado: ✅ APROBADO Y APLICADO (2026-06-03).** El usuario aprobó los paquetes A, B y C con las
> recomendaciones: A1-alt `full_journey` como valor del enum · B5-alt documento de auditoría como
> referencia S3 · B6-alt `network_summary` por ProfileResult. Schemas editados (deny de `specs/`
> levantado temporalmente con consentimiento y restaurado de inmediato), validados contra
> Draft 2020-12 y con todos los ejemplos pasando. Se conserva este documento como registro del paquete.
> Branch `rework/storefront-audit-scope` · 2026-06-03 · Origen: realineación de alcance (RF-21..RF-29 aprobados).
> Todo cambio aquí es **BREAKING** (P2): requiere bump de versión y aprobación humana explícita campo por campo.
> Política P2: `v2` se publica manteniendo `v1` operativo 30 días.

---

## Paquete A — `synthetic-user-config.schema.json` (v1 → v2)

| # | Campo | Cambio propuesto | Racional |
|---|---|---|---|
| A1 | `flows[].items.enum` | Agregar: `search_and_filter`, `browse_discounted_products`, `pdp_validation`, `cart_review`, `full_journey` (queda: 7 valores) | RF-21/RF-22 — catálogo modular cerrado. `full_journey` es un **alias de composición**: el backend lo expande a la secuencia declarada en FlowCatalog; el executor nunca lo recibe como flow |
| A2 | `flows[].maxItems` | `2` → `6` (las 6 individuales; si `full_journey` está presente, se expande y deduplica server-side) | Permitir subconjuntos arbitrarios sin permitir redundancia |
| A3 | `mode` (NUEVO, opcional) | `enum: ["gate", "exploratory"]`, `default: "gate"` | RF-28 — runs exploratorios nunca entran al baseline (C11) |
| A4 | `schema_version` | `const: "v1"` → `const: "v2"` | Bump por A1–A3 |
| A5 | `options.capture_intermediate_screenshots` | Sin cambio (`const: false`). Solo se actualiza la *description*: la evidencia por hallazgos (RF-26) es dirigida por evento, NO es "capturar intermedios" | Preserva el invariante de costo con la semántica nueva documentada |

**Decisión que requiere tu elección:**
- **A1-alt:** ¿`full_journey` como valor del enum (recomendado — un solo campo, simple para el translator y el dashboard) o campo separado `journey_scope: "single|subset|full"`? La recomendación es **enum** porque mantiene `flows[]` como única fuente del alcance.

## Paquete B — `execution_report.schema.json` (v1 → v2)

| # | Campo | Cambio propuesto | Racional |
|---|---|---|---|
| B1 | `FlowResult.flow_name.enum` | + los 4 flows modulares (NO `full_journey`: el reporte siempre muestra la composición expandida, un FlowResult por flow) | RF-21; H6.3 AC4 |
| B2 | `StepResult.screenshot_state.enum` | `["fail","final"]` → `["fail","final","finding","critical"]` + campo NUEVO opcional `finding_dimension` (enum de las 6 dimensiones, solo cuando state=`finding`) | RF-26 — evidencia por hallazgos con naming `{paso}-{finding-{dim}|critical}.png` |
| B3 | `StepResult.phase` (NUEVO, opcional) | `enum: ["setup","flow"]`, default `flow` | H6.2 AC3 — los pasos de auto-preparación se reportan separados del módulo bajo prueba |
| B4 | `mode` (NUEVO, requerido top-level) | `enum: ["gate","exploratory"]` | RF-28 — el reporte exploratorio se marca visiblemente |
| B5 | `audit` (NUEVO, opcional top-level) | Objeto: `findings[]` (`{dimension, severity, page_url, step, data, evidence_refs[]}`), `hypotheses[]` (`{text, confidence: 0–1, requires_human_review: bool}`), `synthesis_available: bool`, `document_md_url` (ref S3) | RF-24/RF-25 — hallazgos deterministas + síntesis del agente. El semáforo NO vive aquí (C10) |
| B6 | `network_summary` (NUEVO, opcional por ProfileResult) | `{total_requests, failed_requests, controllers[]: {pattern, count, p95_ms}, web_vitals: {lcp_ms, cls, ttfb_ms}, har_url}` | RF-23 — resumen en reporte, HAR completo en S3 |
| B7 | `$id` / versión | path `/v1/` → `/v2/` | Bump por B1–B6 |

**Decisiones que requieren tu elección:**
- **B5-alt:** ¿documento de auditoría **inline** en el JSON o **referencia S3** + hallazgos estructurados inline (recomendado — el JSON se mantiene parseable y acotado; el MD largo vive en S3)?
- **B6-alt:** ¿`network_summary` por ProfileResult (recomendado — mobile y desktop difieren) o agregado top-level?

## Paquete C — Contrato `POST /v1/translate` (NUEVO)

| Elemento | Propuesta |
|---|---|
| Request | `{instruction: string (2..2000 chars)}` |
| Response 200 | `{status: "ok", proposed_config: SyntheticUserConfig(v2), explanation: string}` — config YA validado contra schema + catálogo; **no ejecuta nada** |
| Response 200 (ambigua) | `{status: "ambiguous", clarification_question: string}` |
| Response 422 | `{error_code: "instruction_rejected", reason}` — fuera de catálogo / prompt injection (se loggea) |
| Archivo | `specs/translate-request-response.schema.json` (nuevo — aditivo, no breaking para consumidores existentes) |

## Secuencia de aplicación (tras tu aprobación)

1. Editar los 2 schemas + crear el de translate (un solo commit, con bump de versión y ejemplos actualizados)
2. Validar ejemplos contra los schemas (skill `validate-synthetic-config` para el config)
3. Registrar en `audit.md` la aprobación y el diff aplicado
4. Recién entonces: planes de construcción U5–U8 (cascade #7)

---

*Ningún campo de `specs/` se modifica hasta la aprobación explícita de los paquetes A, B y C (con tus elecciones en A1-alt, B5-alt, B6-alt).*
