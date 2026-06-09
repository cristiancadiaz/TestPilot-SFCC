# Ideal Customer Profile — Plataforma de Testing Continuo con Usuarios Sintéticos

> Perfil de cliente ideal. Derivado de Internal Solution Brief + Deep researches de validación y crítica.

> ⚠️ **Realineado 2026-06-02** (branch `rework/storefront-audit-scope`). La audiencia se **amplía a perfiles no-técnicos** (QA, PM, negocio) gracias a la ventana de lenguaje natural — ver Persona 4. Objetivo canónico en [`PRODUCT.md`](../../PRODUCT.md) §1.

---

## ICP — Segmento beachhead (primeras 4 semanas)

**Cliente primario:** Equipos de ingeniería de **2 a 8 personas** operando una tienda SFCC en **LatAm** (Colombia, Ecuador, México, Chile, Brasil, Perú) que hacen **≥2 deploys/mes** y todavía validan releases con QA manual.

**Verticales prioritarios:**

1. **Implementadores SFCC LatAm operando tiendas propias o de clientes** — agencias certificadas Salesforce con equipos de 3–8 ingenieros responsables del ciclo de vida de la tienda (PASH como caso interno; perfil análogo en BBR, Globant, 4Geeks).
2. **Retailers mid-market con SFCC in-house** — equipos digitales con 500–10,000 órdenes/mes y un Tech Lead responsable de QA pre-release (segmentos como retail moda, beauty, especialidad).
3. **Otros agentes/sistemas AI del ecosistema interno** — pipelines de CI/CD, agentes de code review, dashboards operativos que consumen el JSON de reporte para tomar decisiones de release automatizadas.

**NO es para (explícitamente fuera del ICP):**

- Tiendas Shopify, Magento, VTEX, WooCommerce (la especialización SFCC es el wedge — perdería valor en otro stack).
- Retailers Tier 1 con suites enterprise existentes (Mabl, Testim, Tricentis ya contratado).
- Equipos con ≤1 deploy/mes (QA manual es viable a esa cadencia).
- Tiendas en producción sin ambiente de staging funcional con datos de prueba.
- Equipos sin Tech Lead con autoridad para autorizar excepciones de IP en Akamai/Cloudflare.

---

## Buyer personas

### Persona 1 — Tech Lead / Gerente de Tecnología (sponsor y decisor)

**Quién es:** Ingeniero senior con 7–15 años de experiencia, hands-on con JavaScript/SFRA/SFCC + algo de Node y AWS. Responsable de la calidad del producto en producción y de la cadencia de releases. En PASH específicamente, esta persona es **el sponsor del proyecto**.

**Qué evalúa antes de adoptar:**

- ¿La plataforma corre sobre staging sin contaminar reportes de negocio (órdenes reales, notificaciones a clientes)?
- ¿El reporte es **accionable en <10 minutos**? Si tiene que excavar 50 screenshots para entender qué falló, no lo usa.
- ¿El sistema entiende SFCC lo suficiente para no llenarlo de falsos positivos? Un timeout de 30s en una API de SFCC puede ser normal — el clasificador necesita ese contexto.
- ¿Se integra con el flujo de deploy existente sin pedirle a su equipo aprender una herramienta nueva?
- ¿La infra cuesta menos de $200/mes? Si pasa ese umbral, prefiere QA manual.

**Mata la adopción si:** los falsos positivos son >20% del total de hallazgos; el reporte es ilegible sin tutorial; un release falla por un test mal escrito y no por un bug real; la herramienta no corre por una semana porque "se rompieron los selectores".

### Persona 2 — Ingeniero del equipo (usuario diario)

**Quién es:** Desarrollador SFRA / Node de 2–6 años de experiencia. Hace los deploys, escribe los cartridges, fixea los hotfixes. Es quien recibirá el reporte antes de mergear.

**Qué evalúa:**

- ¿El reporte le dice **exactamente qué se rompió y dónde** (URL, paso, screenshot, mensaje de error)?
- ¿Puede correr el test localmente / on-demand antes de pedir merge, o solo corre automáticamente post-deploy?
- ¿El JSON de salida tiene un schema estable y documentado para que pueda consumirlo desde otros agentes/scripts?
- ¿Hay historial comparable —"este checkout era 2.1s hace una semana, ahora 3.4s"— o solo el resultado del último run?

**Mata la adopción si:** el reporte solo dice "checkout falló" sin contexto; el JSON cambia de schema entre ejecuciones; no hay forma de correr tests on-demand; el sistema falla y nadie sabe debuggearlo.

