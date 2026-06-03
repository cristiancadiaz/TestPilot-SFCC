# TestPilot SFCC

> Archivo de contexto cross-tool para cualquier coding agent (Claude Code, Cursor, Windsurf, Copilot, Devin, OpenCode).
> Si una herramienta también lee `CLAUDE.md` o `.cursorrules`, esos archivos apuntan aquí como source of truth.

---

## 1. Contexto del negocio

**¿Qué hace este producto?**
TestPilot SFCC es una plataforma interna de PASH para automatizar el QA de storefronts Salesforce Commerce Cloud (SFRA). Cualquier miembro del equipo —técnico o no— **describe en lenguaje natural** lo que quiere validar y obtiene: **(a)** un veredicto de deploy-gate (semáforo verde/amarillo/rojo, regla determinista, <30 min) y **(b)** un **documento de auditoría del recorrido completo de la tienda** (búsqueda/PLP → PDP → carrito → checkout) que sintetiza 6 dimensiones con evidencia enlazada: integridad de comercio, rendimiento, locale, accesibilidad, salud del cliente y contenido. Usuarios sintéticos vía Playwright, agentes Claude API acotados (traductor pre-run + síntesis post-run), reportes JSON + Markdown consumibles por humanos y agentes.

**¿Quién es el usuario?**
Equipo de ingeniería de PASH (3-7 personas) + perfiles no-técnicos (QA/PM/negocio) vía la ventana de lenguaje natural. Tech Leads y desarrolladores que hacen ≥2 deploys/mes de storefronts SFCC en LatAm. Actualmente invierten 4-8 horas en QA manual por release.

**¿Cuál es el estado actual?**
**Realineación de alcance completada y aprobada (2026-06-03, branch `rework/storefront-audit-scope`):** inception rehecha, `specs/` en **v2**, planes de construcción listos. **Alcance fijo — ningún módulo se recorta; el tiempo es la variable de ajuste.** Ola 1 = gate de checkout (U0–U4 + MD0); ola 2 = recorrido + auditoría + red + ventana NL (U5–U8). Racional: `aidlc-docs/inception/scope-realignment-brief.md`.

---

## 2. Arquitectura

**Stack tecnológico:**
- Lenguaje: Python 3.12
- API: FastAPI (endpoint `/v1/run`)
- Browser automation: Playwright (Python)
- LLM: Claude API vía Anthropic Python SDK
- Orquestación: AWS Step Functions
- Ejecución: ECS Fargate + Docker (imagen Playwright oficial)
- Storage: DynamoDB (historial de ejecuciones + baselines), S3 (screenshots)
- Deploy infra: AWS CDK (Python)

**Estructura de carpetas:**
```
src/
├── api/              ← FastAPI app, endpoints /v1/run y /v1/translate, schemas de entrada/salida
├── agents/           ← Traductor NL → SyntheticUserConfig validado + preview (Claude API, pre-run)
├── executor/         ← Runner de perfiles + flows Playwright + captura de red + datos de auditoría
│   ├── flows/        ← Un archivo por flow: checkout_full, checkout_card_declined,
│   │                   search_and_filter, browse_discounted_products, pdp_validation, cart_review (ola 2)
│   ├── flow_catalog.py ← Registro del catálogo cerrado + composición full_journey + puntos críticos (ola 2)
│   └── profiles/     ← Perfiles sintéticos (mobile_co.py, desktop_co.py, desktop_ec.py)
├── reporter/         ← Reporte JSON + Markdown + semáforo determinista + integración de auditoría
├── baseline/         ← Manager de DynamoDB: escritura, lectura, cálculo p95 (solo runs modo gate)
└── classifier/       ← Agente de SÍNTESIS de auditoría (Claude API): hallazgos deterministas →
                        documento de 6 dimensiones. Sintetiza, NUNCA decide el semáforo (P7). (ola 2)

specs/                ← JSON Schemas v2 (config, reporte, translate) — source of truth del contrato API
infra/                ← AWS CDK stacks (Step Functions, ECS, DynamoDB, S3, API Gateway)
tests/                ← Unitarios (pytest) e integración
docs/                 ← PRD y documentación de planificación existente
```

