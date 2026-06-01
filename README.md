# TestPilot SFCC

> Plataforma interna de testing continuo con usuarios sintéticos para storefronts Salesforce Commerce Cloud (SFCC / SFRA).

Dashboard interno + agente de testing que permite configurar y lanzar flujos automatizados con usuarios sintéticos sobre tiendas SFCC, visualizar resultados en tiempo real y obtener un semáforo de deploy-gate consumible tanto por humanos como por otros agentes del ecosistema interno.

---

## El problema

Las tiendas SFCC del equipo no tienen testing automatizado. Cada release se valida manualmente: un ingeniero navega checkout, búsqueda y PDP en distintos dispositivos — entre **4 y 8 horas por ciclo** que no escalan con la frecuencia de deploys.

| Métrica | Situación actual |
|---|---|
| Ciclo de QA por release | 4–8 h de ingeniería |
| Flujos E2E con cobertura automatizada | 0 |
| Tiempo de detección de regresión de performance | Días o semanas |
| Historial de performance | No existe |
| Costo estimado de un bug en checkout en producción | USD 500–50,000 (según volumen y duración) |

Cada segundo adicional de carga en mobile reduce conversión 4.42% (Google/SOASTA). Una regresión de 2 s no detectada durante 2 semanas puede costar 8–9% en conversión perdida.

---

## La solución

Antes de cada deploy, el agente ejecuta automáticamente 2–3 flujos críticos con perfiles sintéticos parametrizados y entrega un semáforo (verde / amarillo / rojo) en menos de 10 minutos.

**Criterios de éxito (semana 4):**

| Métrica | Objetivo |
|---|---|
| Ciclo de QA por release | <30 min de revisión de reporte |
| Flujos E2E automatizados | 2 flujos críticos |
| Tiempo de detección de regresión | <1 h |
| Confianza para deployar sin QA manual | 70% en flujos cubiertos |
| Reportes consumibles por humanos y agentes | 1 por ejecución |

**Objetivo semana 12:** gate automatizado de deploy (auto-approve en verde).

---

## Cómo funciona

```
Dashboard web interno
(JSON: environment_id + productos + flujos + perfiles, SIN credenciales en payload)
              │
              ▼
   POST /v1/run  (API REST versionada)
              │
              ▼
   Claude API — NL → SyntheticUserConfig (validado contra JSON Schema)
              │
              ▼
   AWS Step Functions — orquesta 3 perfiles en paralelo
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
mobile/CO  desktop/CO  desktop/EC
   │          │          │
   └──────────┼──────────┘
              ▼
   ECS Fargate + Playwright
   Flujo: login → búsqueda → categoría → PDP → carrito → checkout
              │
        ┌─────┴──────┐
        ▼            ▼
   Screenshots    Métricas
   OK + FAIL      (tiempo/paso, HTTP, errores)
   en S3
              │
              ▼
   Claude API — clasifica errores + genera resumen markdown
              │
              ▼
   Output: JSON + Markdown + semáforo
   DynamoDB (historial + baseline p95)
```

**Flujos en MVP:**
- `checkout_full`: login → búsqueda → categoría → PDP → carrito → checkout con pago que falla en el paso final
- `checkout_card_declined`: mismo recorrido, tarjeta rechazada, validar mensaje de error

**Perfiles sintéticos:** mobile/Colombia, desktop/Colombia, desktop/Ecuador.

---

## Stack

- **Lenguaje:** Python 3.12 (gestor de paquetes `uv`)
- **API:** FastAPI — endpoint `/v1/run`
- **Browser automation:** Playwright (Python)
- **LLM:** Claude API vía Anthropic Python SDK
- **Orquestación:** AWS Step Functions
- **Ejecución:** ECS Fargate + Docker (imagen Playwright oficial)
- **Storage:** DynamoDB (historial + baselines), S3 (screenshots), Secrets Manager (credenciales)
- **Infra-as-code:** AWS CDK (Python)

---

## Decisiones de diseño no obvias

- **Catálogo cerrado de flows.** Solo `checkout_full` y `checkout_card_declined` en MVP. El LLM traduce NL a un config que solo puede referenciar estos flows — reduce la tasa de error del LLM de ~20% a casi cero.
- **Validación estricta antes de ejecutar.** Todo `SyntheticUserConfig` se valida contra JSON Schema antes de levantar un solo browser. Config inválido = rechazo inmediato.
- **Cero contaminación.** El método de pago siempre falla en el paso final (no se crean órdenes reales). Los usuarios sintéticos siempre usan email `@testpilot.internal`. Es un invariante del sistema, no una configuración.
- **Screenshots solo en fallo + paso final.** Capturar en cada paso costaría ~17 GB/mes en S3; con esta restricción son ~500 MB/mes.
- **Período de bootstrap (14 ejecuciones).** El semáforo no emite alertas amarillas hasta tener 14 runs exitosos en DynamoDB. Sin baseline suficiente no hay p95 confiable.
- **Thresholds p95, no porcentajes fijos.** El baseline compara contra el percentil 95 de las últimas 10 ejecuciones, no contra un margen arbitrario.
- **API versionable desde el día 1.** Cualquier cambio de campo en el contrato de `/v1/run` es breaking. El schema vive en `specs/` y se valida estrictamente.