### Persona 3 — Otros agentes / sistemas AI consumidores (usuario indirecto)

**Quién es:** Pipeline CI/CD (GitHub Actions, GitLab CI, Jenkins), agente de code review, dashboard operativo del Tech Lead. Consumen el output via API o lectura de JSON en S3.

**Qué evalúa:**

- ¿El endpoint REST tiene **versionado claro** (`/v1/run`, `/v1/results/{id}`)?
- ¿El schema de respuesta es estable o cualquier deploy del agente rompe consumidores downstream?
- ¿Hay autenticación y rate-limiting documentados?
- ¿Las latencias de respuesta están bounded (timeout máximo conocido) para no colgar el CI/CD?

**Mata la adopción si:** no hay versionado de API; un cambio de schema rompe el pipeline silenciosamente; la respuesta puede tardar 20 minutos sin warning de timeout.

### Persona 4 — Miembro no-técnico del equipo (QA, PM, negocio) — habilitado por la ventana NL

**Quién es:** Analista de QA, Product Manager o stakeholder de negocio sin habilidad (ni interés) para escribir JSON o consumir una API. Hoy depende de un ingeniero para lanzar cualquier validación.

**Qué evalúa:**

- ¿Puedo lanzar una prueba **describiendo en español** lo que quiero validar, sin ayuda de un dev?
- ¿El **documento de auditoría** es legible para mí (no solo para ingenieros)?
- ¿Puedo verificar una **promoción/descuento** o un cambio de contenido antes de que salga, por mi cuenta?

**Mata la adopción si:** la ventana NL traduce mal mi intención y ejecuta algo distinto a lo que pedí; el reporte asume conocimiento técnico que no tengo.

**Por qué importa:** multiplica quién puede pedir una auditoría pre-deploy — descarga al ingeniero de ser el único que puede operar el sistema. Es el efecto directo de la ventana de lenguaje natural.

---

## Pains (puntos de dolor)

### Pain operativo

- **El QA manual pre-release consume 4–8 horas de un ingeniero senior cada vez que hay un deploy.** Para un equipo con 4 deploys/mes son 16–32h/mes en QA repetitivo — entre $1,500 y $3,000 USD/mes en horas-ingeniería.
- **No hay baseline histórico de performance.** Si el checkout pasa de 2.1s a 3.4s en un release, nadie lo nota hasta que el equipo de negocio reporta caída de conversión semanas después. El estudio Google/SOASTA estima **4.42% de caída en conversión por cada segundo adicional** de carga en mobile.
- **Los bugs en checkout que llegan a producción cuestan 15–30x más que detectados en pre-release** (IBM 2023). Un bug en checkout durante un fin de semana sin oncall puede costar entre $15K y $50K en revenue perdido para una tienda con 1K órdenes/mes.

### Pain estratégico

- **El equipo no escala con la frecuencia de releases.** A más cartridges custom, más fuerza de QA manual se necesita, y el cuello de botella se vuelve permanente.
- **No hay manera de demostrar al sponsor que "la tienda está lista para producción"** más allá del juicio subjetivo del ingeniero de turno. Cuando algo se rompe, no hay traza de qué se probó y qué no.
- **Los implementadores SFCC venden proyectos pero no venden operación continua confiable.** Sin testing automatizado, el go-live es siempre una negociación tensa con el cliente sobre "qué incluye QA".

### Pain específico de SFCC

- **Los selectores CSS se rompen con cada deploy de cartridges.** El 40–60% del tiempo de mantenimiento de cualquier suite E2E sobre SFCC se va en arreglar selectores rotos (Testim State of Testing 2024).
- **Akamai Bot Manager bloquea Playwright por defecto.** Sin excepción de IP, las pruebas devuelven captchas o redirects silenciosos — el test pasa técnicamente pero nunca llegó al checkout.
- **SFCC no tiene "modo dry-run" para transacciones.** Las órdenes en staging son órdenes reales en el sistema hasta que se cancelen manualmente.

---

## Deseos

