# U6 Auditoría: Colectores + Agente de Síntesis — Code Generation Plan

> ★ Realineación 2026-06-03 — ola 2. Prerrequisitos: U5 + U7 completos (consume sus datos), U3 (integración en reporter), `specs/execution_report.schema.json` v2 (HECHO).

## Unit Context
- **Tipo**: Brownfield — extiende `src/executor/` (recolección), `src/classifier/` (agente) y `src/reporter/` (integración)
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Stories cubiertas**: H7.1, H7.2, H7.3, H7.4, H7.5 — RF-24, RF-25, RF-26, RNF-14
- **Restricciones**: P7/C10 (el agente NUNCA decide el semáforo) · colectores 100% deterministas · evidencia por hallazgos (ADR-003) · input del LLM sanitizado · degradación con gracia · Claude API solo vía `src/classifier/` (boundary)

## Dependencies
Requiere U5 (datos de precios/URLs por flow), U7 (NetworkSummary para dimensión rendimiento), U3 (reporter). axe-core como dependencia nueva → cambio en `pyproject.toml` requiere confirmación humana (HITL de dependencias).

## Steps

### Step 1: Crear `src/classifier/models_audit.py` (o en `src/models.py`) [ ]
- **Acción**: CREATE/MODIFY
- **Contenido**: `AuditFinding` (dimension enum 6 valores, severity, page_url, step, data, evidence_refs, requires_human_review), `AuditHypothesis` (text, confidence 0–1, requires_human_review), `AuditReport` (findings, hypotheses, synthesis_available, document_md_url) — espejo de `$defs` del schema v2

### Step 2: Crear `src/executor/audit_data.py` — recolección cruda durante el flow [ ]
- **Acción**: CREATE
- **Contenido**: `AuditDataCollector` — listeners de consola JS (errores), requests fallidos/mixed content (de U7), precios observados por página (de U5), snapshot de meta/title/imágenes/alt en páginas clave. Solo RECOLECTA — no clasifica

### Step 3: Crear `src/classifier/collectors.py` — colectores deterministas [ ]
- **Acción**: CREATE
- **Contenido**: una función pura por dimensión: `collect_commerce_integrity` (comparación de precios PLP/PDP/cart + descuentos esperados), `collect_performance` (umbral sobre NetworkSummary/CWV), `collect_locale` (moneda/idioma/formato por perfil CO/EC), `collect_accessibility` (parse de resultados axe-core), `collect_client_health` (errores JS, 4xx/5xx, mixed content), `collect_content_integrity` (meta/SEO, imágenes rotas, alt). Cada una: `(raw_data) -> list[AuditFinding]`. Fallo individual → dimensión "no recolectada", nunca excepción al flow (H7.1 AC3)

### Step 4: Integrar axe-core en páginas clave [ ]
- **Acción**: MODIFY (`src/executor/audit_data.py`) + `pyproject.toml` (HITL dependencias)
- **Contenido**: inyección del script axe-core en páginas clave declaradas en FlowCatalog (NO en cada estado — RNF-15); serialización de violaciones WCAG AA (regla, impacto, nodo)

### Step 5: Crear `src/executor/evidence_policy.py` [ ]
- **Acción**: CREATE
- **Contenido**: `should_capture(event) -> CaptureDecision` implementando ADR-003: fail+final siempre; `finding-{dim}` cuando un colector emite hallazgo; `critical` solo en puntos declarados en FlowCatalog; nunca pasos OK limpios. Naming `{run_id}/{perfil}/{flujo}/{paso}-{fail|final|finding-{dim}|critical}.png`

### Step 6: Crear `src/classifier/audit_agent.py` [ ]
- **Acción**: CREATE
- **Contenido**: `synthesize(findings, network, steps) -> AuditSynthesis` — llamada Claude API (modelo `CLAUDE_MODEL`) con: sanitizador previo (sin credenciales/cookies/PII — RNF-14), presupuesto de tokens `AUDIT_AGENT_MAX_TOKENS` con truncado por severidad, timeout `AUDIT_AGENT_TIMEOUT_S`, prompt que EXIGE hipótesis con confidence y PROHÍBE veredictos de semáforo; output pasa filtro de redacción D12 antes de persistir

### Step 7: Crear `src/classifier/audit_document.py` [ ]
- **Acción**: CREATE
- **Contenido**: `render_document_md(report: AuditReport) -> str` — resumen ejecutivo legible para no-técnicos + sección por dimensión + cada hallazgo con evidencia enlazada; subida a S3 `{run_id}/audit-document.md`; si `synthesis_available=False` → documento con hallazgos crudos + nota "síntesis no disponible" (H7.5)

### Step 8: Modificar `src/reporter/report_generator.py` — integración [ ]
- **Acción**: MODIFY
- **Contenido**: `generate_report` acepta `audit: AuditReport | None`; lo serializa en el campo `audit` del schema v2; regla determinista: hallazgo con `requires_human_review=True` → semáforo YELLOW subtipo `human_review` (H7.3 AC1, en coordinación con U2 `compute_traffic_light`) — NUNCA en función del texto del agente

### Step 9: Crear `tests/test_collectors.py` [ ]
- **Acción**: CREATE
- **Contenido**: por dimensión con datos sintéticos — mismatch de precio → finding commerce_integrity con data correcta; moneda errada para perfil EC → finding locale; violación axe → finding accessibility; colector que lanza → dimensión no recolectada sin tumbar

### Step 10: Crear `tests/test_audit_agent.py` [ ]
- **Acción**: CREATE
- **Contenido**: Claude mockeado — síntesis OK produce AuditReport válido; excepción del cliente → `synthesis_available=False` y reporte igual emitido (H7.5 AC3); sanitizador: findings con valores tipo credencial llegan redactados al prompt; presupuesto: exceso de findings trunca por severidad y lo declara

### Step 11: Crear `tests/test_traffic_light_independence.py` [ ]
- **Acción**: CREATE
- **Contenido**: hallazgos con anomalía de comercio → YELLOW determinista aunque la síntesis del agente sea "todo se ve bien" (texto optimista mockeado); el campo `audit` no puede alterar `traffic_light` (C10 — test crítico del invariante P7)

### Step 12: Crear `tests/test_evidence_policy.py` [ ]
- **Acción**: CREATE
- **Contenido**: run limpio → solo fail+final (ADR-003); finding → exactamente una captura `finding-{dim}` enlazada en `evidence_refs`; `critical` solo en puntos del catálogo; naming correcto

## Validation
- `ruff check .` + `mypy src/` sin errores; tests de U6 verdes
- Reporte con `audit` valida contra `specs/execution_report.schema.json` v2
- Test C10 (independencia del semáforo) pasa — blocking
- Documento de auditoría legible validado con lectura de no-técnico (Valentina proxy — revisión humana)
- Criterio de completitud de unit-of-work.md U6 satisfecho (H7.1–H7.5 AC)