---

## Estructura del repositorio

```
src/
├── api/          ← FastAPI app, endpoint /v1/run, schemas de entrada/salida
├── agents/       ← Traducción NL → SyntheticUserConfig via Claude API
├── executor/
│   ├── flows/    ← Un archivo por flow (checkout_full.py, checkout_card_declined.py)
│   ├── profiles/ ← Perfiles sintéticos (mobile_co.py, desktop_co.py, desktop_ec.py)
│   └── selectors.py  ← Selectores SFCC centralizados
├── reporter/     ← Generación de reporte JSON + Markdown + semáforo
├── baseline/     ← DynamoDB: escritura, lectura, cálculo p95, bootstrap guard
└── classifier/   ← Clasificación de errores via Claude API

specs/            ← JSON Schemas (contrato de la API)
infra/            ← AWS CDK stacks
tests/            ← Unitarios e integración (pytest)
docs/             ← PRD, ICP, PVB, deep research
```

---

## Estado actual

**Fase:** diseño/requisitos completada dentro del programa Hardcore AI Cohorte 2. Iniciando implementación del MVP.

**Timeline:**
- Semana 4 → ciclo de QA <30 min funcionando end-to-end
- Semana 12 → gate automatizado de deploy (auto-approve en verde)

---

## Alcance del MVP

**En alcance:**
- Dashboard interno con 2 pantallas (registro de ambientes + lanzamiento + historial)
- 3 ambientes soportados: sandbox, development, staging
- Credenciales separadas en Secrets Manager: `env_access_credentials` (gate del ambiente) + `shopper_credentials` (usuario shopper que ejecuta el checkout)
- 3 perfiles sintéticos × 2 flujos
- Reporte JSON + Markdown + semáforo (verde / amarillo / rojo)
- Historial en DynamoDB con baseline p95
- Screenshots en S3 nombrados por `run_id/perfil/flujo/paso`

**Fuera de alcance (post-MVP):**
- Auto-reparación de selectores rotos con IA
- Flujos de devolución o registro de nuevos usuarios
- Integración automática con CI/CD pipeline
- Comportamiento cognitivo complejo de perfiles (scroll, hover, tiempo de decisión)
- Benchmarking de competidores via scraping (viola ToS)
- Monitor continuo en producción (solo staging en MVP)

---

## Riesgos principales

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Anti-bot (Akamai/Cloudflare) bloquea Playwright | Alta | Excepción de IP para el rango de ECS, configurada antes de empezar |
| Selectores SFCC se rompen con cada deploy de cartridge | Alta | Preferir `data-cmp`/`data-testid`; centralizar en `selectors.py`; auto-reparación LLM post-MVP |
| Ambiente de staging sin datos de prueba | Media | Dataset mínimo definido como prerrequisito (5 productos, 1 tarjeta, 1 cliente) |
| LLM genera configs incorrectas | Media | JSON Schema estricto + catálogo cerrado de flows + logging de instrucción + config |
| Costos de ECS + S3 + DynamoDB escalan | Baja | Cap de 10 runs/día en MVP; revisión de costos en semana 2 |
| Adopción post-curso | Media | Integrar el trigger en el proceso de deploy existente |

---

## Documentación

Para una lectura saludable, empieza por [`docs/README.md`](./docs/README.md). Ese mapa separa fuentes canónicas, artefactos derivados de estaciones, investigación y documentos históricos.

| Necesitas... | Lee primero |
|---|---|
| Entender el producto y sus invariantes | [`PRODUCT.md`](./PRODUCT.md) |
| Implementar o revisar código con agentes | [`AGENTS.md`](./AGENTS.md) |
| Revisar UI, tono visual o reportes renderizados | [`DESIGN.md`](./DESIGN.md) |
| Validar contratos API | [`specs/`](./specs/) |
| Navegar investigación, PRD y artefactos de estaciones | [`docs/README.md`](./docs/README.md) |
| Revisar trazabilidad AI-DLC | [`aidlc-docs/README.md`](./aidlc-docs/README.md) |

---

## Equipo

**Autor:** Christian Díaz · [cdiaz@pash.com.co](mailto:cdiaz@pash.com.co)
**Equipo:** PASH — Ingeniería (3–7 personas, ≥2 deploys/mes de storefronts SFCC en LatAm)
**Programa:** Hardcore AI Cohorte 2

---

*Última actualización: 2026-05-27*