**Decisiones de diseño no obvias:**
- **Catálogo cerrado de flows (specs v2):** `checkout_full`, `checkout_card_declined`, `search_and_filter`, `browse_discounted_products`, `pdp_validation`, `cart_review` + `full_journey` como **alias de composición** (el backend lo expande vía FlowCatalog — nunca es un archivo flow, el executor nunca lo ve). El catálogo crece SOLO curado vía PR; el usuario elige el alcance (módulo único / subconjunto / recorrido completo). Reduce tasa de error del LLM de ~20% a casi cero.
- **Validación estricta antes de ejecutar:** todo `SyntheticUserConfig` se valida contra JSON Schema v2 antes de levantar un solo browser. La instrucción NL se traduce, se muestra en preview, el usuario confirma — **la NL nunca llega al executor** (C12). Config inválido = rechazo inmediato con error descriptivo, nunca ejecución parcial.
- **Cero contaminación:** el método de pago siempre falla en el paso final (no se crean órdenes reales). Los usuarios sintéticos siempre usan email `@testpilot.internal`. Los flows de recorrido NO contienen pasos de pago — solo los `checkout_*` tocan pago. Esto es un invariante del sistema, no una configuración.
- **Evidencia dirigida por hallazgos (ADR-003):** fallo + paso final SIEMPRE (~500 MB/mes). En modo auditoría, capturas adicionales SOLO por hallazgo de un colector determinista (6 dimensiones) o punto crítico declarado en el FlowCatalog. Nunca capturas de pasos OK limpios. HAR: solo metadata+timings, sin bodies, con redacción.
- **El agente de auditoría sintetiza, no juzga (P7/C10):** el semáforo lo calcula EXCLUSIVAMENTE la regla determinista (p95). El LLM redacta el documento de auditoría e hipótesis con `confidence`/`requires_human_review`; no puede mover el veredicto. Si falla, el reporte sale igual con hallazgos crudos.
- **Modos gate/exploratorio:** gate = determinista, entra al baseline, veredicto de deploy. Exploratorio = descubrimiento; NUNCA entra al baseline ni cuenta como deploy-safe (C11). Cap 10 runs/día suma ambos.
- **Período de bootstrap (14 ejecuciones):** sin alertas amarillas hasta 14 runs exitosos — **por par perfil×flow** (cada flow nuevo del catálogo arranca su propio bootstrap).
- **Thresholds p95, no porcentajes fijos:** el baseline compara contra el percentil 95 de las últimas 10 ejecuciones, no contra un margen arbitrario.

---

## 3. Convenciones

**Estilo de código:**
- Formatter: `ruff format` (reemplaza Black + isort)
- Linter: `ruff check` con reglas E, F, I, UP habilitadas
- Type checking: `mypy --strict`
- Pre-commit: ruff + mypy solo sobre archivos modificados

**Nombrado:**
- Variables y funciones: `snake_case` (`get_execution_by_id`, no `getExecutionById`)
- Clases: `PascalCase` (`SyntheticUserConfig`, `PlaywrightExecutor`)
- Constantes: `SCREAMING_SNAKE_CASE` (`MAX_PROFILES`, `BOOTSTRAP_RUN_COUNT`)
- Archivos: `snake_case` (`checkout_full.py`, `baseline_manager.py`)
- Tipos derivados de Pydantic: prefijo del dominio (`ExecutionReport`, `UserProfile`)

**Commits:**
- Formato: Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Idioma: inglés, corto y conciso, primera línea < 70 chars
- Scope sugerido por módulo: `feat(executor):`, `fix(reporter):`, `refactor(baseline):`
- Tamaño: un commit = una intención lógica. Diff > 10 archivos → dividir.

**Tests:**
- Framework: pytest
- Naming: `test_should_[comportamiento]_when_[condición]` en inglés
- Mocks: usar `unittest.mock` solo para llamadas externas lentas o no deterministas (Claude API, DynamoDB, Playwright). Lógica de negocio sin mocks.
- Cobertura objetivo: >80% en `src/baseline/`, `src/reporter/`, `src/agents/`; >60% en `src/executor/`

---

## 4. Flujo de trabajo con el agente

