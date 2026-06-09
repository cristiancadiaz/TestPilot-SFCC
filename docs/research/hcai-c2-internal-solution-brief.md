# Internal Solution Brief — Hardcore AI Cohorte 2

> **Vigencia (2026-06-02):** insumo histórico de la Estación 1. Notablemente, este brief **ya anticipaba** el recorrido completo (`login → búsqueda → categoría → PDP → carrito → checkout`), el agente que *"clasifica errores + genera resumen"*, y la entrada por **lenguaje natural** — la visión amplia estuvo desde el inicio; la inception la recortó para el MVP de 4 semanas. El **objetivo y alcance vigentes** están en [`PRODUCT.md`](../../PRODUCT.md) §1 (realineado 2026-06-02). Si este brief contradice `PRODUCT.md` o `specs/*.json`, gana lo canónico.

## SOLUCION

**Nombre de la solucion:** Plataforma de Testing Continuo con Usuarios Sinteticos para SFCC

**Descripcion en una linea:** Dashboard interno + agente de testing que permite configurar y lanzar flujos automatizados con usuarios sinteticos sobre tiendas SFCC, visualizar resultados en tiempo real y obtener un semaforo de deploy-gate consumible por humanos y otros agentes.

**Autor:** Christian

---

## 1. PROBLEMA DE NEGOCIO

Las tiendas SFCC del equipo no tienen testing automatizado de ningun tipo. Cada release se valida manualmente: un ingeniero navega el checkout, la busqueda y el PDP en diferentes dispositivos — un proceso que toma entre 4 y 8 horas por ciclo y que no escala con la frecuencia de deploys. Los bugs de checkout que llegan a produccion cuestan entre 15x y 30x mas que los detectados antes del release (IBM, 2023), y las regresiones de performance (un checkout que pasa de 2s a 4s de carga) son invisibles hasta que el equipo de negocio nota una caida en conversion.

**Cuantificacion del problema:**

| Metrica                                            | Situacion actual                                                   |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| Ciclos de testing manual por release               | 4-8 horas de ingenieria                                            |
| Frecuencia de deploys                              | Variable, sin cadencia definida                                    |
| Bugs detectados por usuarios en produccion         | Sin datos (no se mide)                                             |
| Tiempo hasta detectar una regresion de performance | Dias o semanas                                                     |
| Costo de un bug en checkout en produccion          | $500-$50,000 USD (segun volumen y duracion) — estimacion industria |

**Impacto estimado para una tienda con 1,000 ordenes/mes:**

- Conversion rate promedio checkout SFCC: 1.8-3.5%
- Cada segundo adicional de carga en mobile reduce conversion 4.42% (Google/SOASTA benchmark)
- Una regresion de performance de 2s no detectada durante 2 semanas puede costar 8-9% en conversion perdida
- Ahorro en tiempo de ingenieria: 4-8 horas/release → 30 minutos de revision de reporte automatizado

_Nota: Las cifras de conversion son benchmarks de industria — deben validarse con datos reales de la tienda._

---

## 2. STAKEHOLDERS Y SPONSOR

**Sponsor:** Gerente de Tecnologia / Tech Lead del equipo

**Usuarios finales:**

- Ingenieros del equipo (consumen el reporte antes de cada deploy)
- Otros agentes de IA del ecosistema (consumen el JSON estructurado como input)

**¿Quien puede bloquear la adopcion?**

- Equipo de DevOps / IT (acceso a credenciales de staging SFCC, apertura de puertos para Playwright)
- Equipo de Seguridad (aprobacion de scripts automatizados corriendo contra la tienda)
- Equipo de Negocio (si los test runs en staging generan ordenes de prueba que contaminen reportes)

---

## 3. ESTADO ACTUAL

**¿Como se resuelve hoy?**

- Testing completamente manual antes de cada release
- Un ingeniero navega los flujos principales en diferentes dispositivos y browsers
- No hay criterios formales de "pasar/fallar" — la aprobacion es subjetiva
- Las regresiones de performance no se miden — solo se notan cuando son muy evidentes
- No existe historial de performance ni baseline de comparacion

**¿Que herramientas se usan actualmente?**

- Browser manual (Chrome, Firefox) para QA
- Business Manager de SFCC para verificar configuraciones
- No hay herramientas de testing automatizado

**¿Que funciona bien del proceso actual?**

- El ingeniero que hace QA conoce la tienda en profundidad y detecta errores visuales o de UX que un script no detectaria

**¿Que no funciona?**

- No escala: a mayor frecuencia de deploys, el QA manual se vuelve cuello de botella
- Sin cobertura de performance: los tiempos de carga no se miden de forma sistematica
- Sin historial: no es posible comparar si el checkout de hoy es mas rapido o lento que el de la semana pasada
- Los bugs llegan a produccion porque el QA manual no cubre todos los flujos posibles

---

## 4. ESTADO FUTURO DESEADO

**¿Como se veria el proceso si la solucion funciona perfectamente?**

