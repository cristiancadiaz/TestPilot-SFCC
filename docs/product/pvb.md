# Product Vision Board — Plataforma de Testing Continuo con Usuarios Sintéticos

> **Producto:** Plataforma de Testing Continuo con Usuarios Sintéticos para SFCC
> **Cohorte:** Hardcore AI by 30X — Cohorte 2
> **Demo Day:** 9 de junio de 2026
> **Autor:** Christian

---

> ⚠️ **Realineado 2026-06-02** (branch `rework/storefront-audit-scope`). Este Vision Board refleja el **alcance redefinido**: recorrido completo de tienda + documento de auditoría (6 dimensiones) + ventana de lenguaje natural para usuarios no-técnicos. Objetivo canónico en [`PRODUCT.md`](../../PRODUCT.md) §1; racional en [`aidlc-docs/inception/scope-realignment-brief.md`](../../aidlc-docs/inception/scope-realignment-brief.md).

## PRODUCTO

**Nombre del producto:** SyntheticQA (working title)

**Descripción en una línea:** Plataforma interna donde **cualquier miembro del equipo —técnico o no— describe en lenguaje natural una prueba**, y un agente ejecuta el **recorrido completo de la tienda SFCC** (búsqueda → PDP → carrito → checkout) con usuarios sintéticos en varios perfiles, devolviendo **(a)** un **semáforo de deploy-gate** y **(b)** un **documento de auditoría** de 6 dimensiones (integridad de comercio, rendimiento, locale, accesibilidad, salud del cliente, contenido) — consumible por humanos y por otros agentes del ecosistema CI/CD.

**Tagline interno:** _"QA manual que se hace solo, mientras tomás un café."_

---

## 1. PROBLEMA

### Problema que resuelvo

Los equipos SFCC validan cada release con QA manual. Un ingeniero senior navega checkout, búsqueda y PDP en distintos dispositivos —entre 4 y 8 horas de trabajo por release— para confirmar que nada se rompió. No hay baseline histórico de performance, no hay criterios objetivos de "listo para producción", y las regresiones de performance pasan invisibles hasta que el equipo de negocio reporta caída de conversión semanas después.

**Cifras concretas del dolor:**

- **4–8 horas por release** de QA manual ($300–800 USD en horas-ingeniería senior).
- A 4 releases/mes: **$1,200–$3,200 USD/mes** en QA repetitivo.
- **Bugs en producción cuestan 15–30x más** que detectados pre-release (IBM, 2023). Un bug de checkout en pico de tráfico puede costar **$15K–$50K USD** en revenue perdido para una tienda con 1K órdenes/mes.
- **4.42% de caída en conversión por cada segundo adicional** de carga en mobile (Google/SOASTA). Una regresión no detectada de 2.1s → 3.4s durante 2 semanas puede costar **8–9% en conversión perdida**.

### ¿Sobrevive al próximo salto de modelos?

**[X] Sí, porque es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT**

El próximo modelo foundation (Opus 5, Gemini 4) será mejor entendiendo screenshots y navegando UI — eso **acelera** el producto, no lo invalida. Lo que no resuelve un modelo más inteligente:

- El cliente sigue necesitando que la plataforma se integre con su pipeline existente.
- El ground truth de errores específicos de la tienda sigue siendo input humano.
- El reporte estructurado que otros agentes consumen sigue siendo trabajo de schema design.
- El semáforo verde/amarillo/rojo sigue siendo decisión de producto, no de modelo.

**Durability Score: 4/5**

(Pierde 1 punto: si Salesforce extiende Agentforce Testing Center a SFCC, una parte significativa del wedge SFCC-specific se erosiona.)

---

## 2. SEGMENTO TARGET

### ¿Para quién es este producto?

**Beachhead (primeras 4 semanas):** El equipo de PASH operando tiendas SFCC propias y de clientes. Específicamente:

1. **Implementadores SFCC LatAm operando tiendas propias o de clientes** — agencias certificadas con equipos de 3–8 ingenieros. Beachhead inmediato = PASH.
2. **Retailers mid-market con SFCC in-house** — equipos digitales con 500–10K órdenes/mes y Tech Lead responsable de QA pre-release.
3. **Otros agentes/sistemas AI del ecosistema interno** — CI/CD pipelines, agentes de code review, dashboards operativos que consumen el JSON estructurado.
4. **Miembros no-técnicos del equipo interno (QA, PM, negocio)** — gracias a la **ventana de lenguaje natural**, lanzan pruebas describiendo en español lo que quieren validar, sin escribir JSON ni conocer la API. Amplía el uso más allá de los ingenieros y multiplica quién puede pedir una auditoría antes de un deploy.

