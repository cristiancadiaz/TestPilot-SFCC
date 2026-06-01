---
tipo: glosario
proyecto: TestPilot SFCC
actualizado: 2026-05-29
tags: [glosario, referencia]
---

# 📖 Glosario — TestPilot SFCC

> Definiciones canónicas, ordenadas por bloques temáticos. Copia versionada del
> glosario del vault Obsidian (`.hardcore-ai/GLOSARIO.md`, gitignored); aquí los
> enlaces internos del vault se presentan como texto plano. Las referencias a
> `paso-NN-...` apuntan al plan de ejecución en `.hardcore-ai/plan-ejecucion/`.

---

## Metodología y framework

### AI-DLC
*AI-Driven Development Lifecycle.* Framework de AWS Labs (v0.1.8) para construir software con un agente que guía el ritmo en fases: **Inception** (el QUÉ) → **Construction** (el CÓMO) → Operations. Su "cerebro" es `core-workflow.md`, copiado al `CLAUDE.md` del repo. Ver `paso-04-indices-canonicos-aidlc`.

### Inception
Primera fase de AI-DLC: define **qué** construir y **por qué**. Produce 6 artefactos (workspace-detection, requirements-analysis, user-stories, workflow-planning, application-design, units-generation). Es la entrada obligatoria de Construction.

### Construction
Segunda fase de AI-DLC: define **cómo** construir. Por cada Unit of Work ejecuta 5 actividades: Diseño Funcional → NFR Requirements → NFR Design (ADR) → Infrastructure Design → Code Generation. Ver pasos `paso-05-codegen-u0`–`paso-11-build-and-test`.

### Spec-Driven Development
Desarrollo guiado por especificación: la spec aprobada es el objetivo; el código es consecuencia. *"La tarea no es llegar al código, es generar la especificación más completa posible."*

### Unit of Work
*Unidad de trabajo.* Agrupación lógica de módulos que se construye y testea de forma incremental. En TestPilot son 6: **MD0** (dashboard), **U0** (setup base), **U1** (executor), **U2** (baseline), **U3** (reporter), **U4** (API). No son microservicios — el sistema es un monolito Python modular.

### ADR
*Architecture Decision Record.* Documento corto que captura una decisión arquitectónica: contexto, decisión, alternativas descartadas y **consecuencias** (con ⚠️ obligatorio — toda decisión tiene costo). Ver `paso-04-indices-canonicos-aidlc`.

### NFR
*Non-Functional Requirement.* Requisito de calidad (performance, seguridad, disponibilidad). Regla de oro: sin un **valor numérico verificable** no es un NFR (ej. `p95 < 500ms`). Ver p95.

### C4 model
Notación de diagramas de arquitectura en 4 niveles: Contexto, Contenedores, Componentes, Código. TestPilot documenta niveles 1–2 en Mermaid.

### Gherkin
Lenguaje de escenarios `DADO / CUANDO / ENTONCES` para historias de usuario. El `ENTONCES` debe ser verificable automáticamente; los tests de integración trazan a estos escenarios. Ver `paso-11-build-and-test`.

### DDD
*Domain-Driven Design.* Patrones tácticos usados en el Diseño Funcional: **Entity** (identidad propia), **Value Object** (inmutable, sin identidad), **Aggregate** (raíz de consistencia), **Domain Service**. Lenguaje ubicuo = nombres del dominio reflejados en el código.

### MoSCoW
Priorización de scope: **M**ust / **S**hould / **C**ould / **W**on't. Usado en el PRD §8.

### PVB / ISB / PRD / ICP
Artefactos de producto. **PVB** Product Vision Board (startup). **ISB** Internal Solution Brief (problema interno de empresa — el caso de TestPilot). **PRD** Product Requirements Document (13 segmentos, co-creado con IA en E2). **ICP** Ideal Customer Profile.

---

## Ingeniería agéntica (Estación 3)

### ReAct
Bucle de razonamiento del agente: **Pensar → Planificar → Ejecutar → Observar → Corregir**. Diferencia un agente de un autocomplete: decide qué herramientas usar observando el entorno.

### Context Engineering
Diseñar el entorno del agente (`CLAUDE.md`, `AGENTS.md`, hooks, permisos) para producir resultados verificables. Pesa más que el prompting.

### CLAUDE.md
Memoria de proyecto específica de Claude Code: workflow, invariantes, comandos. En TestPilot contiene el framework AI-DLC y los invariantes duros.

### AGENTS.md
Estándar cross-tool (lo leen Claude Code, Cursor, Windsurf, Copilot, OpenCode): arquitectura, convenciones y reglas de agentes. Ver `paso-02-opencode-config`.

### MCP
*Model Context Protocol.* Protocolo para conectar el LLM a fuentes externas vía servidores. TestPilot declara 6 en `.mcp.json` (GitHub, Context7, Sequential Thinking, Excalidraw activos; PostgreSQL y Vercel inactivos con razón).