- Antes de cada deploy, el agente corre automaticamente 2-3 flujos criticos con perfiles sinteticos parametrizados
- El equipo recibe un reporte con semaforo (verde/amarillo/rojo) en menos de 10 minutos
- Las regresiones de performance se detectan inmediatamente comparando contra el baseline historico
- Otros agentes del equipo (code review, CI/CD) pueden consultar el estado de la tienda via API antes de aprobar un merge
- El equipo tiene por primera vez un dashboard de performance historico de la tienda

**¿Que cambia para el equipo en su dia a dia?**

- QA manual se reduce de 4-8 horas a 30 minutos de revision del reporte
- Los deploys tienen un criterio objetivo de "listo para produccion"
- Las incidencias de produccion por regresion de checkout disminuyen progresivamente

---

## 5. CRITERIOS DE EXITO

| Metrica                                                   | Valor actual     | Target (semana 4)                                      |
| --------------------------------------------------------- | ---------------- | ------------------------------------------------------ |
| Tiempo de ciclo QA por release                            | 4-8 horas manual | <30 min (revision de reporte)                          |
| Flujos E2E con cobertura automatizada                     | 0                | 2 flujos criticos                                      |
| Tiempo de deteccion de regresion de performance           | Dias/semanas     | <1 hora                                                |
| Confianza del equipo para deployar sin QA manual completo | 0%               | 70% para flujos cubiertos                              |
| Reportes generados y consumidos correctamente             | 0                | 1 reporte por ejecucion, legible por humanos y agentes |

---

## 6. RESTRICCIONES

**Restricciones tecnicas:**

- Playwright en AWS Lambda tiene limitaciones de tamano de deployment — usar ECS Fargate con imagen Docker
- La tienda puede tener proteccion anti-bot (Akamai/Cloudflare) que bloquee Playwright — requiere excepcion de IP de testing
- Los tests deben correr en staging, no en produccion — requiere ambiente de staging funcional y con datos de prueba

**Restricciones de datos:**

- Las credenciales de la tienda (Business Manager, API keys) no pueden almacenarse en el codigo — usar AWS Secrets Manager
- Los datos de clientes sinteticos deben ser ficticios — nunca usar datos reales de clientes

**Restricciones organizacionales:**

- Timeline de 4 semanas para MVP funcional
- El equipo no tiene experiencia previa en Playwright ni en testing automatizado
- Se necesita un ambiente de staging con datos de prueba limpios (tarjetas de prueba, productos en inventario)

**Restricciones de compliance:**

- El benchmarking de competidores via scraping automatizado puede violar sus ToS — fuera de alcance del MVP
- Los test runs en staging no deben generar ordenes reales o comunicaciones a clientes

---

## 7. ENFOQUE TECNICO PROPUESTO

**¿Que capacidad de AI aplica?** Agente con Tools + Navegacion headless. El modelo recibe la instruccion en lenguaje natural, la traduce a una configuracion de perfil sintetico (JSON estructurado), orquesta la navegacion via Playwright, interpreta los resultados (clasifica errores reales vs ruido), y genera el reporte estructurado.

**¿Por que AI y no automatizacion tradicional?** La parte deterministica (navegar, hacer click, medir tiempos) la hace Playwright. La IA agrega: (1) traducir instrucciones en lenguaje natural a configs, (2) clasificar si un error es un bug real o comportamiento esperado, (3) generar el resumen en markdown comprensible para humanos. Sin IA, el sistema sigue siendo util — la IA lo hace mas flexible y el output mas accionable.

**Arquitectura de alto nivel:**

```
  Dashboard web interno
  (campo JSON: store_url + credenciales + productos + flujos + perfiles)
              │
              ▼
    API REST POST /v1/run
              │
              ▼
    Claude API — traduce config JSON a SyntheticUserConfig validado
              │
              ▼
    Orquestador (AWS Step Functions)
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
 Perfil 1  Perfil 2  Perfil 3
(mobile/CO)(desktop/CO)(desktop/EC)
    │         │          │
    └────┬────┘
         ▼
  ECS Fargate + Playwright
  Flujo: login → busqueda → categoria → PDP → carrito → checkout
         │
    ┌────┴─────────────────┐
    ▼                      ▼
  Screenshots OK + FAIL   Metricas
  por modulo (S3)         (tiempo/paso, HTTP status, errores)
         │
         ▼
  Claude API — clasifica errores + genera resumen markdown
         │
         ▼
  Output: JSON + markdown + semaforo (verde/amarillo/rojo)
  DynamoDB (historial + baseline p95) — Dashboard muestra resultados
```

**Stack propuesto:**

