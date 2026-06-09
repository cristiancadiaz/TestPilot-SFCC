# HANDOFF — TestPilot SFCC · continuar en U8 (NL Window + modos)

> Documento de traspaso para retomar la generación de U8 en una sesión nueva.
> Generado 2026-06-09 tras cerrar U5 (`8b412d8`) y U7 (`296b980`). Pégalo al inicio
> de una sesión nueva (mismo repo) para que otro modelo retome U8 sin perder contexto.

Eres Claude Code trabajando en **TestPilot SFCC** (rama `rework/storefront-audit-scope`).
Sigues el workflow **AI-DLC** definido en `CLAUDE.md` (Construction → Code Generation
por unidad: Part 1 Planning con aprobación HITL → Part 2 Generation → Gate → commit).

## Regla de sesión (obligatoria)
Vigila el uso de tokens. **Si superas el 80% de la ventana de contexto, DETENTE y guarda
estado** (checkboxes del plan + `aidlc-docs/aidlc-state.md` + append a `aidlc-docs/audit.md`)
antes de continuar. U8 es la unidad más pesada — si ves que no cabe completa, genera por
fases y para en un punto limpio.

## Dónde quedamos (hechos)
Ola 2 en curso. Completado y COMMITEADO (sin push):
- **U5 Journey Flows** — Gate U5 cerrado — commit `8b412d8`
- **U7 Network Capture** — Gate U7 cerrado — commit `296b980`
- Suite completa: **213 tests verde**. ruff + mypy --strict (45 files) limpios.
- Pendiente: **U8** (siguiente), luego **U6 Audit** (depende de U5+U7 ✅), luego **Infra/CDK**
  (adapters boto3 detrás de los Protocols de U4) y el **push** de la rama.

## U8 — plan YA reconciliado y APROBADO
El plan vive en `aidlc-docs/construction/plans/u8-code-generation-plan.md` (reconciliado a
la realidad actual, Part 1 aprobado). **Léelo primero.** Genera Part 2 contra ese plan.

### Realidad actual que el plan original (2026-06-03) NO reflejaba — verifícalo:
- `src/agents/` **NO existe** → el translator se **crea desde cero** (aquí aterriza TASK-005).
- **No hay** `src/api/main.py` → la API es `src/api/app.py` (factory) + `src/api/routers/`.
  El endpoint nuevo va en `src/api/routers/translate.py` y se cablea en `app.py`.
- `SyntheticUserConfig.mode` (Literal["gate","exploratory"]="gate") **ya existe** en `src/models.py`.
- El **baseline gate-only (C11) ya está implementado** (`src/baseline/baseline_manager.py`
  descarta exploratory) → U8 solo añade el PBT que lo confirma.
- `GET /v1/runs/latest` gate-only **ya existe** (U4 Phase B).
- El dashboard es un proyecto **Vite/React/TS en la RAÍZ del repo** (`index.html`,
  `eslint.config.js`, `dist/`), NO `src/dashboard/`. Toolchain: pnpm + vitest + tsc strict + eslint.