**NO es para:** tiendas Shopify/Magento/VTEX/WooCommerce (la especialización SFCC es el wedge), retailers Tier 1 con Mabl/Testim ya contratados, equipos con ≤1 deploy/mes, tiendas sin staging aislado.

### ¿Quién controla el veto de confianza?

Dos perfiles, en orden de poder:

1. **Tech Lead / Gerente de Tecnología (sponsor + decisor).** Mata la adopción si los falsos positivos superan 20%, si el reporte no es accionable en <10 min, o si la infra cuesta >$200/mes. En PASH es el sponsor directo del proyecto.
2. **DevOps / Seguridad del cliente final (bloqueador operativo).** Mata la adopción si no aprueba la excepción de IP en Akamai/Cloudflare. Sin esta excepción el sistema entrega falsos verdes.

**Implicación:** las primeras 4 semanas se ejecutan sobre **tiendas operadas por PASH** donde el sponsor y el aprobador de IP están en la misma organización. La expansión a clientes terceros depende de demostrar valor primero internamente.

---

## 3. MOAT PRIMARIO

**[X] Trust Moat (especialización SFCC + ground truth)**

### ¿Qué trust única poseemos o podemos construir?

Tres capas acumulables:

1. **Catálogo de selectores SFCC validados** — `data-cmp` y `data-testid` documentados por componente (PDP, cart, checkout, login, search). Esto se construye una vez por cartridge custom y se reutiliza en cada tienda. **No replicable comprando Mabl** — Mabl no sabe qué `data-cmp` usa PASH.
2. **Ground truth de errores esperados vs reales** — biblioteca documentada de "este timeout de 30s es normal en sincronización de inventario, este HTTP 503 en horario X es esperado por mantenimiento". Esto requiere meses de operación real para calibrar. Es **el moat que más tarda en construirse y el más difícil de replicar**.
3. **Integraciones nativas con gateways LatAm** — Wompi, ePayco, MercadoPago, PSE. Los flujos de checkout con tarjeta rechazada/aprobada en cada gateway tienen sus particularidades. Mabl/Testim no entienden estos contextos sin trabajo custom.

**El moat real NO es el código** (replicable en 2–3 semanas con Playwright + Claude). **Es la red de selectores SFCC validados + el ground truth de errores específicos de cada tienda.** Eso solo se acumula operando.

---

## 4. ARENA COMPETITIVA

**[X] Replacement (Specialist niche)** — Reemplazamos la opción "Mabl/Testim para SFCC" + "QA manual" con una alternativa especializada que es más barata y más SFCC-aware.

### ¿Cómo sobrevives o complementas a los gigantes?

**Mabl, Testim, Functionize** ofrecen testing E2E genérico con cobertura buena pero **sin conocimiento SFCC ni LatAm**. Cuestan $3K–60K/año, requieren equipo dedicado para configurar, y no hablan español. Sirven a retailers enterprise globales. **No sirven** a mid-market LATAM con presupuesto limitado.

**Datadog Synthetics / Checkly** son synthetic _monitoring_ (cobertura continua en producción), no testing _pre-release_ con criterios de aceptación específicos.

**GitHub Actions + Playwright** es la alternativa "construye tú mismo": $1/mes pero requiere fin de semana de configuración + mantenimiento + diseño del reporte estructurado + integración LLM. Cubre la primitiva pero no el producto.

**Agentforce Testing Center (Salesforce)** — riesgo a 12 meses. Si Salesforce extiende a SFCC, este proyecto necesita pivotar a complementar (no competir).

**Posicionamiento defensible:** somos la **capa de testing SFCC-specific** que ningún player horizontal construirá porque el mercado SFCC LatAm es demasiado pequeño para justificar su atención. Para PASH es **capability embedded en propuestas comerciales** (parte del valor de "implementador SFCC moderno"), no producto vendible standalone.

---

## 5. UX PARADIGM

**[X] Autonomous con HITL controlado** — el sistema se ejecuta solo, el humano solo interviene en disputas o casos nuevos.

### ¿Por qué este paradigma?

El producto **es la ausencia del humano en el ciclo de QA pre-release**. Si el ingeniero tiene que mirar cada ejecución, ya no estamos ahorrando 4–8h por release. La autonomía es la propuesta de valor.

