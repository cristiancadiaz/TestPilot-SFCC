# Brief de Realineación de Alcance — TestPilot SFCC

> **Estado:** BORRADOR para revisión humana (HITL) · **Branch:** `rework/storefront-audit-scope`
> **Fecha:** 2026-06-02 · **Autor:** Christian Díaz (con Claude Code)
> **Naturaleza del cambio:** reorganización de alcance ANTES de iniciar desarrollo de código.

---

## 1. Por qué existe este documento

Durante la revisión del alcance se detectó que la **visión original del producto** (en
`docs/product/pvb.md` y `docs/product/prd.md`) era **más amplia** que el alcance
que quedó en la capa de inception (`requirements.md`, `coverage-matrix.md`).

La fase de inception **recortó deliberadamente** la visión para entregar un MVP en 4 semanas:

| Visión original (PRD/PVB) | Recorte de inception | Decisión |
|---|---|---|
| Flujos críticos = login → **búsqueda → PDP → carrito** → checkout | Búsqueda/PDP/carrito degradados a *pasos* dentro de 2 flows de checkout | D8 + unit-of-work |
| MD2 con **clasificador + generador de resumen** | Clasificador descartado del MVP | D7 (J4 aplazado) |
| Entrada por instrucción NL (traductor) | Payload estructurado; traductor opcional | D8 |
| Screenshots de **todos los módulos** OK+FAIL (~17 GB) | Solo fallo + paso final (~500 MB) | ADR-002 / C7 revisado |

**El recorte no fue un error** — fue una serie de decisiones de des-riesgo razonables para una
demo de 4 semanas. Pero la ambición real del producto es la del PRD. Este brief **realinea
inception de vuelta con producto**, de forma deliberada y trazable.

---

## 2. Idea principal redefinida

> **Fuente canónica del objetivo: [`PRODUCT.md`](../../PRODUCT.md) §1.** Esta sección lo resume; si divergen, gana `PRODUCT.md`.

TestPilot SFCC permite a **cualquier miembro del equipo —técnico o no— lanzar una prueba
describiendo en lenguaje natural lo que quiere validar** sobre una tienda SFCC, y obtener:

- **(a) un veredicto de deploy-gate** (semáforo verde/amarillo/rojo, <30 min, consumible por
  humanos y agentes CI/CD), y
- **(b) un documento de auditoría** del recorrido completo (búsqueda/PLP → PDP → carrito →
  checkout) que **sintetiza** (no juzga) seis dimensiones con evidencia enlazada: integridad de
  comercio, rendimiento, correctitud de locale, accesibilidad, salud del cliente e integridad de
  contenido.

Todo **sin contaminar datos reales**. Cambia el centro de gravedad de *"smoke test de checkout"*
a *"auditoría de recorrido de tienda con gate de deploy"* — que es lo que el PRD siempre planteó.

**Estado (2026-06-02):** objetivo FIJADO en `PRODUCT.md` §1 (Paso 1 del cascade). Modos de
operación **gate** (determinista) y **exploratorio** (agéntico) definidos. Las 6 dimensiones de
auditoría son núcleo (confirmadas por el equipo).

---

## 3. Alcance en 3 cubos

### 3.1 RESTAURAR (estaba en PRD, lo recortó inception)

- **R1. Flujos de recorrido completo** como pruebas propias, no solo pasos del checkout:
  navegación de catálogo/PLP (incl. **productos con descuento**), PDP, carrito. Catálogo de
  flows **sigue cerrado**, solo crece de forma curada.
- **R2. Agente de auditoría** = el "Generador de Resumen" (MD2/SUMM) + clasificación de
  hallazgos. **Restricción de diseño:** el agente **sintetiza y redacta** sobre datos
  deterministas; **NO decide** verde/amarillo/rojo (eso sigue siendo regla determinista — respeta
  el racional de D7/P4 y evita re-introducir el riesgo de falsos juicios del LLM).

### 3.2 NUEVO (no estaba en el PRD original)

- **N1. Tiempos de respuesta de APIs / captura de red.** Factible vía captura de tráfico de
  Playwright (estilo HAR) — *user-perceived + network timing*, NO APM de backend. Requiere
  campos nuevos en `execution_report.schema.json`.

### 3.3 YA EN SCOPE (solo construir bien)

- **Y1. Dashboard matriz** (filas = perfiles/agentes, columnas = flows) con vista en tiempo
  real (MD0, ya Must Have). **Restricción:** renderizar flows de forma **genérica** — sin
  hardcodear "checkout" ni asumir exactamente 2 flows.

---

## 4. Decisiones de inception a revisar