- El **cap diario de 10 runs/día (invariante #7) NO está implementado** en ningún lado.

### Decisiones HITL ya tomadas (aplícalas, no las re-preguntes):
- **D-U8-1**: crear `src/agents/__init__.py` + `translator.py`. Claude API vía Anthropic SDK
  detrás de un Protocol inyectable + fake in-memory (los tests NUNCA llaman a la API real,
  mismo patrón que los fakes de AWS en U4). Todas las llamadas a Claude viven aquí (boundary).
- **D-U8-2**: endpoint como `routers/translate.py` cableado en `app.py` (reusa security/
  middleware/taxonomía de errores de U4); el factory recibe una dependencia `translator`.
- **D-U8-3**: gate post-traducción reusa el catálogo cerrado: valida el config propuesto
  contra `specs/` v2 (jsonschema) Y `flow_catalog.expand_flows` ANTES de responder (P3).
  Fuera de catálogo / inyección → 422 `instruction_rejected` + log. El endpoint NUNCA lanza browser.
- **D-U8-4**: filtro de modo en baseline ya satisfecho (C11) → solo PBT confirmatorio.
- **D-U8-5 (APROBADA = guard in-app AHORA)**: implementar guard que cuenta runs del día
  (gate+exploratory) → `429 rate_limited` al llegar a 10 (invariante #7). Nueva fila en la
  taxonomía de errores. Enforcement final queda para infra.
- **D-U8-6**: ventana NL en el dashboard React de la raíz. Textarea NL como vía principal en
  NewRun → "Traducir" → preview (explanation + config legible) → "Confirmar y lanzar" →
  POST /v1/run; editor JSON como toggle avanzado; selector gate/exploratory; exploratory
  marcado visualmente en historial/detalle.
- Nota: gates **D-NL** (Q1≥90%, Q2=100%) son evaluación operativa pre-lanzamiento (dataset),
  NO código. **RT1** (Q8=0) SÍ es código: `tests/test_prompt_injection.py`.

### Decisión PENDIENTE para el usuario (pregúntala al arrancar):
Alcance de esta sesión dado el presupuesto: **(a)** solo backend Python de U8 (translator +
endpoint + RT1 + cap diario + tests) dejando la ventana NL del dashboard React para otra
sesión, o **(b)** U8 completa (backend + dashboard). El dashboard es lo más caro en tokens.

## Invariantes a respetar (de CLAUDE.md — NO relajar)
- **C12**: la NL NUNCA llega al executor — `src/executor/` no importa `src/agents` (test estático grep).
- **C11**: runs exploratory NUNCA al baseline ni a latest-gate.
- **Catálogo cerrado** (invariante #2): el translator elige SOLO del catálogo; full_journey
  es alias de composición (lo expande FlowCatalog). Nada de flows arbitrarios.
- **Cero contaminación** (#1): los journey flows no tocan pago; emails `@testpilot.internal`.
- **RT1**: suite anti-inyección 100% bloqueada (Q8=0), blocking antes de exponer la ventana NL.
- **NL ≤ 2000 chars** (RNF-05).
- **specs/*.json** son contrato breaking-change — confirma con humano antes de tocarlos.
- Rutas que requieren confirmación HITL antes de editar: `specs/`, `infra/`,
  `src/executor/flows/`, `pyproject.toml`/`uv.lock`, `.github/workflows/`.

## Obligaciones AI-DLC (de CLAUDE.md)
- Marca los checkboxes del plan `[x]` en la MISMA interacción en que completes cada step.
- Actualiza `aidlc-docs/aidlc-state.md` al cerrar el Gate U8.
- **APPEND** (nunca sobrescribir) a `aidlc-docs/audit.md`: registra input del usuario + acción.
- **Commit solo cuando el usuario lo pida.** Commits en inglés, Conventional Commits, y
  terminados con: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Verificación (Gate U8)
```bash
uv run ruff check src/agents/ src/api/ tests/test_translate_endpoint.py tests/test_prompt_injection.py tests/test_modes.py tests/test_executor_no_translator_import.py
uv run mypy src
uv run pytest                       # la suite completa (ahora 213) debe seguir verde
pnpm build && pnpm test             # dashboard (si haces D-U8-6)
```
Gate U8: RT1 100% bloqueada (Q8=0) · executor sin import del translator (C12 grep) ·
exploratory fuera de baseline+latest (C11) · NL≤2000 · injection→422 instruction_rejected+log ·
ruff+mypy limpios · dashboard tsc+vitest+eslint verde (si aplica).

## Stack / convenciones
Python 3.12 + `uv`. FastAPI. Playwright. Anthropic SDK. Hay un hook que corre `ruff format` +
`ruff check --fix` tras cada edición .py. Skill útil: `/validate-synthetic-config`.
Modelo: claude-opus-4-8. Lee `CLAUDE.md`, `AGENTS.md` y `specs/translate-request-response.schema.json`
antes de generar.

## Primer paso sugerido en la sesión nueva
1. Lee `u8-code-generation-plan.md`, `specs/translate-request-response.schema.json`,
   `src/api/app.py`, `src/api/routers/runs.py` (patrón de router), `src/api/errors.py`,
   `src/api/stores.py` (patrón Protocol+fake) y `src/models.py` (`SyntheticUserConfig`, `Mode`).
2. Confirma con el usuario el alcance (backend-only vs +dashboard) y arranca Part 2 por fases.