**Humano-en-el-loop SOLO en:**

- Primera vez que un selector falla en producción → el ingeniero marca el nuevo selector y la herramienta lo persiste.
- Hallazgos marcados "amarillo" (degradación detectada) → ingeniero decide si bloquea deploy o no.
- Ground truth update → cuando aparece un nuevo error que no estaba clasificado, el equipo decide la categoría.

**Todo lo demás:** disparador automático post-commit → ejecución de flujos → clasificación de hallazgos → reporte estructurado → semáforo. **Tiempo target end-to-end: <10 minutos** entre commit y reporte legible.

**Entrada por lenguaje natural (nuevo):** el usuario —técnico o no— describe la prueba en español; el sistema la traduce a una `SyntheticUserConfig` **validada antes de ejecutar** (sin esto, no abre browser). Dos modos de operación:

- **Gate** — determinista y reproducible; es el que bloquea deploys y alimenta el baseline p95.
- **Exploratorio** — el agente improvisa desde la descripción libre para descubrir/QA exploratorio; **no** bloquea deploys ni entra al baseline (evita contaminar la reproducibilidad del gate).

---

## 6. AI DECISION TRIANGLE

**[X] Speed**

### Trade-offs que acepto

- **Agente de auditoría como síntesis, no juez:** uso Claude Haiku 4.5 o Sonnet 4.6 para sintetizar el documento de auditoría (rendimiento, hallazgos, evidencia) de forma rápida. Casos ambiguos suben a Opus, pero son <5% del volumen. El agente **redacta y categoriza, NO decide** rojo/amarillo/verde — eso lo dicta una regla determinista sobre datos de Playwright + baseline.
- **Cobertura curada, no infinita:** la visión cubre el **recorrido completo** (búsqueda → PDP → carrito → checkout) auditado en 6 dimensiones, pero con **catálogo cerrado** de flows (curados, no arbitrarios) y entregado **incrementalmente** — no 10 flujos libres de golpe.
- **Sacrifico fidelidad de mediciones de performance:** mido p50/p95 sobre 3 ejecuciones para reducir ruido, no busco precisión sub-segundo.
- **Sacrifico features de UI avanzadas:** el dashboard MVP es funcional (lanzar prueba + ver resultados + historial), no analítico. Grafana, sparklines, comparaciones visuales entre runs y anomaly detection quedan fuera del MVP. El dashboard básico SÍ está en scope.

**Razón de fondo:** el reporte llega rápido o el ingeniero deja de esperarlo. El estudio del propio brief: ciclo de QA debe bajar de 4–8 horas a <30 minutos para que el cambio sea perceptible. La latencia del agente importa más que la perfección del clasificador.

---

## 7. MODELO ECONÓMICO

**Modelo:** Para uso interno PASH = **costo-evitado** sobre QA manual. Para clientes externos = **flat por tienda/mes**.

### Costos de infraestructura

| Componente                                         | Costo estimado/mes |
| -------------------------------------------------- | ------------------ |
| ECS Fargate (Playwright, 1 vCPU 2GB, 30 min/día)   | ~$15               |
| Step Functions + Lambda triggers                   | <$1                |
| S3 (screenshots solo en error, ~2GB/mes)           | <$0.10             |
| DynamoDB (histórico de ejecuciones)                | <$1                |
| Claude API (clasificación, ~1K llamadas/mes Haiku) | ~$5                |
| Secrets Manager + CloudWatch logs                  | <$2                |
| **Total infra por tienda**                         | **~$25/mes**       |

### Modelo de pricing (si se ofrece a clientes externos)

- **Plan starter:** $99/tienda/mes — incluye 2 flujos, 1 perfil, 4 ejecuciones/día.
- **Plan growth:** $299/tienda/mes — 5 flujos, 3 perfiles, 24 ejecuciones/día, historial 90 días.
- **Plan agencia:** flat $999/mes para hasta 10 tiendas operadas por el mismo equipo.

### ¿Escala a 10x usuarios? **[X] Sí**

El costo marginal por tienda es ~$25/mes. Cada tienda adicional aporta ~$74–274/mes de margen. El cuello de botella NO es infra — es **mantenimiento de selectores**: cada cartridge nuevo añade horas semanales. La economía se rompe si el mantenimiento crece linealmente con tiendas.

### Economía interna PASH

