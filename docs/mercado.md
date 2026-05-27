# Análisis de mercado — Testing automatizado de e-commerce SFCC en LatAm

> Documento de contexto para la Plataforma de Testing Continuo con Usuarios Sintéticos.
> Fuente: Internal Solution Brief + Deep research de validación, mayo 2026.

---

## 1. Tamaño del mercado de testing automatizado

El mercado de **automated testing tools** es uno de los más maduros del software enterprise. La novedad no es el tamaño — es la **mezcla con AI**.

- **Mercado global de software testing 2025:** ~$50B (analytics agregadas: Gartner, MarketsAndMarkets, Mordor Intelligence). Subsegmento de **test automation:** ~$30B.
- **Subsegmento AI-augmented testing:** se reporta como categoría separada desde 2022. Proyección 2026: $2–3B; proyección 2030: $15–20B (Cognitive Market Research, Mordor Intelligence). *Estas cifras son aspiracionales y mezclan AI-augmented con synthetic monitoring tradicional.*
- **Synthetic monitoring puro (Datadog, New Relic, Checkly, Pingdom):** ~$1.5B en 2025, crecimiento 18–22% YoY.

> **Nota crítica:** Las proyecciones de "AI testing market" suelen inflar el TAM mezclando categorías. El sub-segmento real de **AI agents that drive browsers for testing** —el corazón de esta plataforma— es menor: probablemente $200–400M en 2026, dominado por Mabl, Testim, Functionize, KaneAI.

## 2. Adopción de testing automatizado en e-commerce

- **Equipos enterprise con CI/CD maduro:** ~70% reportan tener al menos suites E2E parciales (State of DevOps Report 2024, DORA).
- **Equipos mid-market e-commerce (1K–10K órdenes/mes):** ~30% tiene testing automatizado. La mayoría confía en testing manual pre-release.
- **Equipos LATAM:** la adopción está estimada **15–25% por debajo** de Norteamérica para mid-market. No hay encuesta dedicada con tamaño muestral significativo.
- **SFCC específicamente:** Salesforce no publica datos sobre adopción de testing automatizado en su base. La mayoría de implementaciones SFCC en LatAm son **operadas por agencias** (PASH, Globant, BBR, MagentoLATAM) que típicamente entregan con QA manual y dejan al cliente sin suite automatizada.

**Implicancia:** existe un floor de demanda no atendida en el mid-market e-commerce LATAM. La pregunta abierta es si están dispuestos a pagar o si lo construyen in-house.

## 3. Sizing del mercado SFCC en LatAm

Salesforce no publica número de tiendas activas por región, pero hay aproximaciones:

