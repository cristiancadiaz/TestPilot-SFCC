# PRODUCT.md — TestPilot SFCC

> Memoria de producto canónica. Da **criterio**: para quién es, qué resuelve, qué tono tiene y qué decisiones de producto son no negociables. El diseño visual vive en [`DESIGN.md`](./DESIGN.md); la arquitectura técnica en [`AGENTS.md`](./AGENTS.md) y [`README.md`](./README.md).
>
> Mantenido por el playbook `sfcc-product-owner` (`.ai/agents/`). Actualizar cuando cambie audiencia, propósito, alcance o tono.

---

> ⚠️ **Realineación de alcance en curso** (2026-06-02 · branch `rework/storefront-audit-scope`). La **sección 1 (Objetivo) ya refleja el alcance redefinido**. Las secciones 2–8 todavía describen el alcance anterior (acotado a checkout) y se actualizan en los pasos siguientes del cascade — ver [`aidlc-docs/inception/scope-realignment-brief.md`](./aidlc-docs/inception/scope-realignment-brief.md).

## 1. Qué es

**Objetivo.** TestPilot SFCC es una **plataforma interna de testing continuo con usuarios sintéticos** para storefronts Salesforce Commerce Cloud (SFRA) que permite a **cualquier miembro del equipo —técnico o no— lanzar una prueba describiendo en lenguaje natural lo que quiere validar**, y obtener dos entregables:

- **(a) Un veredicto de deploy-gate** — semáforo verde / amarillo / rojo en <30 min, consumible por un ingeniero o por otro agente del pipeline CI/CD.
- **(b) Un documento de auditoría** del **recorrido completo de la tienda** (búsqueda/PLP → PDP → carrito → checkout), generado por un agente que **sintetiza** (no juzga — el semáforo lo dicta una regla determinista) seis dimensiones, cada hallazgo enlazado a su evidencia:
  1. **Integridad de comercio** — consistencia de precios PLP/PDP/carrito, aplicación de promociones/descuentos, disponibilidad.
  2. **Rendimiento** — Core Web Vitals + waterfall de controllers SFRA (tiempos de respuesta).
  3. **Correctitud de locale** — moneda, idioma y formato por perfil (CO / EC).
  4. **Accesibilidad** — violaciones WCAG (axe-core).
  5. **Salud del cliente** — errores JS, requests fallidos, mixed content.
  6. **Integridad de contenido** — meta/SEO, imágenes rotas, `alt`.

**Reduce el ciclo de QA de 4–8 h manuales a <30 min de revisión.**

La **entrada principal es lenguaje natural** (traducida a una `SyntheticUserConfig` validada antes de ejecutar — el JSON estructurado queda como vía avanzada). Dos modos de operación: **gate** (determinista, reproducible, bloquea deploys) y **exploratorio** (agéntico, para descubrimiento; no entra al baseline).

> ✅ Secciones de audiencia (2), pantallas (7) y fuera-de-alcance (8) **actualizadas** (2026-06-02): usuarios no-técnicos, ventana NL y documento de auditoría.

## 2. Para quién es (audiencia)

Cuatro consumidores, en orden de poder de decisión:

| Persona | Rol | Qué necesita de la UI |
| :--- | :--- | :--- |
| **Tech Lead / Gerente de Tecnología** | Sponsor y decisor. Veta la adopción. | Veredicto accionable en <10 min, sin excavar 50 screenshots. Confianza para deployar. |
| **Ingeniero del equipo** | Usuario diario. Hace deploys y fixes. | Qué se rompió, **dónde** (URL, paso, screenshot, error) e historial comparable de performance. |
| **Otros agentes / CI/CD** | Consumidor indirecto vía API. | JSON con schema estable y versionado, latencia acotada, semáforo legible por máquina. |
| **Miembro no-técnico (QA, PM, negocio)** | Usuario nuevo, vía **ventana de lenguaje natural**. | Describir la prueba en español y leer el documento de auditoría, sin escribir JSON ni conocer la API. |

**Explícitamente NO es para:** público externo, marketing, ni demos comerciales. Es una herramienta operativa de ingeniería. Detalle completo en [`docs/product/icp.md`](./docs/product/icp.md).

## 3. Propósito y valor

- **Problema:** los storefronts SFCC del equipo no tienen testing automatizado; cada release se valida a mano (4–8 h) y las regresiones de performance son invisibles hasta que negocio reporta caída de conversión.
- **Promesa:** criterio objetivo de "listo para producción" + historial de performance defendible ante negocio.
- **Métrica que mata el producto:** no es la accuracy del clasificador — es **cuántos reportes el ingeniero lee con atención** antes de aprender a ignorarlo. Si cae bajo 50%, el producto está muerto. → La UI existe para que el reporte **se lea**, no para verse bonita.

