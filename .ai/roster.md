# Roster de Agentes — TestPilot SFCC (capa neutral, tool-agnóstica)

> **Qué es este archivo.** La descripción **conceptual** del equipo de agentes y
> del flujo de trabajo, independiente de la herramienta. Aquí vive el **QUÉ**
> (roles, responsabilidades, foco AI-DLC, puertas de control). El **CÓMO** —
> frontmatter, `tools`, `model`, hooks, rutas exactas— vive en la carpeta nativa
> de cada herramienta (su "proyección").
>
> Fuentes de verdad relacionadas: `AGENTS.md` (instrucciones de proyecto,
> estándar cross-tool) y `.aidlc-rules/aws-aidlc-rules/core-workflow.md` (guía del
> flujo AI-DLC). Este roster NO se ejecuta solo: cada herramienta lo proyecta.

## Proyecciones por herramienta

| Capa | Ubicación | Qué contiene |
|---|---|---|
| **Neutral (fuente)** | `AGENTS.md`, `.ai/` | instrucciones de proyecto, este roster, prompts, perfiles |
| **Claude Code** | `.claude/agents/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/skills/`, `.mcp.json` | subagentes operativos (con frontmatter), hooks, permisos, skills |
| **Otras (futuro)** | `.codex/`, `.cursor/`, `.opencode/` | misma intención, en el formato nativo de cada tool |

> Regla: para montar otra herramienta NO se copia `.claude/`. Se lee este roster
> + `AGENTS.md` + `core-workflow.md` y se crea la proyección en el dialecto de esa
> herramienta.

## Enfoque actual (2026)

Inception está completo; el proyecto está en **Station 4 (reconciliación)** y la
**generación de código no ha empezado**. El foco del equipo es **documentación y
definición de arquitectura** (`aidlc-docs/`, `docs/`). La generación de código es
**modo futuro**: se activa solo cuando `aidlc-docs/aidlc-state.md` marque esa fase
y el humano la apruebe.

## Taxonomía: orquestador · principales · especialistas

Dos formas de clasificar el equipo. La primera es **estructural** (la impone la
herramienta); la segunda es **funcional** (el rol en el arnés).

**Estructural — ¿quién puede lanzar a quién?** En Claude Code todos viven en
`.claude/agents/` y técnicamente son subagentes; lo que distingue al orquestador
es que **solo `leader` tiene la herramienta `Agent`** (puede invocar a los demás).
El resto son **trabajadores hoja**: no pueden lanzar subagentes.

**Funcional — rol en el arnés:**

| Capa | Agente(s) | Rol |
|---|---|---|
| 🟦 **Orquestador del arnés** | `leader` | Coordina el flujo AI-DLC, decide etapas, hace cumplir gates HITL. Único con `Agent`. No produce. |
| 🟩 **Agentes principales** (ciclo núcleo) | `implementer`, `reviewer` | El bucle **produce → verifica** que el leader ejecuta en cada etapa. |
| 🟨 **Subagentes especialistas** (on-demand) | `flow-guardian`, `sfcc-product-owner`, `design-steward` | Se invocan cuando la etapa lo requiere: guardián, asesor de criterio, productor visual. |

> Tu intuición es correcta: `leader` (orquestador) + `implementer` + `reviewer`
> son los **principales**; los otros tres son **especialistas** que entran según
> la necesidad de la etapa.

## El equipo (responsabilidades — el "QUÉ")

### leader — Orquestador AI-DLC
Descompone el trabajo por **etapas de `core-workflow.md`**, decide qué etapa toca
(ALWAYS vs CONDITIONAL con evaluación inteligente), delega y hace cumplir las
**puertas de aprobación humana** (HITL). Registra en `audit.md`, actualiza
`aidlc-state.md`. **Nunca produce artefactos ni código**; solo coordina.

### implementer — Autor de artefactos
Produce **una** pieza por sesión. **Modo A (activo):** documentación/arquitectura
AI-DLC siguiendo el rule detail de la etapa, `content-validation.md` y la
profundidad de `depth-levels.md`. **Modo B (diferido):** generación de código de
unidades / features, cuando se abra Construction Code Generation.

### reviewer — Verificador
Aprueba o rechaza (no edita). **Modo A:** valida artefactos contra el rule detail
de la etapa, trazabilidad de la cadena (requisito→historia→diseño→unidad→ADR),
validación de contenido y compliance de extensiones. **Modo B (diferido):**
revisión de código (gates, boundaries, invariantes).

### flow-guardian — Guardián del catálogo (read-only)
Vigila el **catálogo cerrado de flows** y el **contrato del JSON Schema**. Bloquea
cambios que rompan invariantes 2 y 7. Relevante en la fase de código; en fase doc
solo aplica si se documentan flows/contratos.

### sfcc-product-owner — Asesor de producto/SFCC (read-only)
Aporta **criterio** de negocio, ecommerce y Salesforce Commerce Cloud sobre
requisitos, historias, NFR y priorización. No escribe artefactos; su salida es
insumo para implementer/reviewer/humano.

### design-steward — Curador de diseño visual y memoria de producto
Crea/mantiene `PRODUCT.md` y `DESIGN.md`, produce material visual (slides, PDF)
con estándar anti-AI-slop. No toca código ni contratos.

## Perfiles de rol (lectura humana)

Los perfiles extensos de las personas/roles detrás de estos agentes viven en
`.claude/profiles/` (separados de los agentes cargables para no ensuciar el loader):
- `.claude/profiles/ai_agentic_architect_profile.md` — perfil del orquestador (sustento del `leader`).
- `.claude/profiles/perfil_ecommerce_sfcc_product_owner.md` — perfil de producto/SFCC (sustento del `sfcc-product-owner`).

> Nota: son documentos **portables** (sin frontmatter de herramienta). Si en el
> futuro se añaden más herramientas, conviene moverlos a `.ai/profiles/` para que
> cualquier tool los lea sin depender de `.claude/`.

## Flujo de orquestación (resumen)

```
leader  →  elige etapa AI-DLC según aidlc-state.md / core-workflow.md
        →  implementer redacta el artefacto en aidlc-docs/<fase>/<etapa>/
        →  reviewer valida (+ sfcc-product-owner si hay criterio de negocio)
        →  leader presenta completitud y PARA en la puerta de aprobación humana
        →  (humano aprueba) → audit.md + checkboxes en aidlc-state.md → siguiente etapa
```

---

*Capa neutral creada el 2026-05-31. Reemplaza los agentes SDD obsoletos que vivían
en `.ai/agents/` (modelo `feature_list.json` / `init.sh` / `spec_author`, ajeno a
AI-DLC). La proyección operativa activa es Claude Code en `.claude/`.*
