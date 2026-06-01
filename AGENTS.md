# TestPilot SFCC

> Archivo de contexto cross-tool para cualquier coding agent (Claude Code, Cursor, Windsurf, Copilot, Devin, OpenCode).
> Si una herramienta también lee `CLAUDE.md` o `.cursorrules`, esos archivos apuntan aquí como source of truth.

---

## 1. Contexto del negocio

**¿Qué hace este producto?**
TestPilot SFCC es una plataforma interna de PASH para automatizar el QA de storefronts Salesforce Commerce Cloud (SFRA). Simula usuarios sintéticos que ejecutan flujos críticos de checkout via Playwright, orquestados por agentes de IA (Claude API), y entrega reportes estructurados (JSON + Markdown + semáforo verde/amarillo/rojo) consumibles tanto por humanos como por otros agentes del ecosistema interno.

**¿Quién es el usuario?**
Equipo de ingeniería de PASH (3-7 personas). Tech Leads y desarrolladores que hacen ≥2 deploys/mes de storefronts SFCC en LatAm. Actualmente invierten 4-8 horas en QA manual por release. El reporte en Markdown es consumido por humanos; el JSON es consumido por agentes downstream en el mismo ecosistema.

**¿Cuál es el estado actual?**
Fase de diseño/requisitos completada dentro del programa Hardcore AI Cohorte 2. Iniciando implementación del MVP. Objetivo semana 4: ciclo de QA < 30 minutos. Objetivo semana 12: gate automatizado de deploy (auto-approve en verde).

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
├── api/              ← FastAPI app, endpoint /v1/run y schemas de entrada/salida
├── agents/           ← Traducción NL → SyntheticUserConfig via Claude API
├── executor/         ← Runner de perfiles + flows Playwright
│   ├── flows/        ← Un archivo por flow (checkout_full.py, checkout_card_declined.py)
│   └── profiles/     ← Perfiles sintéticos (mobile_co.py, desktop_co.py, desktop_ec.py)
├── reporter/         ← Generación de reporte JSON + Markdown + semáforo
├── baseline/         ← Manager de DynamoDB: escritura, lectura, cálculo p95
└── classifier/       ← Clasificación de errores via Claude API (bug real vs comportamiento esperado)

specs/                ← JSON Schemas de SyntheticUserConfig y del reporte de salida (source of truth del contrato API)
infra/                ← AWS CDK stacks (Step Functions, ECS, DynamoDB, S3, API Gateway)
tests/                ← Unitarios (pytest) e integración
docs/                 ← PRD y documentación de planificación existente
```

**Decisiones de diseño no obvias:**
- **Catálogo cerrado de flows:** solo `checkout_full` y `checkout_card_declined` en MVP. El LLM traduce NL a un config que solo puede referenciar estos flows. La flexibilidad arbitraria de flows queda fuera de scope — reduce tasa de error del LLM de ~20% a casi cero.
- **Validación estricta antes de ejecutar:** todo `SyntheticUserConfig` generado por Claude se valida contra JSON Schema antes de levantar un solo browser. Config inválido = rechazo inmediato con error descriptivo, nunca ejecución parcial.
- **Cero contaminación:** el método de pago siempre falla en el paso final (no se crean órdenes reales). Los usuarios sintéticos siempre usan email `@testpilot.internal`. Esto es un invariante del sistema, no una configuración.
- **Screenshots solo en fallo + paso final:** capturar en cada paso costaría ~17 GB/mes en S3; con esta restricción son ~500 MB/mes.
- **Período de bootstrap (14 ejecuciones):** el semáforo no emite alertas amarillas hasta tener 14 runs exitosos en DynamoDB. Sin baseline suficiente no hay p95 confiable.
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
- Idioma: español, primera línea < 70 chars
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
- Agregar flows nuevos al catálogo sin confirmación explícita (el catálogo cerrado es intencional)
- Capturar screenshots en pasos intermedios (viola la restricción de costos de S3)

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
- No enviar requests directos a la API de Claude sin pasar por el módulo `src/agents/` (maneja reintentos, logging y validación)
- No escribir a DynamoDB directamente desde `src/executor/` — toda escritura de historial pasa por `src/baseline/`
- No emitir alerta amarilla durante las primeras 14 ejecuciones (período de bootstrap)

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

| Subagente | Modelo | Propósito |
|---|---|---|
| `feature-implementer` | Sonnet | Implementa features pequeñas con scope aprobado en `docs/features/`. |
| `flow-guardian` | Haiku | **Read-only.** Vigila que cambios a `src/executor/flows/` solo introduzcan flows declarados en el catálogo cerrado de `specs/`. |

---

*Última actualización: 2026-05-27 · Mantenido por: Christian Díaz (cdiaz@pash.com.co)*