**Lo que QUIERO que el agente haga automáticamente:**
- Después de cada `Edit` o `Write` sobre `.py`, ejecutar `ruff format` + `ruff check --fix` sobre el archivo afectado (configurado vía hook)
- Si un cambio toca más de 3 archivos, mostrar un plan en un único mensaje antes de aplicar
- Para tareas de exploración y lectura masiva, delegar al subagente `Explore` (Haiku) para ahorrar tokens
- Siempre validar que los emails de usuarios sintéticos en tests y fixtures usen el dominio `@testpilot.internal`

**Lo que SIEMPRE necesita mi confirmación:**
- Cambios a `specs/*.json` (el contrato de la API — cualquier cambio de campo es breaking)
- Cambios a `infra/` (afectan infraestructura AWS real)
- Cambios a `src/executor/flows/` (afectan lógica de ejecución en staging/producción)
- Cualquier comando con `rm -rf`, `--force`, `--no-verify`, o que afecte recursos AWS en producción
- Instalar nuevas dependencias (impacto en imagen Docker + costos Fargate)

**Lo que NO debe hacer:**
- Crear archivos fuera de `src/`, `specs/`, `infra/`, `tests/`, `docs/`
- Usar emails que no sean `@testpilot.internal` en datos sintéticos
- Hacer commits automáticamente — todos los cambios se quedan staged
- Relajar la validación JSON Schema de `SyntheticUserConfig` para "facilitar pruebas"
- Agregar flows nuevos al catálogo sin confirmación explícita (el catálogo cerrado es intencional; crece solo curado vía PR)
- Capturar screenshots fuera de la política ADR-003 (fallo/final siempre; hallazgo/punto crítico solo en auditoría — nunca pasos OK limpios "porque sí")
- Pasar la instrucción NL al executor o ejecutar un config sin confirmación del usuario (C12)
- Escribir runs exploratorios al baseline o dejar que el agente de auditoría toque el semáforo (C11, C10)

---

## 5. Restricciones

**Archivos protegidos (nunca leer ni editar):**
- `.env`, `.env.local`, `.env.production` — API keys de Claude, credenciales AWS, URLs de SFCC
- `secrets/` — claves de servicios externos
- `infra/cdk.context.json` — estado de CDK, no editar manualmente

**Carpetas que NO son contexto del proyecto (ignorar al explorar):**
- `.hardcore-ai/` — material de referencia personal del curso Hardcore AI Cohorte 2. Organizado por estación (`estacion-3/`, `estacion-4/`, ...). No habla de TestPilot SFCC. Solo consultar si el usuario pregunta explícitamente por una estación específica.

**Rutas que requieren máxima cautela:**
- `specs/` — contratos de API; un campo renombrado es un breaking change para agentes downstream
- `src/executor/flows/` — define exactamente qué acciones se ejecutan en el storefront; un bug aquí crea órdenes o contamina datos
- `src/baseline/` — lógica de p95 y bootstrap; errores aquí generan falsos semáforos

**Patrones a evitar:**
- No hardcodear selectores CSS/XPath de SFCC directamente en el código — usar constantes en `src/executor/selectors.py`
- No usar `time.sleep()` fijo en Playwright — usar `wait_for_selector()` o `expect()`
- No enviar requests directos a la API de Claude sin pasar por `src/agents/` (traductor) o `src/classifier/` (agente de auditoría) — manejan reintentos, logging, sanitización y validación
- No escribir a DynamoDB directamente desde `src/executor/` — toda escritura de historial pasa por `src/baseline/` (y solo runs gate al baseline)
- No emitir alerta amarilla durante las primeras 14 ejecuciones del par perfil×flow (período de bootstrap)
- No despachar flows con if/else por nombre — usar el registro del FlowCatalog; `full_journey` se expande antes del executor
- No alimentar al agente de auditoría con datos crudos del browser — solo hallazgos deterministas sanitizados (sin credenciales/cookies/PII)