### Skill
Capacidad modular y versionable del agente, estructura `<skill>/SKILL.md` con frontmatter (`name`, `description`) y recursos en `scripts/`/`references/`. TestPilot tiene `ui-audit`, `generate-api-docs`, `review-pr` + el propio `validate-synthetic-config`. Ver `paso-12-estacion6-design-skills`.

### Subagente
Agente especializado con rol acotado, definido en `.claude/agents/<nombre>.md` (modelo, tools, contexto). TestPilot: `flow-guardian`, `feature-implementer`, `sfcc-product-owner`, `design-steward`.

### Hook
Script determinista que el harness ejecuta automáticamente ante un evento. **PostToolUse** (ej. lint tras cada edición) y **PreToolUse** (ej. bloquear comandos peligrosos). Los hooks son código, no instrucciones advisory. Ver `paso-01-hooks-deterministas`.

### opencode.json
Configuración de OpenCode: modelo (cloud/local), MCPs y referencia a `AGENTS.md` como estándar cross-tool. Ver `paso-02-opencode-config`.

### Antigravity
Orquestador visual de Google (*Mission Control*: Agent Manager + editor Monaco). Permite sesiones paralelas sobre el mismo repo en ramas independientes. Ver `paso-03-antigravity-paralelo`.

### headless (claude -p)
Modo no interactivo de Claude Code (`claude -p "..."`) para integrarlo en CI/CD.

---

## Producto TestPilot (invariantes y dominio)

### Zero contamination
Invariante: el pago **siempre falla** en el paso final (no se crean órdenes reales) y los emails sintéticos siempre usan `@testpilot.internal`. Validado con `assert orders_created == 0`. Ver `paso-06-codegen-u1`.

### Closed flow catalog
Catálogo cerrado de flows: solo `checkout_full` y `checkout_card_declined` en MVP. El LLM elige del catálogo, no genera flows libres → baja el error del LLM de ~20% a casi cero.

### JSON Schema gate
Todo SyntheticUserConfig se valida contra `specs/` antes de lanzar un browser. Config inválido = rechazo inmediato.

### SyntheticUserConfig
Modelo Pydantic que parametriza un run (environment_id, productos, flows, perfiles). Definición única en `src/models.py` tras `paso-05-codegen-u0`.

### ExecutionReport
Artefacto de salida dual: JSON estable (`specs/execution_report.json`, `additionalProperties:false`) para agentes + Markdown con semáforo para humanos. Ver `paso-09-codegen-u3`.

### p95
Percentil 95 de la latencia sobre la ventana de las últimas 10 ejecuciones exitosas. Base del semáforo; se usan thresholds p95 (no porcentajes fijos) por la alta varianza de SFCC.

### bootstrap
Período honesto inicial: durante las primeras **14 runs exitosas** no se emiten alertas amarillas (sin historia no hay p95 confiable). Ver `paso-07-codegen-u2`.

### traffic light (semáforo)
Veredicto de 3 estados: **verde** (apto), **amarillo** (degradación vs p95), **rojo** (fallo funcional). El del reporte = peor semáforo entre los 3 perfiles.

### Property-Based Testing
Testing con `hypothesis`: en vez de casos fijos, valida propiedades (ej. monotonicidad de p95, idempotencia del bootstrap) sobre inputs generados. Ver `paso-07-codegen-u2`.

### Protocol / Strategy
Patrón Python (`typing.Protocol` + implementación concreta) que permite swap futuro (ej. `InMemoryBaselineStore` → DynamoDB) sin tocar consumidores.

---

## Stack y plataforma

### Pydantic
Librería de validación de modelos (v2.9.2). Base de SyntheticUserConfig y ExecutionReport; `model_dump(by_alias=True)` para camelCase.

### Playwright
Automación de browser headless (1.48.0, async). Ejecuta los flows de checkout. Anti-flake: `wait_for_selector`/`expect`, prohibido `time.sleep`. Imagen Docker base `mcr.microsoft.com/playwright/python`.

### FastAPI
Framework web async (0.115.0). Sirve `/v1/run` y los GET. Auth por header `X-API-Key`. Ver `paso-10-codegen-u4`.

### Mangum
Adapter ASGI para desplegar FastAPI en AWS Lambda.

### ruff / mypy
`ruff` = linter + formatter. `mypy --strict` = type checking. Gate de calidad desde `paso-05-codegen-u0`.

### Step Functions / ECS Fargate / DynamoDB / S3 / Secrets Manager
Plataforma AWS: **Step Functions** orquesta los 3 perfiles en paralelo · **ECS Fargate** corre el contenedor Playwright · **DynamoDB** historial + baseline · **S3** screenshots · **Secrets Manager** credenciales (nunca en el payload).

### supply chain
Cadena de suministro del build: versiones *pinned*, imagen base verificada, modelo LLM actualizado → build reproducible (RNF-10/08). Ver `paso-05-codegen-u0`.

---

*TestPilot SFCC · 2026-05-29.*