| Métrica                                                          | Valor                |
| ---------------------------------------------------------------- | -------------------- |
| Costo de QA manual por release (1 ingeniero senior, 6h promedio) | ~$500                |
| Costo de infra del agente por mes                                | ~$25                 |
| Reducción en QA manual a 30 min/release                          | ahorro ~$425/release |
| Break-even por tienda                                            | **<1 release/mes**   |

**Lectura:** internamente, el producto se paga con el primer release ahorrado. Para clientes externos, la economía funciona a partir de 2 tiendas operadas por el mismo equipo.

---

## 8. MÉTRICAS DE ÉXITO

### Métricas de usuario

1. **Tiempo de ciclo QA por release** — meta semana 4: **<30 min** revisión de reporte (vs 4–8h manual).
2. **% de releases que pasan sin re-validación manual** — meta semana 4: **>70%** para flujos cubiertos.

### Métricas específicas de AI

1. **Tasa de falsos positivos del clasificador** — meta: **<15%** (medida manualmente sobre 50 hallazgos en semana 3–4 con ground truth).
2. **Tasa de hallazgos accionables** — % de hallazgos que el ingeniero confirma como bug/regresión real. Meta: **>40%**.

### Métricas de salud técnica

- **Tiempo end-to-end (commit → reporte):** p50 <5 min, p95 <10 min.
- **Tasa de ejecuciones bloqueadas por Akamai/Cloudflare:** **0%** (precondición: excepción de IP).
- **Costo de infra/mes:** <$50 en MVP.

### Anti-métricas (lo que NO se mide)

- Número de tests automatizados (no es cobertura, es valor de cobertura).
- Screenshots almacenados (no es output, es ruido).
- Llamadas al LLM (no es uso, es costo).

---

## 9. RIESGOS CRÍTICOS

### 1. ¿Qué pasa si Salesforce extiende Agentforce Testing Center a SFCC?

**Riesgo medio-alto.** Salesforce lanzó Agentforce Testing Center para Service/Sales Cloud en 2024. Extender a SFCC es probable en 2026–2027 dado la prioridad estratégica del segmento Commerce.

**Mitigación:**

- Construir el moat en lo **no commoditizable**: ground truth de errores, integraciones gateway LatAm, conocimiento de cartridges PASH específicos.
- Posicionar como **complemento** a Agentforce, no competencia. La plataforma de PASH puede vivir encima si Salesforce hace bien la primitiva.
- Si Salesforce empaqueta una alternativa gratuita y suficientemente buena, **pivotar a servicios** (consultoría SFCC + testing como entregable) en lugar de producto.

### 2. ¿Selectores rotos paran la operación y el equipo abandona la herramienta?

**Riesgo alto.** 40–60% del mantenimiento de E2E es selectores. SFCC con cartridges custom hace esto peor. Sin auto-healing, cada cambio de cartridge puede romper flujos completos.

**Mitigación:**

- Usar exclusivamente `data-cmp` y `data-testid` semánticos en cartridges (estándar del equipo).
- Logging visible cuando un selector falla → backlog priorizable, no problema invisible.
- Post-MVP: agregar capa de auto-healing con Claude sugiriendo el nuevo selector candidato.
- **Acepto que sin esto, el proyecto tiene una vida útil de 8–12 semanas antes de degradar.**

### 3. ¿Qué pasa si el clasificador AI genera falsos positivos sostenidos y el equipo pierde confianza?

**Riesgo medio.** Sin ground truth, el clasificador no se puede medir. Falsos positivos sostenidos = el equipo deja de leer reportes.

**Mitigación:**

- El clasificador **no decide** — solo categoriza. La decisión rojo/amarillo/verde la dicta una regla determinista (HTTP code + presencia de elementos + diff de performance vs baseline).
- Loop de feedback: el ingeniero marca falsos positivos → se acumulan en una "exclusion list" del clasificador.
- Documentar ground truth desde la semana 1 — entregable, no riesgo.
- Si tasa de falsos positivos >20% en semana 3, **detener el rollout** y rediseñar criterios antes de extender a más flujos.

**Verdad incómoda:** la métrica que mata el producto no es la accuracy del clasificador. Es **cuántos reportes el ingeniero lee con atención** antes de aprender a ignorar la herramienta. Si esa métrica cae bajo 50%, el producto está muerto sin importar las métricas técnicas.

---

_Hardcore AI by 30X — Cohorte 2 — Estación 2 (mayo 2026). Realineado 2026-06-02 (alcance: recorrido completo + auditoría de 6 dimensiones + ventana NL) — objetivo canónico en `PRODUCT.md` §1._
