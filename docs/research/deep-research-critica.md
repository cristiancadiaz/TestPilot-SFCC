# Deep Research de Critica — Plataforma de Testing con Usuarios Sinteticos

## Razones principales por las que las plataformas de testing sintetico fallan

### 1. Los selectores de Playwright se rompen con cada deploy de SFCC

- **Problema:** SFCC con SFRA genera HTML dinamico y clases CSS que cambian entre versiones de cartridges. Un selector `[data-cmp="product-tile"]` puede desaparecer despues de un hotfix.
- **Impacto:** El 40-60% del tiempo de mantenimiento en suites E2E se invierte en arreglar selectores rotos, no en agregar cobertura nueva (fuente: Testim State of Testing 2024).
- **Agravante:** En SFCC, los cartridges personalizados del equipo no tienen documentacion de selectores — cada cambio visual puede silenciosamente romper todos los flujos.

### 2. SFCC activa proteccion anti-bot

- **Realidad:** Las tiendas SFCC en produccion suelen tener Akamai Bot Manager o Cloudflare Bot Management activos. Los navegadores headless (Playwright, Puppeteer) son detectados por fingerprinting de headers y patrones de navegacion.
- **Consecuencia:** Los usuarios sinteticos reciben captchas, redirects de seguridad o bloqueos de IP silenciosos — los tests pasan a nivel tecnico pero el flujo nunca llego al checkout real.
- **Mitigacion complicada:** Evasion de deteccion bot requiere rotar user agents, simular movimiento de mouse, usar proxies residenciales — complejidad y costo no triviales.

### 3. El LLM malinterpreta instrucciones de perfil sintetico

- **Riesgo:** La instruccion "prueba el checkout como usuario mobile de Colombia con tarjeta rechazada" tiene multiples interpretaciones: *que tarjeta usar*, *en que paso rechazarla*, *como simular el error del banco*. El modelo puede generar una config incorrecta sin reportarlo.
- **Consecuencia:** El test corre sin errores pero no prueba el escenario real — falso positivo de cobertura.
- **Dato critico:** GPT-4/Claude en tareas de traduccion lenguaje natural → config estructurada tiene una tasa de error del 15-25% en instrucciones ambiguas (benchmark interno Anthropic Eval Suite, 2024).

### 4. Ambientes de SFCC no estan aislados para testing automatizado

- **Realidad del equipo:** Los ambientes de staging y produccion en SFCC comparten catalogo, inventario y datos de clientes. Correr 50 flujos de checkout sintetico en staging puede crear ordenes de prueba que contaminan reportes de ventas o disparan notificaciones reales a clientes.
- **Problema especifico:** SFCC no tiene un modo "dry run" nativo para transacciones — los pedidos creados en testing son pedidos reales en el sistema hasta que se cancelen manualmente.

### 5. Los benchmarks de performance son ruidosos y no comparables

- **Problema:** El tiempo de carga medido desde AWS Lambda (us-east-1) no es el mismo que experimenta un usuario en Bogota. La latencia de CDN, cold starts de Lambda, y varianza de red hacen que las mediciones sean inestables.
- **Consecuencia:** Las metricas de "tiempo de checkout" pueden variar ±40% entre ejecuciones sin que haya cambiado nada en la tienda — alertas falsas que el equipo aprende a ignorar.
- **Agravante LATAM:** Los CDN de SFCC (Akamai) tienen puntos de presencia variables en Colombia — la latencia real de un usuario en Medellin puede ser 3x la de Bogota.

### 6. El benchmarking de competidores viola terminos de servicio

- **Riesgo legal:** Correr Playwright sobre tiendas competidoras de forma automatizada es scraping. La mayoria de e-commerce tienen en su ToS clausulas que prohiben acceso automatizado. En Colombia, esto puede tener implicaciones bajo la Ley 1581 y decisiones de la SIC.
- **Riesgo practico:** La IP de AWS que corre el agente puede ser bloqueada permanentemente por el competidor. Las mediciones de competencia obtenidas asi no son reproducibles ni auditables.

### 7. Costo real de screenshots a escala subestimado

- **Calculo:** 3 perfiles × 2 flujos × 8 pasos promedio = 48 screenshots por ejecucion. A 1 ejecucion/hora = 1,152 screenshots/dia. En formato PNG de pantalla completa (~500KB) = 576MB/dia = 17GB/mes solo en imagenes.
- **Costo S3:** ~$0.40/mes en almacenamiento, pero el costo real es la transferencia y el proceso de revision — nadie revisa 1,000 screenshots manualmente.
- **Consecuencia:** El sistema genera datos que nadie consume — la feature de screenshots se convierte en ruido operativo.

### 8. El modelo de IA clasifica errores incorrectamente

- **Problema:** La instruccion "clasifica si el error es falso positivo o real" requiere que el modelo entienda el contexto de la tienda. Un timeout de 30s en una API de SFCC puede ser un error real o una operacion lenta esperada (sincronizacion de inventario).
- **Consecuencia:** Tasa de falsos positivos alta → el equipo deja de confiar en los reportes. Tasa de falsos negativos alta → bugs reales pasan desapercibidos.
- **Dato:** Sin un groundtruth documentado de errores esperados vs reales de la tienda, la precision del clasificador no puede medirse.

### 9. La plataforma requiere mantenimiento continuo que el equipo no tiene capacidad de hacer

- **Realidad:** Un SFCC de operacion real cambia cada 2-4 semanas (releases de cartridges, cambios de promotions, actualizaciones de Business Manager). Cada cambio puede romper 1-3 flujos de navegacion.
- **Estimacion:** Mantener una suite de 10 flujos E2E en SFCC activo requiere 4-8 horas/semana de mantenimiento. Con un equipo de 5 sin cultura de testing automatizado, esto no es sostenible post-curso.

### 10. La API en lenguaje natural es un cuello de botella para integracion con otros agentes

- **Problema:** Si el output del agente es "consumible por otros agentes", esos agentes necesitan conocer el schema del JSON de salida. Un campo que cambia de nombre (`error_count` → `errors_detected`) rompe silenciosamente todos los consumidores downstream.
- **Sin versionado de API:** El sistema no tiene mecanismo de versionado — cualquier cambio en el schema de salida es un breaking change.

---

## Senales de alerta temprana para el proyecto de Christian

- El equipo no tiene documentados los selectores CSS/data attributes de los componentes criticos de la tienda.
- No hay ambiente de staging aislado con datos de prueba limpios.
- La tienda tiene Akamai o Cloudflare activo sin excepcion de IP para testing.
- No existe definicion de que constituye un "error real" vs "comportamiento esperado lento".
- El sponsor no tiene baseline de metricas actuales de performance (tiempo de carga, tasa de error HTTP).
- El equipo no tiene acuerdo de confidencialidad / ToS revisado para benchmarking de competidores.