**Decisiones ya tomadas que no debemos reabrir:**
- **Playwright, no Selenium.** API moderna, ejecución paralela de perfiles, mejor debugging con trace viewer.
- **ECS Fargate, no Lambda.** El binario de Playwright supera el límite de Lambda. Fargate permite ejecución paralela de los 3 perfiles.
- **Catálogo cerrado de flows, no NL arbitraria.** Reduce tasa de error del LLM de ~20% a casi cero para el gate de producción.
- **p95, no margen fijo.** Los tiempos de SFCC tienen varianza natural alta; un margen fijo generaría ruido constante.
- **Python, no Node.js.** SDK de Anthropic, boto3 y pytest tienen mejor DX para este tipo de proyecto de automatización/AI.

---

## 6. MCP servers

Configurados en `.mcp.json`. De los 6 servers del codelab Hardcore AI Clase 3, **4 están activos** y **2 marcados como N/A** porque no aplican al stack actual:

| Server | Estado | Por qué |
|---|---|---|
| `github` | ✅ activo | Lectura de issues / PRs / releases. Lo usa `/review` y el agente para context histórico. |
| `context7` | ✅ activo | Docs al día de FastAPI, Playwright Python, boto3, Anthropic SDK. Anti-alucinación. |
| `sequential-thinking` | ✅ activo | Razonamiento encadenado para baseline p95 y orquestación Step Functions. |
| `excalidraw` | ✅ activo | Diagramas de arquitectura. |
| `postgres` | ⚠️ N/A | Stack usa DynamoDB, no Postgres. Declarado pero `_active: false`. |
| `vercel` | ⚠️ N/A | Deploy es AWS (ECS + CDK), no Vercel. Declarado pero `_active: false`. |

**Regla:** no invocar herramientas de servers `_active: false` — el agente las verá listadas pero no debe consultarlas.

## 7. Skills disponibles

Estructura: `.claude/skills/<name>/SKILL.md` + recursos opcionales en `scripts/`, `references/`, `assets/`.

| Skill | Propósito |
|---|---|
| `ui-audit` | Auditoría del storefront SFCC bajo prueba (no del repo) — accesibilidad, layout breakpoints, selectores frágiles. |
| `generate-api-docs` | Generar/actualizar OpenAPI desde la definición FastAPI de `src/api/`. |
| `review-pr` | Code review enfocado en invariantes TestPilot (catálogo cerrado, zero contamination, screenshots policy). |
| `validate-synthetic-config` | Validar un payload `SyntheticUserConfig` contra `specs/synthetic-user-config.schema.json`. Skill custom del dominio. |
| `code-reviewer` | Review genérico preexistente (mantenido por compatibilidad). |

## 8. Subagentes

Roster operativo en `.claude/agents/` (proyección Claude Code); descripción conceptual tool-agnóstica en `.ai/roster.md`. Foco actual: **documentación + arquitectura AI-DLC**; generación de código diferida.

| Subagente | Modelo | Rol | Propósito |
|---|---|---|---|
| `leader` | Opus | 🟦 Orquestador | Orquesta el flujo AI-DLC: decide etapa, delega y hace cumplir las puertas de aprobación humana. Único con la tool `Agent`; no escribe artefactos. |
| `implementer` | Sonnet | 🟩 Principal | Autor de artefactos. Modo A (activo): documentación/arquitectura AI-DLC. Modo B (diferido): código de unidades / features ad-hoc. |
| `reviewer` | Sonnet | 🟩 Principal | Verifica artefactos contra el rule detail de la etapa, trazabilidad y `content-validation`. No edita; aprueba o rechaza. |
| `flow-guardian` | Haiku | 🟨 Especialista | **Read-only.** Vigila el catálogo cerrado de flows (v2: 6 flows + `full_journey`) y el contrato `specs/synthetic-user-config.schema.json`. |
| `sfcc-product-owner` | Sonnet | 🟨 Especialista | **Read-only.** Aporta criterio de producto/SFCC sobre requisitos, historias y NFR. |
| `design-steward` | Sonnet | 🟨 Especialista | Diseño visual y memoria de producto: `PRODUCT.md`, `DESIGN.md`, slides. |

Perfiles de referencia (no cargables) en `.claude/profiles/`.

---

*Última actualización: 2026-06-03 (realineación de alcance — catálogo v2, agente de auditoría, evidencia por hallazgos, modos gate/exploratorio) · Mantenido por: Christian Díaz (cdiaz@pash.com.co)*