- **Frontend**: Dashboard web interno (React o HTML/JS simple — TBD) con campo de entrada JSON y visualizacion de resultados en tiempo real
- Node.js / Python (orquestador y API backend)
- AWS ECS Fargate + Docker con Playwright (ejecucion de flujos)
- AWS Step Functions (orquestacion del flujo multi-perfil)
- Claude API (traduccion de instrucciones + clasificacion de errores + resumen)
- AWS S3 (almacenamiento de screenshots OK + FAIL por modulo — estimar ~17 GB/mes a escala completa)
- AWS DynamoDB (historial de ejecuciones y metricas)
- AWS Lambda + API Gateway (endpoint REST de ingesta)
- AWS Secrets Manager (credenciales del usuario de prueba — nunca en codigo ni logs)
- SFCC staging (tienda objetivo de las pruebas)

---

## 8. RIESGOS Y DEPENDENCIAS

| Riesgo                                            | Probabilidad | Mitigacion                                                                                                                 |
| ------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Proteccion anti-bot bloquea Playwright            | Alta         | Configurar excepcion de IP en Akamai/Cloudflare para el rango de IPs de ECS antes de empezar                               |
| Selectores de SFCC se rompen con deploys          | Alta         | Usar data attributes semanticos (`data-cmp`, `data-testid`) en lugar de clases CSS; documentar selectores criticos         |
| Ambiente de staging no tiene datos de prueba      | Media        | Definir dataset minimo (5 productos, 1 tarjeta de prueba, 1 cliente test) como prerequisito del proyecto                   |
| El LLM genera configs incorrectas de perfil       | Media        | Validar el JSON generado contra un schema definido antes de ejecutar; loggear instruccion + config generada para debugging |
| Costo de ECS + screenshots escala inesperadamente | Baja         | Poner un limite de ejecuciones por dia en el MVP (max 10 runs/dia); revisar costos en semana 2                             |
| El equipo no adopta la herramienta post-curso     | Media        | Integrar el trigger en el proceso de deploy existente (git push → ejecucion automatica) para eliminar friccion de adopcion |

**Dependencias criticas:**

- Acceso a ambiente de staging SFCC con datos de prueba configurados
- Excepcion de IP para testing en el sistema anti-bot de la tienda
- Cuenta de Claude API (o OpenAI) con limites de uso suficientes
- Credenciales de Business Manager de SFCC en AWS Secrets Manager
- Definicion documentada de "error real vs comportamiento esperado" de la tienda

---

## 9. LIMITES DE ALCANCE

**En alcance (lo que SI construyo en 4 semanas):**

- Dashboard web interno con dos pantallas principales: (a) registro de ambientes y (b) lanzamiento de pruebas + historial
- Soporte para 3 ambientes: sandbox, development, staging — cada uno con dos tipos de credenciales separadas en Secrets Manager:
  - `env_access_credentials`: autenticacion contra la puerta del ambiente (HTTP Basic Auth / proxy gate — nivel infraestructura)
  - `shopper_credentials`: usuario SFCC registrado (@testpilot.internal) que ejecuta el checkout (nivel aplicacion)
- Campo de entrada JSON en el dashboard con: environment_id, productos a buscar/validar, flujos y perfiles — SIN credenciales en el payload
- Login con usuario shopper como primer paso de cada flujo (el storefront requiere autenticacion para comprar)
- API REST backend versionada (`POST /v1/run`) consumible por el dashboard y por agentes CI/CD externos
- 3 perfiles sinteticos (mobile/Colombia, desktop/Colombia, desktop/Ecuador)
- 2 flujos: (1) checkout-full: login → busqueda → categoria → PDP → carrito → checkout con pago que falla al final; (2) checkout-card-declined: mismo recorrido, pago rechazado, validar mensaje de error
- Medicion de tiempo por paso y deteccion de errores HTTP
- Screenshot en cada modulo del flujo, tanto en estado OK como en estado FAIL — almacenados en S3 nombrados por run_id/perfil/flujo/paso
- Reporte en JSON estructurado + resumen en markdown
- Historial de ejecuciones en DynamoDB (comparacion vs baseline p95)
- Semaforo 3 estados: verde (sin errores, performance ok), amarillo (degradacion vs baseline), rojo (error funcional)

**Fuera de alcance (lo que NO construyo ahora):**

- Auto-reparacion de selectores rotos con IA (post-MVP)
- Testing de flujos de devolucion o registro de nuevos usuarios (semana 5+)
- Integracion automatica con CI/CD pipeline (post-MVP — el trigger es manual via dashboard o API en el MVP)
- Perfiles con comportamiento cognitivo complejo (scroll, hover, tiempo de decision) — navegacion directa
- Benchmarking de competidores via scraping (riesgo legal — viola ToS)
- Monitor continuo en produccion (solo staging en MVP)

---

## Checklist de entrega

- [ ] Problema identificado y cuantificado con datos estimados de industria
- [ ] Sponsor y stakeholders identificados
- [ ] Estado actual documentado (proceso, herramientas, pain points)
- [ ] Estado futuro deseado definido
- [ ] Deep research de validacion completado
- [ ] Deep research de critica completado
- [ ] Internal Solution Brief completado (este documento)
- [ ] Listo para presentar en la Estacion 2 (miercoles 13 de mayo)