## 4. Tono y voz

- **Senior, denso en señal, cero marketing.** Suena a ingeniero que reporta a otro ingeniero, no a brochure.
- **Verdad incómoda sobre adorno.** Mostrar el dato crudo (p95, HTTP code, paso exacto) antes que una visualización decorativa.
- **Español neutro LatAm** en la UI; identificadores técnicos y nombres de campo en inglés (`run_id`, `checkout_full`).
- **El semáforo no exagera.** Verde no es celebración, rojo no es alarma dramática. Son estados de un gate.

## 5. Principios de producto

1. **El veredicto primero.** La pantalla de resultados abre con el semáforo y el "qué hacer", no con tablas. Todo lo demás es drill-down.
2. **Un reporte, dos lectores.** El mismo run sirve al humano (Markdown + UI) y al agente (JSON versionado). Nunca divergen en contenido.
3. **Trazabilidad sobre opinión.** Cada hallazgo enlaza a evidencia (screenshot, URL, paso, error). Sin evidencia no hay hallazgo.
4. **Silencio honesto.** Durante el bootstrap (primeras 14 runs exitosas) no se inventan alertas amarillas: la UI dice "calibrando baseline", no finge confianza.
5. **El costo es visible.** Cap de 10 runs/día; la UI muestra cuántas quedan. Nada de uso ilimitado implícito.

## 6. Decisiones de producto no negociables (invariantes)

Estas son **producto**, no configuración. La UI nunca debe ofrecer una opción que las viole:

1. **Cero contaminación.** El pago siempre falla en el paso final — no se crean órdenes reales. Emails sintéticos siempre `@testpilot.internal`.
2. **Catálogo cerrado de flows.** Solo `checkout_full` y `checkout_card_declined` en MVP. El usuario elige del catálogo; no escribe flows libres.
3. **JSON Schema gate.** Todo `SyntheticUserConfig` se valida contra [`specs/`](./specs/) antes de lanzar un browser. Config inválido = rechazo inmediato con error descriptivo en la UI.
4. **Bootstrap silencioso.** Sin alertas amarillas hasta 14 runs exitosos.
5. **Thresholds p95, no porcentajes fijos.** SFCC tiene alta varianza natural; márgenes fijos generan ruido.
6. **Screenshots solo en fallo + paso final.** La UI muestra evidencia, no un álbum.
7. **API versionable.** Cualquier cambio de campo en `/v1/run` es breaking → sube a `/v2`.

## 7. Pantallas del MVP

| Pantalla | Propósito | Estado de éxito |
| :--- | :--- | :--- |
| **Ambientes** | Registrar/listar ambientes (sandbox, development, staging) y sus credenciales (en Secrets Manager, nunca en el payload). | El ingeniero registra un ambiente sin tocar AWS a mano. |
| **Lanzar + Historial** | **Describir la prueba en lenguaje natural** (o JSON avanzado) y lanzarla; ver resultado en vivo (vista matriz perfiles × flows, **genérica sobre flows**), el **documento de auditoría** y el historial con baseline p95. | El veredicto se entiende en <10 min, el documento de auditoría es legible para no-técnicos, y el historial muestra deriva de performance. |

Detalle de layout, tokens y componentes en [`DESIGN.md`](./DESIGN.md).

## 8. Fuera de alcance (producto)

Auto-reparación de selectores con IA · flujos de devolución/registro · integración CI/CD automática · comportamiento cognitivo de perfiles · benchmarking de competidores · monitor continuo en producción · dashboard analítico (Grafana/sparklines/anomaly detection). Ver [`README.md`](./README.md#alcance-del-mvp).

> **Realineado 2026-06-02:** **sí entran** al producto (en olas posteriores, **no recortables**): recorrido completo de tienda, documento de auditoría de 6 dimensiones, ventana de lenguaje natural y captura de red. Los ítems de arriba siguen fuera por **decisión de producto** (no por recorte de tiempo).

## 9. Cómo se usa este documento

- **`sfcc-product-owner`** lo lee antes de redactar cualquier feature scope o historia de usuario.
- **`design-steward`** lo lee antes de tocar `DESIGN.md`, slides o cualquier UI: el criterio de aquí restringe las decisiones visuales de allá.
- Un cambio de audiencia, propósito o invariante aquí **obliga** a revisar `DESIGN.md` y los specs.

---

*TestPilot SFCC — Hardcore AI Cohorte 2. Última actualización: 2026-06-02 (realineación de alcance — Paso 1: objetivo).*