- **Una herramienta interna que el equipo controle**, sin dependencia de un SaaS externo que cobra por seat o por test run.
- **Reportes consumibles tanto por humanos como por agentes** — un solo output que sirva al ingeniero antes de mergear y al pipeline CI/CD que decide si seguir el deploy.
- **Historial de performance para defender al equipo ante negocio** — "el checkout era 2.1s hace 4 semanas, hoy es 3.4s; aquí está el deploy que lo rompió".
- **Configuración explícita y versionada de los criterios de evaluación** — qué es un bug, qué es un warning, qué es un falso positivo conocido. Ground truth que el equipo controla, no la herramienta.
- **Detección temprana de regresiones que el QA manual no atrapa** — particularmente performance, errores HTTP intermitentes, y comportamientos diferenciales por dispositivo/región.
- **Acceso sin barrera técnica** — que un perfil no-técnico (QA/PM/negocio) lance una prueba en **lenguaje natural**, sin escribir JSON ni depender de un ingeniero.
- **Auditoría multi-dimensión, no solo "pasa/falla"** — un documento que cubra integridad de comercio (precios/promos), rendimiento, locale (CO/EC), accesibilidad y salud del cliente, con evidencia enlazada.

---

## Triggers de compra (qué eventos detonan adopción)

1. **Un bug en checkout escapa a producción y el sponsor pide explicación.** El "no se probó eso" deja de ser respuesta aceptable después de la primera vez que pasa con impacto en ventas.
2. **El equipo crece de 3 a 6 ingenieros y la frecuencia de releases sube de 2/mes a 6/mes.** El QA manual se vuelve imposible de sostener.
3. **Un cliente pregunta explícitamente "qué cobertura de testing automatizado tienen".** Para un implementador SFCC vendiendo proyectos, no tener respuesta es una desventaja competitiva inmediata.
4. **Performance reportado por usuarios cae y nadie tiene baseline para defender la tienda.** El sponsor descubre que no hay manera de demostrar cuándo se rompió ni qué deploy lo causó.
5. **Black Friday / Hot Sale se acerca.** El costo de un bug en pico de tráfico justifica inversión que durante el año normal se posterga.

---

## Objeciones probables

| Objeción | Respuesta honesta |
|---|---|
| "Mabl/Testim ya hace esto, ¿por qué construirlo?" | Mabl funciona, pero (a) cuesta $15K–60K/año en plan enterprise, (b) no conoce SFCC ni gateways de pago LatAm, (c) los selectores se rompen igual y no hay nadie del lado de Mabl que sepa qué `data-cmp` usar en este cartridge custom. La plataforma interna acumula conocimiento SFCC-específico del equipo. |
| "Tenemos QA manual y funciona." | Funciona hasta 2 deploys/mes con 1 ingeniero senior dedicado. A 4 deploys/mes ya es cuello de botella. Y no detecta regresiones de performance — solo bugs funcionales obvios. La primera vez que un deploy degrada el checkout de 2.1s a 3.4s y nadie lo nota durante 2 semanas, el costo del QA manual queda claro. |
| "¿Qué pasa cuando se rompen los selectores con un deploy de cartridge?" | Pasa, y va a pasar. El plan es: (a) usar `data-cmp` y `data-testid` semánticos —no clases CSS volátiles—, (b) loggear cuándo un selector falla para crear backlog visible, (c) post-MVP, agregar capa de auto-healing con el LLM sugiriendo el nuevo selector. Es trabajo, no magia. |
| "El LLM va a clasificar mal los errores y vamos a perder confianza en los reportes." | Riesgo real. Mitigación: el LLM **NO** decide qué es un bug — solo clasifica si un error encontrado por Playwright (HTTP 500, timeout, elemento faltante) cae en una de N categorías predefinidas. La decisión final de "rojo/amarillo/verde" sigue reglas deterministas. El LLM ayuda en el resumen, no en el veredicto. |
| "¿No nos van a banear por bot las propias herramientas anti-bot de la tienda?" | Sí, si no se configura excepción de IP en Akamai/Cloudflare antes de empezar. Por eso es **dependencia crítica** del proyecto — sin esa excepción, no arrancamos. |
| "Otros agentes consumiendo el JSON van a romper cuando cambiemos el schema." | Por eso versionamos el endpoint desde el día 1 (`/v1/run`). Cambios breaking suben a `/v2/`. Los consumidores deciden cuándo migrar. |
| "¿Y si el equipo abandona la herramienta post-curso?" | Riesgo real — mantener una suite SFCC requiere 4–8h/semana. Mitigación: el **alcance completo se entrega incrementalmente** (cada incremento muestra valor temprano — **sin recortar módulos del producto**); trigger integrado en el git push para uso automático, no opcional; y auto-healing de selectores post-MVP para bajar el mantenimiento. La **ventana NL** amplía la base de usuarios más allá de los ingenieros, lo que sube el uso sostenido. |

---

*Hardcore AI by 30X — Cohorte 2 — Estación 2. Realineado 2026-06-02 (audiencia ampliada a no-técnicos vía ventana NL; auditoría multi-dimensión) — objetivo canónico en `PRODUCT.md` §1.*