| Decisión | Estado actual | Acción propuesta |
|---|---|---|
| **D7** (clasificador descartado) | Sin clasificador en MVP | Restaurar como **agente de síntesis** (no juez); des-aplazar J4 parcialmente |
| **D8** (entrada estructurada) | Payload estructurado, NL opcional | Mantener; el agente de auditoría es salida, no entrada |
| **ADR-002 / C7** (screenshots) | Solo fallo + paso final | Revisar: ¿el documento de auditoría necesita más evidencia visual? Cuidar cost cap |
| **Catálogo cerrado de flows** (invariante #2) | 2 flows checkout | Mantener cerrado; crecer curado (browse/PLP/PDP/cart) |

---

## 5. Frontera del MVP — DECIDIDO (2026-06-02)

**Decisión del equipo:** el **alcance es fijo — ningún módulo se recorta**. La variable de ajuste
es el **tiempo**, no el scope. Todos los módulos (recorrido completo, agente de auditoría, ventana
NL, dashboard genérico, 6 dimensiones de auditoría) se construyen aunque el desarrollo se extienda
más allá de las 4 semanas.

- **Entrega incremental por valor/riesgo:** se prioriza para mostrar avance temprano (p.ej.
  checkout + dashboard genérico primero), pero lo diferido **se construye después — no se elimina**.
- **Demo Day (9-jun) es fecha fija:** muestra lo que esté listo a esa fecha; el producto **no se
  poda** para caber en la demo.
- En la práctica = el incrementalismo de la antigua Opción A + el alcance completo de la Opción B,
  con el **tiempo como variable de ajuste** (no el alcance).

---

## 6. Plan de cascade — documentos a actualizar (en orden de dependencia)

El orden sigue la **cronología de las estaciones** (lo primero generado se actualiza primero): research (E1) → producto (E2) → inception (E4) → construcción (E5) → arnés.

| # | Capa (Estación) | Documento | Cambio |
|---|---|---|---|
| 0 | Producto | `PRODUCT.md` §1 (objetivo) | ✅ HECHO — objetivo fijado (Paso 1) + rename `prd-2026-05-22.md`→`prd.md` |
| 1 | Research (E1) | `docs/research/*` | Notas de vigencia apuntando al objetivo nuevo; revisar framing de scope en `hcai-c2-internal-solution-brief.md`. **NO reescribir evidencia/casos** (mercado, deep-research, crítica son insumos citados) |
| 2 | Producto (E2) | `docs/product/pvb.md` | Tesis "auditoría de recorrido" + usuarios no-técnicos |
| 3 | Producto (E2) | `docs/product/icp.md` | Ampliar audiencia a no-técnicos (QA/PM/negocio) |
| 4 | Producto (E2) | `docs/product/prd.md` | Reactivar MD2 clasificador/resumen; flows de recorrido; timings API; ventana NL |
| 5 | Producto (E2) | `PRODUCT.md` (secciones 2/7/8) | Audiencia, pantallas, fuera-de-alcance |
| 6 | Inception (E4) | `requirements/requirements.md` | RFs nuevos; revisar D6/D7/D8 |
| 7 | Inception (E4) | `user-stories.md` + `coverage-matrix.md` | Historias nuevas; des-aplazar J4; MoSCoW |
| 8 | Inception (E4) | `application-design/unit-of-work.md` | Unidades U5 (browse-flows), U6 (audit-agent), U7 (network-capture) |
| 9 | **Contratos (breaking, HITL)** | `specs/synthetic-user-config.schema.json` + `execution_report.schema.json` | `product_selection`, enums/maxItems de flows, campos de auditoría; bump versión |
| 10 | Construcción (E5) | `aidlc-docs/construction/plans/*` | Planes de unidades nuevas |
| 11 | **Estado AI-DLC** | `aidlc-docs/aidlc-state.md` + `audit.md` | Regreso Construction→Inception; log del proceso + del rename del PRD |
| 12 | Arnés | `CLAUDE.md` + `AGENTS.md` + `docs/arquitectura/matriz-tecnologia-fase.md` | Data flow, boundaries, invariantes, tech nueva (HAR, axe-core, agente síntesis) |

**Nota de flujo AI-DLC:** este cambio implica que el proyecto **regresa a la fase de Inception**
(Requirements Analysis) desde Construction. El `leader` debe orquestar la re-entrada, pasar por
las puertas HITL, y registrar todo en `audit.md`. Ningún contrato (`specs/`) se toca sin
confirmación humana explícita.

---

## 7. Decisiones abiertas que requieren tu confirmación

1. ~~**Frontera del MVP:** ¿Opción A u Opción B?~~ → **RESUELTO (2026-06-02):** alcance fijo, ningún módulo se recorta; el **tiempo** es la variable de ajuste (ver §5).
2. **Alcance de los flujos de recorrido:** ¿cuáles entran al catálogo? (p.ej. `browse_discounted_products`, `search_and_filter`, `pdp_validation`, `cart_review`)
3. **Agente de auditoría:** ¿síntesis-sobre-datos-deterministas (recomendado) o clasificador que juzga?
4. **Tiempos de API:** ¿captura de red vía Playwright (in) o fuera de este alcance?
5. **Screenshots:** ¿se mantiene fallo+final, o el documento de auditoría justifica más evidencia (revisando cost cap)?

---

## 8. Estado de avance (resume point)

> **Branch:** `rework/storefront-audit-scope` · **Última sesión:** 2026-06-02

**Hecho y commiteado** (5 commits `fe4f344`..`9867c84`, sin push):

- ✅ Paso 1 — Objetivo fijado (`PRODUCT.md` §1)
- ✅ E1 — Research (notas de vigencia)
- ✅ E2 — Producto (`pvb.md`, `icp.md`, `prd.md` [renombrado desde `prd-2026-05-22.md`], `PRODUCT.md`)

**Próximo paso → E4 Inception:** `requirements/requirements.md` (tarea #3) → historias + `coverage-matrix.md` (#4) → `unit-of-work.md` (#5). Luego: contratos `specs/` (HITL, #6), construcción (#7), estado AI-DLC + `audit.md` (#8), arnés `CLAUDE.md`/`AGENTS.md` + matriz (#9). Tracking vivo en la task list de la sesión.

**Decisiones (§7) ya reflejadas en los docs:** #1 alcance fijo · #3 agente sintetiza-no-juzga (P7) · #4 captura de red IN (M22). **Aún abiertas:** #2 (cuáles flows de recorrido entran al catálogo) y #5 (evidencia/screenshots para el documento de auditoría).

**Sin commitear (no relacionado con la realineación):** `docs/conceptos/*`, `docs/tasks/linear-publish.yaml`.
