# U8 Ventana NL + Modos de Operación — Code Generation Plan

> ★ Realineación 2026-06-03 — ola 2. Prerrequisitos: U0 (translator), U2 (filtro de baseline), U4 + MD0 operativos, `specs/` v2 (HECHO). Paralelizable con U5 y U7.

## Unit Context
- **Tipo**: Brownfield — extiende `src/agents/translator.py`, `src/api/`, `src/baseline/`, `src/dashboard/`
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Stories cubiertas**: H9.1, H9.2, H9.3 — RF-27, RF-28
- **Restricciones**: la NL NUNCA llega al executor (C12) · runs exploratorios NUNCA al baseline (C11) · validación P3 estricta (schema + catálogo) · RT1 prompt injection 100% bloqueado (Q8=0) · NL ≤2000 chars (RNF-05)

## Dependencies
Requiere U0 (translator existente), U4 (API), MD0 (dashboard). El contrato está en `specs/translate-request-response.schema.json`.

## Steps

### Step 1: Modificar `src/models.py` — campo mode + modelos translate [ ]
- **Acción**: MODIFY
- **Contenido**: `SyntheticUserConfig.mode: Literal["gate","exploratory"] = "gate"`; `TranslateRequest` (instruction 2..2000), `TranslateResponse` (status ok|ambiguous, proposed_config, explanation, clarification_question) — espejo del schema

### Step 2: Modificar `src/agents/translator.py` — promoción a componente principal [ ]
- **Acción**: MODIFY
- **Contenido**: catálogo extendido v2 en el prompt (6 flows + full_journey); mapeo de alcance ("revisa solo el carrito" → cart_review; "toda la tienda" → full_journey — RF-22 AC6); detección de ambigüedad → `status="ambiguous"` con pregunta de clarificación (NUNCA adivinar, P3); generación de `explanation` legible en español neutro; defensa de prompt injection (instrucciones del sistema endurecidas + validación posterior)

### Step 3: Crear endpoint `POST /v1/translate` en `src/api/` [ ]
- **Acción**: MODIFY (`src/api/main.py` o router nuevo)
- **Contenido**: auth X-API-Key; valida `instruction` ≤2000; llama translator; valida el config propuesto contra JSON Schema v2 + catálogo ANTES de responder (P3); fuera de catálogo / injection → 422 `instruction_rejected` + log del intento (RT1); NO ejecuta nada — el run requiere POST /v1/run posterior con el payload confirmado

### Step 4: Modificar `POST /v1/run` y servicios — modo [ ]
- **Acción**: MODIFY
- **Contenido**: acepta `mode` (default gate); `RunOrchestrator` propaga el modo al reporte; `GET /v1/runs/latest` con semántica gate-only para decisión de deploy (RF-28 AC4 — los exploratorios no aparecen como latest de gate); cap 10 runs/día suma ambos modos

### Step 5: Modificar `src/baseline/baseline_manager.py` — filtro por modo [ ]
- **Acción**: MODIFY
- **Contenido**: `save_run` no persiste al baseline runs con `mode="exploratory"` (C11) — o los persiste marcados y `get_last_n_runs` los excluye del cálculo (decisión de diseño local, documentar); PBT: p95 nunca incluye runs exploratorios

### Step 6: Dashboard MD0 — ventana NL (P2) [ ]
- **Acción**: MODIFY (`src/dashboard/`)
- **Contenido**: campo de texto NL como vía principal en NewRun; botón "Traducir" → muestra preview (explanation + config legible) → botón "Confirmar y lanzar" → POST /v1/run; editor JSON queda como vía avanzada (toggle); selector de modo gate/exploratory con explicación; runs exploratorios marcados visualmente en historial y detalle

### Step 7: Crear `tests/test_translate_endpoint.py` [ ]
- **Acción**: CREATE
- **Contenido**: con Claude mockeado — instrucción válida → status ok + config que valida contra schema v2 + explanation presente; ambigua → status ambiguous + clarification_question; >2000 chars → 422; sin API key → 401; el endpoint NUNCA lanza browser (assert executor no invocado)

### Step 8: Crear `tests/test_prompt_injection.py` [ ]
- **Acción**: CREATE
- **Contenido**: suite RT1 del PRD §11.4 (5 escenarios: ignora reglas, flujo fuera de catálogo, flujo malicioso, devuelve env vars, jailbreak prefix) → 100% rechazados con 422 + log; gate Q8=0

### Step 9: Crear `tests/test_modes.py` [ ]
- **Acción**: CREATE
- **Contenido**: run exploratory no aparece en p95 (PBT con mezcla de modos); `latest` para gate ignora exploratorios; reporte exploratory lleva `mode="exploratory"`; cap diario suma ambos modos

## Validation
- `ruff check .` + `mypy src/` sin errores; tests de U8 verdes
- Suite RT1 al 100% bloqueada (blocking antes de exponer la ventana NL)
- Gates D-NL: Q1 ≥90%, Q2 = 100% (evaluación contra dataset D-NL — actividad operativa pre-lanzamiento)
- Test C12: el executor no tiene import del translator (grep estático)
- Criterio de completitud de unit-of-work.md U8 satisfecho (H9.1–H9.3 AC)