- **Salesforce Commerce Cloud globalmente:** ~3,500 brands en producción (Salesforce 10-K 2024, estimaciones BuiltWith).
- **LatAm SFCC:** estimación **150–300 tiendas activas** en producción, concentradas en Brasil, México, Colombia, Chile, Argentina. (BuiltWith + reportes de agencias certificadas Salesforce LatAm).
- **Tipos de marcas SFCC en LatAm:** retailers grandes (Falabella, Cencosud, Grupo Éxito, Liverpool), marcas internacionales con presencia regional (Adidas, Nike, L'Oréal, Kering), retailers especializados (Tiendas D1 marketplace, Tugó).
- **Implementadores SFCC LatAm:** ~15–25 agencias certificadas con práctica seria. PASH entre ellas.

**Sub-mercado de testing para SFCC LatAm:** orden de magnitud 50–150 tiendas que harían sentido económico para una herramienta especializada (las que tienen >500 órdenes/mes y >2 releases/mes). Esto es **un mercado pequeño** — viable como herramienta interna de una agencia, débil como producto comercial standalone.

## 4. Empresas relevantes en el ecosistema

### Players de testing globales con potencial uso en SFCC

| Empresa | Foco | Funding / scale | Aplicabilidad a SFCC |
|---|---|---|---|
| **Mabl** | E2E SaaS con auto-healing | $77M total | Funciona — pero no entiende SFCC específicamente |
| **Testim (Tricentis)** | E2E + AI selector healing | Parte de Tricentis | Suite enterprise; integra con cualquier UI |
| **KaneAI (LambdaTest)** | Test authoring con NL | Parte de LambdaTest | Genérico; no SFCC-aware |
| **Browserbase** | Browsers serverless para agentes | $40M Series A | Infra base, no producto |
| **Datadog Synthetics** | Synthetic monitoring | Datadog Inc. | Sirve, pero overkill y caro para mid-market |

> **Estas empresas NO son competencia directa de una plataforma interna PASH** — son herramientas que un equipo SFCC puede adoptar. Son posibles **build-vs-buy benchmarks** para el sponsor.

### Implementadores SFCC en LatAm

| Empresa | País principal | Notas |
|---|---|---|
| **PASH** | Colombia | Sponsor del proyecto. Construye sobre clientes propios. |
| **BBR.cl** | Chile | Agencia Salesforce certificada con foco SFCC. |
| **Globant** | Argentina / global | Gran implementador, equipo SFCC interno. |
| **Linio Tech / 4Geeks** | México / Centroamérica | Implementadores varios. |
| **Trii / Globalbit** | Brasil | Agencias SFCC certificadas. |

> Estos implementadores son **posibles partners de distribución**, no competidores. Cada uno tiene el mismo dolor: QA manual pre-release sin baseline histórico.

### Retailers SFCC LatAm grandes (clientes finales)

| Retailer | País | Volumen estimado | Notas |
|---|---|---|---|
| **Falabella** | Chile / Colombia / Perú | >1M órdenes/mes (regional) | SFCC core de su stack online. |
| **Cencosud** | Chile / Argentina / Colombia | >500K órdenes/mes | Multibrand, varias tiendas SFCC. |
| **Grupo Éxito** | Colombia | ~100K órdenes/mes | Implementación SFCC parcial. |
| **Liverpool / Suburbia** | México | >300K órdenes/mes | SFCC core. |
| **L'Oréal LatAm** | Regional | Tiendas DTC por marca | Múltiples sites SFCC. |
| **Adidas / Nike LatAm** | Regional | Tiendas DTC regionales | SFCC headless en transición. |

---

## 5. Marco regulatorio — el matiz crítico

El testing automatizado de tiendas propias no tiene fricción regulatoria significativa. El testing automatizado de **tiendas de terceros** (competidores) sí.

### Testing sobre tiendas propias (sponsor PASH y sus clientes)

- **No hay fricción regulatoria.** El equipo tiene autorización del owner de la tienda.
- **Sí hay fricción operativa:** Akamai Bot Manager y Cloudflare Bot Management activos en producción bloquean Playwright por defecto. **Requiere whitelist de IP de los rangos de ECS Fargate** antes de empezar.
- **Datos sintéticos vs reales:** los flujos de checkout no deben usar datos reales de clientes. Carrito-test, cliente-test, tarjeta-test deben configurarse en staging.

### Testing sobre competidores — fuera de alcance

- **Riesgo legal en Colombia:**
  - **Ley 1581 de 2012** (protección de datos personales) y decisiones de la **SIC** (Superintendencia de Industria y Comercio) sobre scraping. Si el agente captura datos de clientes durante navegación automatizada, hay exposición.
  - **Términos de servicio de e-commerce competidor:** la mayoría prohíbe explícitamente acceso automatizado. Violarlo no es delito penal pero sí causal de bloqueo permanente y posible reclamación civil.
- **Riesgo legal en México (LFPDPPP), Brasil (LGPD), Chile (Ley 19.628):** marco similar; scraping sin consentimiento es zona gris.
- **Recomendación:** explicitar en el alcance del MVP que el benchmarking de competidores **NO se ejecuta**. La excusa "es solo para uso interno" no protege ante un ToS violado.

### Datos de prueba y compliance interno

- Tarjetas de prueba (Wompi, ePayco, MercadoPago, Stripe LatAm) están explícitamente provisionadas por los gateway providers — su uso es legítimo.
- Datos de clientes sintéticos deben ser **completamente ficticios** (nombres inventados, emails de dominio @test.local, teléfonos +57000000000). Nunca usar datos de clientes reales aunque estén en staging.

---

## 6. Implicancia para esta plataforma

### Posicionamiento de mercado

Esta plataforma NO compite con Mabl ni Testim. Compite con **el script de QA manual que un ingeniero ejecuta antes de cada release**. El benchmark de "build vs buy" es:

| Opción | Costo año 1 | Pain principal |
|---|---|---|
| QA manual (status quo) | $0 cash, ~$30K en horas-ingeniería | No escala, sin baseline histórico |
| **Plataforma interna (este proyecto)** | **~$2K infra + 4 sem de dev** | **Mantenimiento de selectores SFCC, definir ground truth de errores** |
| Mabl / Testim SaaS | $15K–60K/año | No conoce SFCC, no nativo en español |
| Datadog Synthetics | $5K–25K/año | Synthetic monitoring, no testing pre-release |

**El wedge real para PASH:** ser la herramienta interna que **ningún SaaS horizontal sabe construir** porque no conocen los selectores SFCC específicos del equipo, los gateways de pago LatAm, ni los flujos típicos de release de cartridges.

### Orden de uso recomendado

1. **Fase 1 (mes 1, MVP):** Tiendas SFCC operadas directamente por PASH. Validar el flujo y construir el ground truth de errores esperados vs reales.
2. **Fase 2 (mes 2–3):** Onboarding a 1–2 clientes piloto de PASH con tiendas SFCC en staging. Medir reducción real de tiempo de QA pre-release.
3. **Fase 3 (mes 4+):** Decidir si se ofrece como capacidad embedded en propuestas comerciales de PASH (build-as-service) o si se aísla como producto vendible. La decisión depende del LTV observado en fase 2.

### Hipótesis comerciales para validar

- **H1:** Un equipo SFCC pasa de 4–8h de QA manual por release a <30 min de revisión de reporte. **Validable en mes 2 con dato real.**
- **H2:** El equipo confía en el semáforo verde sin re-validación manual ≥70% de las veces para los flujos cubiertos. **Validable en mes 3 con encuesta interna.**
- **H3:** Detectar 1 regresión de performance ≥20% no notada con QA manual paga el costo de infra de 6 meses. **Validable con primer hallazgo real.**
- **H4 [débil]:** Otros implementadores SFCC LatAm pagarían $200–500/mes por acceso a una plataforma SFCC-specific. **No validable en alcance del MVP.**

**Hipótesis comercial principal:** el cliente target NO es "el mercado de e-commerce LATAM". Es **el Tech Lead de un equipo SFCC que hace 2+ releases/mes y todavía hace QA a mano**. Ese cliente paga con presupuesto interno, no con cheque externo — el ROI se mide en horas-ingeniería ahorradas, no en suscripción.

---

*Hardcore AI by 30X — Cohorte 2 — Estación 2*
